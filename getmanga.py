#!/usr/bin/env python
# -*- coding: utf8 -*-
"""Yet another (multi-site) manga downloader"""

# Copyright (c) 2010, Jamaludin Ahmad
# Released subject to the MIT License.
# Please see http://en.wikipedia.org/wiki/MIT_License

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
    from collections import namedtuple
except ImportError:
    sys.exit("You need at least python 2.6 to run this sript")

try:
    import argparse
except ImportError:
    sys.exit('You need to have "argparse" module installed '
             'to run this script')

__version__ = '0.4'


Chapter = namedtuple('Chapter', 'number name uri')
Page = namedtuple('Page', 'name uri')


class MangaException(Exception):
    """Exception class for manga"""
    pass


class GetManga(object):
    def __init__(self, site, title):
        self.concurrency = 4
        self.path = '.'

        self.title = title
        self.manga = SITES[site](title)

    @property
    def chapters(self):
        return self.manga.chapters

    @property
    def latest(self):
        return self.manga.chapters[-1]

    def download(self, chapter):
        path = os.path.expanduser(self.path)
        if not os.path.isdir(path):
            try:
                os.makedirs(path)
            except OSError as msg:
                raise MangaException(msg)

        cbz_name = chapter.name + os.path.extsep + 'cbz'
        cbz_file = os.path.join(path, cbz_name)

        if os.path.isfile(cbz_file):
            sys.stdout.write("file {0} exist, skipped download\n".
                                        format(cbz_name))
        else:
            cbz_tmp = '{0}.tmp'.format(cbz_file)
            pages = self.manga.get_pages(chapter.uri)

            try:
                cbz = zipfile.ZipFile(cbz_tmp, mode='w',
                                      compression=zipfile.ZIP_DEFLATED)
            except IOError as msg:
                raise MangaException(msg)

            sys.stdout.write("downloading {0} {1}:\n".
                                        format(self.title, chapter.number))
            progress(0, len(pages))

            threads = []
            semaphore = threading.Semaphore(self.concurrency)
            queue = Queue.Queue()
            for page in pages:
                thread = threading.Thread(target=self._pagedownload,
                                          args=(semaphore, queue, page))
                thread.daemon = True
                thread.start()
                threads.append(thread)

            try:
                for thread in threads:
                    thread.join()
                    image = queue.get()
                    if image[0]:
                        cbz.writestr(image[0], image[1])
                        progress(len(cbz.filelist), len(pages))
                    else:
                        raise MangaException(image[1])
            except Exception as msg:
                cbz.close()
                os.remove(cbz_tmp)
                raise MangaException(msg)
            else:
                cbz.close()
                os.rename(cbz_tmp, cbz_file)

    def _pagedownload(self, semaphore, queue, page):
        """Downloads page images inside a thread"""
        try:
            semaphore.acquire()
            uri = self.manga.get_image_uri(page.uri)
            name = page.name + os.path.extsep + uri.split('.')[-1]
            image = urlopen(uri)
        except MangaException as msg:
            queue.put((None, msg))
        else:
            queue.put((name, image))
        finally:
            semaphore.release()


class MangaSite(object):
    site_uri = None

    _chapters_re = None
    _pages_re = None
    _image_re = None

    def __init__(self, title):
        self.input_title = title

    @property
    def title(self):
        """Return the right manga title from user input"""
        title = self.input_title.lower()
        return re.sub(r'[^a-z0-9]+', '_',
                      re.sub(r'^[^a-z0-9]+|[^a-z0-9]+$', '', title))

    @property
    def title_uri(self):
        """Returns the index page's url of manga title"""
        return "{0}/{1}/".format(self.site_uri, self.title)

    @property
    def chapters(self):
        content = urlopen(self.title_uri)
        _chapters = self._chapters_re.findall(content)
        _chapters = sorted(set(_chapters), key=lambda x: float(x[1]))

        chapters = []
        for (location, number) in _chapters:
            if self._is_valid_location(location):
                name = self._get_chapter_name(number, location)
                uri = self._get_chapter_uri(location)
                chapters.append(Chapter(number, name, uri))
        return chapters

    def get_pages(self, chapter_uri):
        content = urlopen(chapter_uri)
        _pages = self._pages_re.findall(content)
        _pages = self._get_valid_pages(_pages)
        pages = []
        for _page in _pages:
            name = 'page' + _page.zfill(3) if _page.isdigit() else _page
            uri = self._get_page_uri(chapter_uri, _page)
            pages.append(Page(name, uri))
        return pages

    def get_image_uri(self, page_uri):
        content = urlopen(page_uri)
        uri = self._image_re.findall(content)[0]
        return uri

    def _get_chapter_name(self, number, location):
        """Returns the appropriate name for the chapter"""
        try:
            volume = re.search(r'v[0-9]+', location).group()
        except AttributeError:
            name = "{0}_c{1}".format(self.title, number)
        else:
            name = "{0}_{1}c{2}".format(self.title, volume, number)
        return name

    def _get_chapter_uri(self, location):
        return "{0}{1}".format(self.site_uri, location)

    @staticmethod
    def _get_page_uri(chapter_uri, page_number):
        return "{0}/{1}".format(chapter_uri, page_number)

    @staticmethod
    def _is_valid_location(location):
        return True

    @staticmethod
    def _get_valid_pages(pages):
        return sorted(list(set(pages)), key=int)


class MangaFox(MangaSite):
    """class for mangafox site"""
    site_uri = "http://www.mangafox.com"

    _chapters_re = re.compile(r'</a>[ \r\n]*<a href="([^ ]+)" class='
                              r'"ch" title="[^"]+">.* ([\.0-9]+)</a>')
    _pages_re = re.compile(r'option value="[0-9]+" .*?>([0-9]+)</option')
    _image_re = re.compile(r'img src="([^ ]+)" onerror="')

    @property
    def title_uri(self):
        """Returns the index page's url of manga title"""
        return "{0}/manga/{1}/?no_warning=1".\
                            format(self.site_uri, self.title)

    @staticmethod
    def _get_page_uri(chapter_uri, page_number):
        """Returns manga image page url"""
        return re.sub(r'[0-9]+.html$', "{0}.html".format(page_number),
                      chapter_uri)


class MangaStream(MangaSite):
    """class for mangastream site"""
    site_uri = "http://mangastream.com"

    _chapters_re = re.compile(r'href="(/read/[^ ]+)">.*?([0-9]+)')
    _pages_re = re.compile(r'<a href="[^ ]+".*?>([0-9]{1,2})</a>')
    _image_re = re.compile(r'src="([^ ]+)" border="0"')

    @property
    def title_uri(self):
        return "{0}/manga/".format(self.site_uri)

    def _is_valid_location(self, location):
        return "/{0}/".format(self.title) in location

    @staticmethod
    def _get_page_uri(chapter_uri, page_number):
        return re.sub('[0-9]+$', page_number, chapter_uri)


class MangaBle(MangaSite):
    """class for mangable site"""
    site_uri = "http://mangable.com"

    _chapters_re = re.compile(r'href="([^ ]+)" class=".*>[\n\t]*<p .*>'
                              r'[\n\t]*<b>.* ([0-9]+)')
    _pages_re = re.compile(r'option value="[0-9]+".*?>([0-9]+)</opt')
    _image_re = re.compile(r'<img src="([^ ]+)" id="image"')

    @property
    def title(self):
        """Returns the right manga title from user input"""
        return re.sub(r'[^\-_a-z0-9]+', '',
                      re.sub(r'\s', '_', self.input_title.lower()))

    @staticmethod
    def _get_chapter_uri(location):
        return location

    @staticmethod
    def _get_page_uri(chapter_uri, page_number=None):
        """Returns manga image page url"""
        if page_number:
            return "{0}{1}".format(chapter_uri, page_number)
        else:
            return chapter_uri

    @staticmethod
    def _get_valid_pages(pages):
        not_pages, valid_pages = [], []
        for page in pages:
            if page in not_pages:
                valid_pages.append(page)
            else:
                not_pages.append(page)
        return valid_pages


class MangaAnimea(MangaSite):
    """class for manga animea site"""
    site_uri = "http://manga.animea.net"

    _chapters_re = re.compile(r'href="([^ ]+)" id=[^ ]+ title='
                              r'"[^"]+ ([0-9]+)"')
    _pages_re = re.compile(r'<option value="[0-9]+".*?>([0-9]+)</option>')
    _image_re = re.compile(r'<img src="([^ ]+)" onerror')

    @property
    def title(self):
        """Returns the right manga title from user input"""
        return re.sub(r'[^a-z0-9_]+', '-', self.input_title.lower())

    @property
    def title_uri(self):
        """Returns the index page's url of manga title"""
        return "{0}/{1}.html?skip=1".format(self.site_uri, self.title)

    @staticmethod
    def _get_page_uri(chapter_uri, page_number=1):
        """Returns manga image page url"""
        return re.sub(r'.html$', '-page-{0}.html'.format(page_number),
                      chapter_uri)

    def _is_valid_location(self, location):
        """Returns boolean status of a chapter validity"""
        return self.title in location


class MangaReader(MangaSite):
    """class for mangareader site"""
    site_uri = "http://www.mangareader.net"

    _chapters_re = re.compile(r'<a href="([^ ]+)">.+ ([0-9]+)</a>')
    _pages_re = re.compile(r'<option value=.+>\s*([0-9]+)</option>')
    _image_re = re.compile(r'<img id="img" .+ src="([^ ]+)"')

    @property
    def title(self):
        """Returns the right manga title from user input"""
        return re.sub(r'[^\-a-z0-9]', '',
                      re.sub(r'[ _]', '-', self.input_title.lower()))

    @property
    def title_uri(self):
        """Returns the index page's url of manga title"""
        try:
            content = urlopen("{0}/alphabetical".format(self.site_uri))
            page = re.findall(r'[0-9]+/' + self.title + '.html', content)[0]
            uri = "{0}/{1}".format(self.site_uri, page)
        except IndexError:
            uri = "{0}/{1}".format(self.site_uri, self.title)
        return uri

    def _get_page_uri(self, chapter_uri, page_number='1'):
        """Returns manga image page url"""
        if chapter_uri.endswith('.html'):
            page = re.sub(r'\-[0-9]+/', "-{0}/".format(page_number),
                          chapter_uri)
            return "{0}{1}".format(self.site_uri, page)
        else:
            return "{0}/{1}".format(chapter_uri, page_number)


SITES = dict(animea=MangaAnimea,
             mangable=MangaBle,
             mangafox=MangaFox,
             mangareader=MangaReader,
             mangastream=MangaStream)


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
        except urllib2.HTTPError as msg:
            raise MangaException("HTTP Error: {0} - {1}\n".
                                                format(msg.code, url))
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
        raise MangaException("Failed to retrieve {0}".format(url))


def progress(page, total):
    """Display progress bar"""
    try:
        page, total = int(page), int(total)
        marks = int(round(50 * (page / total)))
        spaces = int(round(50 - marks))
    except Exception:
        raise MangaException('Unknown error')

    loader = '[' + ('#' * int(marks)) + ('-' * int(spaces)) + ']'

    sys.stdout.write('%s page %d of %d\r' % (loader, page, total))
    if page == total:
        sys.stdout.write('\n')
    sys.stdout.flush()


def cmdparse():
    """Returns parsed arguments from command line"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', type=str,
                        help='%(prog)s config file')
    parser.add_argument('-s', '--site', choices=(SITES.keys()),
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
            args.chapter = chapter[0]
        elif len(chapter) == 2:
            args.chapter = None
            args.begin = chapter[0]
            args.end = chapter[1] if chapter[1] else None
        if args.end and (args.begin > args.end):
            parser.print_usage()
            sys.exit('%s: error: invalid chapter interval, the end '
                     'should be bigger than start' % parser.prog)
    return args


def configparse(filepath):
    """Returns parsed config from an ini file"""
    parser = ConfigParser.SafeConfigParser()
    parser.read(filepath)
    config = []
    for title in parser.sections():
        try:
            config.append((parser.get(title, 'site'), title,
                           parser.get(title, 'dir'),
                           parser.getboolean(title, 'new')))
        except Exception as msg:
            raise MangaException('Config Error: %s' % msg)
    return config


if __name__ == '__main__':
    args = cmdparse()

    if args.file:
        try:
            config = configparse(args.file)
            for (site, title, path, new) in config:
                manga = GetManga(site, title)
                manga.path = path
                manga.download(manga.latest)
        except MangaException as msg:
            sys.exit(msg)

    else:
        manga = GetManga(args.site, args.title)
        manga.concurrency = args.limit
        manga.path = args.dir

        try:
            chapters = manga.chapters
            if args.new:
                manga.download(manga.latest)

            elif args.chapter:
                for chapter in chapters:
                    if chapter.number == args.chapter:
                        manga.download(chapter)
                        break
                else:
                    sys.exit("Chapter doesn't exist")
            elif args.begin:
                start = None
                stop = None
                for index, chapter in enumerate(chapters):
                    if chapter.number == args.begin:
                        start = index
                    if args.end and chapter.number == args.end:
                        stop = index + 1
                for chapter in chapters[start:stop]:
                    manga.download(chapter)
            else:
                for chapter in chapters:
                    manga.download(chapter)

        except MangaException as msg:
            sys.exit(msg)
