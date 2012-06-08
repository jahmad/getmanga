# -*- coding: utf8 -*-
# Copyright (c) 2010-2012, Jamaludin Ahmad
# Released subject to the MIT License.
# Please see http://en.wikipedia.org/wiki/MIT_License

from __future__ import division

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
    from lxml import html
except ImportError:
    sys.exit('You need to have "lxml" library installed '
             'to run this script')


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

    def get(self, chapter):
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
                thread = threading.Thread(target=self._get_image,
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

    def _get_image(self, semaphore, queue, page):
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
    descending_list = True

    _chapters_css = None
    _pages_css = None
    _image_css = None

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
        doc = html.fromstring(content)
        _chapters = doc.cssselect(self._chapters_css)
        if self.descending_list:
            _chapters = reversed(_chapters)

        chapters = []
        for _chapter in _chapters:
            location = _chapter.get('href')
            if self._is_valid_location(location):
                number = self._get_chapter_number(_chapter)
                name = self._get_chapter_name(number, location)
                uri = self._get_chapter_uri(location)
                chapters.append(Chapter(number, name, uri))
        return chapters

    def get_pages(self, chapter_uri):
        content = urlopen(chapter_uri)
        doc = html.fromstring(content)
        _pages = doc.cssselect(self._pages_css)
        pages = []
        for _page in _pages:
            page = _page.text
            if any(['Prev' in page, 'Next' in page, 'Comments' in page]):
                continue
            name = 'page' + page.zfill(3) if page.isdigit() else page
            uri = self._get_page_uri(chapter_uri, page)
            pages.append(Page(name, uri))
        return pages

    def get_image_uri(self, page_uri):
        content = urlopen(page_uri)
        doc = html.fromstring(content)
        return doc.cssselect(self._image_css)[0].get('src')

    @staticmethod
    def _get_chapter_number(chapter):
        return chapter.text.split(' ')[-1]

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


class MangaFox(MangaSite):
    """class for mangafox site"""
    site_uri = "http://mangafox.me"

    _chapters_css = "a.tips"
    _pages_css = "#top_bar option"
    _image_css = "img#image"

    @property
    def title_uri(self):
        """Returns the index page's url of manga title"""
        return "{0}/manga/{1}/".format(self.site_uri, self.title)

    @staticmethod
    def _get_chapter_number(chapter):
        num = chapter.get('href').split('/')[-2].lstrip('c').lstrip('0')
        return num if num else 0

    @staticmethod
    def _get_chapter_uri(location):
        return location

    @staticmethod
    def _get_page_uri(chapter_uri, page_number):
        """Returns manga image page url"""
        return re.sub(r'[0-9]+.html$', "{0}.html".format(page_number),
                      chapter_uri)


class MangaStream(MangaSite):
    """class for mangastream site"""
    site_uri = "http://mangastream.com"

    _chapters_css = "td a"
    _pages_css = "div#controls a"
    _image_css = "img#p"

    @property
    def title_uri(self):
        return "{0}/manga/".format(self.site_uri)

    @staticmethod
    def _get_chapter_number(chapter):
        return chapter.text.split(' - ')[0]

    def _is_valid_location(self, location):
        return "/{0}/".format(self.title) in location

    @staticmethod
    def _get_page_uri(chapter_uri, page_number):
        return re.sub('[0-9]+$', page_number, chapter_uri)


class MangaBle(MangaSite):
    """class for mangable site"""
    site_uri = "http://mangable.com"

    _chapters_css = "div#newlist ul li a"
    _pages_css = "div#select_page select option"
    _image_css = "#image"

    @property
    def title(self):
        """Returns the right manga title from user input"""
        return re.sub(r'[^\-_a-z0-9]+', '',
                      re.sub(r'\s', '_', self.input_title.lower()))

    @staticmethod
    def _get_chapter_number(chapter):
        return chapter.get('href').split('/')[-2].split('-')[-1]

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


class MangaAnimea(MangaSite):
    """class for manga animea site"""
    site_uri = "http://manga.animea.net"

    _chapters_css = "ul.chapters_list li a"
    _pages_css = "div.topborder select.pageselect option"
    _image_css = "img.mangaimg"

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
    descending_list = False

    _chapters_css = "#chapterlist td a"
    _pages_css = "div#selectpage option"
    _image_css = "img#img"

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

    @staticmethod
    def _get_page_uri(chapter_uri, page_number='1'):
        """Returns manga image page url"""
        if chapter_uri.endswith('.html'):
            page = re.sub(r'\-[0-9]+/', "-{0}/".format(page_number),
                          chapter_uri)
            return "{0}{1}".format(chapter_uri, page)
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
