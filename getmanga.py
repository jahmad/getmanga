#!/usr/bin/env python
# -*- coding: utf8 -*-
"""Yet another (multi-site) manga downloader"""

# Copyright (c) 2010, Jamaludin Ahmad
# Released subject to the MIT License.
# Please see http://en.wikipedia.org/wiki/MIT_License

# Changes
# version 0.3 : download threading
# version 0.2 : config support for batch download
# version 0.1 : initial release

from __future__ import division

import ConfigParser
import Queue
import StringIO
import gzip
import os
import re
import sys
import threading
import urllib2
import zipfile

try:
    import argparse
except ImportError:
    sys.exit('You need to have "argparse" module installed '
             'to run this script')

if sys.version_info < (2, 7):
    try:
        from ordereddict import OrderedDict
    except ImportError:
        sys.exit('You need to have "ordereddict" module installed '
                 'to run this script')
else:
    from collections import OrderedDict


__version__ = '0.3'


class MangaException(Exception):
    """Exception class for manga"""
    pass


class Manga(object):
    """Base class for manga downloading"""
    site = None

    chapters_regex = None
    pages_regex = None
    image_regex = None

    def __init__(self, title=None, directory='.', concurrency=4):
        """Initiate manga title and download directory"""
        self.title = self._title(title)
        self.concurrency = concurrency

        directory = os.path.abspath(os.path.expanduser(directory))
        if not os.path.isdir(directory):
            try:
                os.makedirs(directory)
            except OSError, msg:
                raise MangaException(msg)
        self.directory = directory

    def get(self, chapter=None, begin=None, end=None, new=False):
        """Decides which action executed from user input"""
        chapter_dict = self.chapterdict()
        chapter_ids = chapter_dict.keys()

        if new:
            latest = chapter_ids[-1]
            self.download(latest, chapter_dict[latest])

        elif chapter:
            chapter_id = self._id(chapter)
            if chapter_id in chapter_dict:
                self.download(chapter_id, chapter_dict[chapter_id])
            else:
                raise MangaException('Chapter does not exist')

        elif begin:
            start = position(self._id(begin), chapter_ids)
            stop = position(self._id(end), chapter_ids) + 1 if end else None

            try:
                for chapter_id in chapter_ids[start:stop]:
                    self.download(chapter_id, chapter_dict[chapter_id])
            except IndexError:
                raise MangaException('Can\'t begin from non-existent '
                                     'chapter')

        else:
            for (chapter_id, chapter_dir) in chapter_dict.iteritems():
                self.download(chapter_id, chapter_dir)

    def chapterdict(self):
        """Returns a dictionary of manga chapters available"""
        sys.stdout.write('retrieving %s info page..\n' % self.title)

        info_html = urlopen(self._infourl())
        chapters = self.chapters_regex.findall(info_html)
        chapters = sorted(set(chapters), key=lambda x: float(x[1]))

        chapter_dict = OrderedDict()
        for (chapter_dir, chapter_id) in chapters:
            if self._verify(chapter_dir):
                chapter_dir = self._cleanup(chapter_dir)
                chapter_dict.update({chapter_id: chapter_dir})

        if chapter_dict:
            return chapter_dict
        else:
            raise MangaException('%s: No such title' % self.title)

    def download(self, chapter_id, chapter_dir):
        """Download and create zipped manga chapter"""
        cbz_name = os.path.join(self.directory,
                                self._name(chapter_id, chapter_dir))
        if os.path.isfile(cbz_name):
            sys.stdout.write('file %s exist, skipped download\n' %
                              cbz_name)
        else:
            tmp_name = '%s.tmp' % cbz_name
            chapter_html = urlopen(self._pageurl(chapter_dir))
            pages = self.pages_regex.findall(chapter_html)
            pages = sorted(list(set(pages)), key=int)

            sys.stdout.write('downloading %s %s:\n' %
                             (self.title, chapter_id))
            progress(0, len(pages))

            threads = []
            semaphore = threading.Semaphore(self.concurrency)
            queue = Queue.Queue()
            for page in pages:
                thread = threading.Thread(target=self._pagedownload,
                                          args=(semaphore, queue,
                                                chapter_dir, page))
                thread.daemon = True
                thread.start()
                threads.append(thread)

            try:
                cbz = zipfile.ZipFile(tmp_name, mode='w',
                                      compression=zipfile.ZIP_DEFLATED)
                for thread in threads:
                    thread.join()
                    image = queue.get()
                    if image[0]:
                        cbz.writestr(image[0], image[1])
                        progress(len(cbz.filelist), len(pages))
                    else:
                        raise MangaException(image[1])
            except Exception, msg:
                cbz.close()
                os.remove(tmp_name)
                raise MangaException(msg)
            else:
                cbz.close()
                os.rename(tmp_name, cbz_name)

    def _pagedownload(self, semaphore, queue, chapter_dir, page):
        """Downloads page images inside a thread"""
        try:
            semaphore.acquire()
            page_html = urlopen(self._pageurl(chapter_dir, page))
            image_url = self.image_regex.findall(page_html)[0]
            image_ext = image_url.split('.')[-1]
            image_name = 'page%03d.%s' % (int(page), image_ext)
            image_file = urlopen(image_url)
        except MangaException, msg:
            queue.put((None, msg))
        else:
            queue.put((image_name, image_file))
        finally:
            semaphore.release()

    @staticmethod
    def _title(title):
        """Return the right manga title from user input"""
        return re.sub(r'[^a-z0-9]+', '_',
                      re.sub(r'^[^a-z0-9]+|[^a-z0-9]+$', '', title.lower()))

    @staticmethod
    def _id(chapter):
        """Returns the right chapter number formatting from user input"""
        return str(chapter)

    def _infourl(self):
        """Returns the index page's url of manga title"""
        return '%s/manga/%s/' % (self.site, self.title)

    def _pageurl(self, chapter_dir, page='1'):
        """Returns manga image page url"""
        return '%s%s/%s' % (self.site, chapter_dir, page)

    def _name(self, chapter_id, chapter_dir):
        """Returns the appropriate name for the zipped chapter"""
        try:
            volume_id = re.search(r'v[0-9]+', chapter_dir).group()
            filename = '%s_%sc%s.cbz' % \
                        (self.title, volume_id, chapter_id)
        except AttributeError:
            filename = '%s_c%s.cbz' % (self.title, chapter_id)
        return filename

    def _verify(self, chapter_dir):
        """Returns boolean status of a chapter validity"""
        return True

    @staticmethod
    def _cleanup(chapter_dir):
        """Returns a cleanup chapter directory"""
        return chapter_dir


class MangaFox(Manga):
    """class for mangafox site"""
    site = 'http://www.mangafox.com'

    chapters_regex = re.compile(r'</a>[ \r\n]*<a href="([^ ]+)" class='
                                r'"ch" title="[^"]+">.* ([\.0-9]+)</a>')
    pages_regex = re.compile(r'option value="[0-9]+" .*?>([0-9]+)</option')
    image_regex = re.compile(r'img src="([^ ]+)" onerror="')

    def _infourl(self):
        """Returns the index page's url of manga title"""
        return '%s/manga/%s/?no_warning=1' % (self.site, self.title)

    def _pageurl(self, chapter_dir, page='1'):
        """Returns manga image page url"""
        return '%s%s%s.html' % (self.site, chapter_dir, page)


class MangaStream(Manga):
    """class for mangastream site"""
    site = 'http://mangastream.com'

    chapters_regex = re.compile(r'<a href="([^ ]+)">([0-9]+)')
    pages_regex = re.compile(r'<a href="[^ ]+".*?>([0-9]{1,2})</a>')
    image_regex = re.compile(r'src="([^ ]+)" border="0"')

    def _infourl(self):
        """Returns the index page's url of manga title"""
        return '%s/manga/' % self.site

    def _verify(self, chapter_dir):
        """Returns boolean status of a chapter validity"""
        return re.search(self.title, chapter_dir)

    @staticmethod
    def _cleanup(chapter_dir):
        """Returns a cleanup chapter directory"""
        return re.sub(r'/[0-9]+$', '', chapter_dir)


class MangaToshokan(Manga):
    """class for mangatoshokan site"""
    site = 'http://www.mangatoshokan.com'

    chapters_regex = re.compile(r'href=\'([^ ]+)\' .* ([0-9]+)</a>')
    pages_regex = re.compile(r'<option value="[^ ]+".*?>([0-9]+)</option>')
    image_regex = re.compile(r'dir=\'rtl\'><img src="([^ ]+)"')

    @staticmethod
    def _title(title):
        """Returns the right manga title from user input"""
        return re.sub(r'[^\-a-zA-Z0-9]+', '', re.sub(r'[ _]', '-', title))

    def _infourl(self):
        """Returns the index page's url of manga title"""
        return '%s/series/%s' % (self.site, self.title)


class MangaBle(Manga):
    """class for mangable site"""
    site = 'http://mangable.com'

    chapters_regex = re.compile(r'href="([^ ]+)" .* Chapter ([\.0-9]+)">')
    pages_regex = re.compile(r'option value="[0-9]+">Page ([0-9]+)</opt')
    image_regex = re.compile(r'<img src="([^ ]+)" class="image"')

    @staticmethod
    def _title(title):
        """Returns the right manga title from user input"""
        return re.sub(r'[^\-_a-z0-9]+', '',
                      re.sub(r'\s', '_', title.lower()))

    def _infourl(self):
        """Returns the index page's url of manga title"""
        return '%s/%s' % (self.site, self.title)

    def _pageurl(self, chapter_dir, page=None):
        """Returns manga image page url"""
        if page:
            return '%s%s' % (chapter_dir, page)
        else:
            return chapter_dir


class MangaAnimea(Manga):
    """class for manga animea site"""
    site = 'http://manga.animea.net'

    chapters_regex = re.compile(r'href="([^ ]+)">.* ([\.0-9]+)</a>\s')
    pages_regex = re.compile(r'<option value="[0-9]+".*?>([0-9]+)</option>')
    image_regex = re.compile(r'<img src="([^ ]+)" .* class="chapter_img"')

    @staticmethod
    def _title(title):
        """Returns the right manga title from user input"""
        return re.sub(r'[^a-z0-9_]+', '-', title.lower())

    def _infourl(self):
        """Returns the index page's url of manga title"""
        return '%s/%s.html?skip=1' % (self.site, self.title)

    def _pageurl(self, chapter_dir, page='1'):
        """Returns manga image page url"""
        return re.sub(r'.html$', '-page-%s.html' % page, chapter_dir)

    def _verify(self, chapter_dir):
        """Returns boolean status of a chapter validity"""
        return re.search(self.title, chapter_dir)


class MangaReader(Manga):
    """class for mangareader site"""
    site = 'http://www.mangareader.net'

    chapters_regex = re.compile(r'<a href="([^ ]+)">.+ ([0-9]+)</a>')
    pages_regex = re.compile(r'<option value=.+>\s*([0-9]+)</option>')
    image_regex = re.compile(r'<img id="img" .+ src="([^ ]+)"')

    @staticmethod
    def _title(title):
        """Returns the right manga title from user input"""
        return re.sub(r'[^\-a-z0-9]', '',
                      re.sub(r'[ _]', '-', title.lower()))

    def _infourl(self):
        """Returns the index page's url of manga title"""
        try:
            list_html = urlopen('%s/alphabetical' % self.site)
            info_page = re.findall(r'[0-9]+/' + self.title + '.html',
                        list_html)[0]
            info_url = '%s/%s' % (self.site, info_page)
        except IndexError:
            info_url = self.site
        return info_url

    def _pageurl(self, chapter_dir, page='1'):
        """Returns manga image page url"""
        if re.search(r'.html$', chapter_dir):
            page = re.sub(r'\-[0-9]+/', '-%s/' % page, chapter_dir)
            return '%s%s' % (self.site, page)
        else:
            return '%s%s/%s' % (self.site, chapter_dir, page)


SITE_NAMES = OrderedDict(animea=MangaAnimea,
                         mangable=MangaBle,
                         mangafox=MangaFox,
                         mangareader=MangaReader,
                         mangastream=MangaStream,
                         toshokan=MangaToshokan)


def urlopen(url):
    """Returns data available (html or image file) from a url"""
    request = urllib2.Request(url)
    request.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; U; ' \
                       'Intel Mac OS X 10_6_5; id) AppleWebKit/533.19.4 ' \
                       '(KHTML, like Gecko) Version/5.0.3 Safari/533.19.4')
    request.add_header('Accept-encoding', 'gzip')

    data = None
    retry = 0
    while retry < 5:
        try:
            response = urllib2.urlopen(request, timeout=15)
            data = response.read()
        except urllib2.HTTPError, msg:
            raise MangaException('HTTP Error: %s - %s\n' % (msg.code, url))
        except Exception:
            #what may goes here: urllib2.URLError, socket.timeout,
            #                    httplib.BadStatusLine
            retry += 1
        else:
            if 'content-length' in response.headers.keys():
                if len(data) == \
                        int(response.headers.getheader('content-length')):
                    retry = 5
                else:
                    data = None
                    retry += 1
            else:
                retry = 5
            if ('content-encoding', 'gzip') in response.headers.items():
                compressed = StringIO.StringIO(data)
                data = gzip.GzipFile(fileobj=compressed).read()
            response.close()
    if data:
        return data
    else:
        raise MangaException('Failed to retrieve %s' % url)


def progress(page, total):
    """Display progress bar"""
    page, total = int(page), int(total)
    marks = int(round(50 * (page / total)))
    spaces = int(round(50 - marks))

    loader = '[' + ('#' * int(marks)) + ('-' * int(spaces)) + ']'

    sys.stdout.write('%s page %d of %d\r' % (loader, page, total))
    if page == total:
        sys.stdout.write('\n')
    sys.stdout.flush()


def position(item, listobj):
    """Returns position of an item inside a list object"""
    for index in xrange(len(listobj)):
        if listobj[index] == item:
            return index


def cmdparse():
    """Returns parsed arguments from command line"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', type=str,
                        help='%(prog)s config file')
    parser.add_argument('-s', '--site', choices=(SITE_NAMES.keys()),
                        help='manga site to download from')
    parser.add_argument('-t', '--title', type=str,
                        help='manga title to download')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-n', '--new', action='store_true',
                       help='download the last chapter')
    group.add_argument('-c', '--chapter', type=str,
                       help='chapter number to download')
    parser.add_argument('-d', '--dir', type=str, default='.',
                        help='download directory')
    parser.add_argument('-l', '--limit', type=int, default=4,
                        help='concurrent connection limit')
    parser.add_argument('-v', '--version', action='version',
                        version='%s %s' % (parser.prog, __version__),
                        help='show program version and exit')
    args = parser.parse_args()
    args.begin = None
    args.end = None

    if args.file:
        if not os.path.isfile(args.file):
            parser.print_usage()
            sys.exit('%s: error: config file does not exit' %
                     parser.prog)
    elif not args.site:
        parser.print_usage()
        sys.exit('%s: error: argument -s/--site is required' %
                 parser.prog)
    elif not args.title:
        parser.print_usage()
        sys.exit('%s: error: argument -t/--title is required' %
                 parser.prog)
    elif args.chapter:
        chapter = args.chapter.split('-')
        if len(chapter) == 1:
            args.chapter = int(chapter[0])
        elif len(chapter) == 2:
            args.chapter = None
            args.begin = int(chapter[0])
            args.end = int(chapter[1]) if chapter[1] else None
        if args.end and (args.begin > args.end):
            parser.print_usage()
            sys.exit('%s: error: invalid chapter interval, the end '
                     'should be bigger than start' % parser.prog)
    return args


def configparse(filepath):
    """Returns parsed config from an ini file"""
    if sys.version_info >= (2, 6):
        parser = ConfigParser.SafeConfigParser(dict_type=OrderedDict)
    else:
        parser = ConfigParser.SafeConfigParser()
    parser.read(filepath)
    config = []
    for title in parser.sections():
        try:
            config.append((parser.get(title, 'site'), title,
                           parser.get(title, 'dir'),
                           parser.getboolean(title, 'new')))
        except Exception, msg:
            raise MangaException('Config Error: %s' % msg)
    return config


def main():
    """Decide the right action from the command line"""
    args = cmdparse()
    try:
        if args.file:
            config = configparse(args.file)
            for (site, title, directory, new) in config:
                manga = SITE_NAMES[site](title, directory)
                manga.get(new=new)
        else:
            manga = SITE_NAMES[args.site](args.title, args.dir, args.limit)
            manga.get(chapter=args.chapter, begin=args.begin,
                      end=args.end, new=args.new)
    except MangaException, msg:
        sys.exit(msg)
    except KeyboardInterrupt:
        sys.exit('Cancelling download... quit')


if __name__ == '__main__':
    main()
