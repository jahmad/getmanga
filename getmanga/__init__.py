# -*- coding: utf8 -*-
# Copyright (c) 2010-2015, Jamaludin Ahmad
# Released subject to the MIT License.
# Please see http://en.wikipedia.org/wiki/MIT_License

from __future__ import division

import os
import re
import sys

if sys.version_info >= (3, 0, 0):
    from io import BytesIO
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen
    from queue import Queue
else:
    from cStringIO import StringIO as BytesIO
    from urllib2 import HTTPError, Request, urlopen
    from Queue import Queue

from collections import namedtuple
from gzip import GzipFile
from threading import Semaphore, Thread
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import html


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
        """Show a list of available chapters"""
        return self.manga.chapters

    @property
    def latest(self):
        """Show last available chapter"""
        return self.manga.chapters[-1]

    def get(self, chapter):
        """Downloads manga chapter as cbz archive"""
        path = os.path.expanduser(self.path)
        if not os.path.isdir(path):
            try:
                os.makedirs(path)
            except OSError as msg:
                raise MangaException(msg)

        cbz_name = chapter.name + os.path.extsep + 'cbz'
        cbz_file = os.path.join(path, cbz_name)

        if os.path.isfile(cbz_file):
            sys.stdout.write("file {0} exist, skipped download\n".format(cbz_name))
            return

        cbz_tmp = '{0}.tmp'.format(cbz_file)

        try:
            cbz = ZipFile(cbz_tmp, mode='w', compression=ZIP_DEFLATED)
        except IOError as msg:
            raise MangaException(msg)

        sys.stdout.write("downloading {0} {1}:\n".format(self.title, chapter.number))

        pages = self.manga.get_pages(chapter.uri)
        progress(0, len(pages))

        threads = []
        semaphore = Semaphore(self.concurrency)
        queue = Queue()
        for page in pages:
            thread = Thread(target=self._get_image, args=(semaphore, queue, page))
            thread.daemon = True
            thread.start()
            threads.append(thread)

        try:
            for thread in threads:
                thread.join()
                name, image = queue.get()
                if name:
                    cbz.writestr(name, image)
                    progress(len(cbz.filelist), len(pages))
                else:
                    raise MangaException(image)
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
            image = uriopen(uri)
        except MangaException as msg:
            queue.put((None, msg))
        else:
            queue.put((name, image))
        finally:
            semaphore.release()


class MangaSite(object):
    site_uri = None
    # all but mangareader uses descending chapter list
    descending_list = True

    _chapters_css = None
    _pages_css = None
    _image_css = None

    def __init__(self, title):
        # all sites only use lowercase title on their urls.
        self.input_title = title.lower()

    @property
    def title(self):
        """Returns the right manga title from user input"""
        # combination of alphanumeric and underscore only is the most used format.
        # used by: mangafox, mangastream, mangahere, mangatown
        return re.sub(r'[^a-z0-9]+', '_', re.sub(r'^[^a-z0-9]+|[^a-z0-9]+$', '', self.input_title))

    @property
    def title_uri(self):
        """Returns the index page's url of manga title"""
        # this is the most common url for manga title
        # used by: mangafox, mangastream, mangahere, mangatown
        return "{0}/manga/{1}/".format(self.site_uri, self.title)

    @property
    def chapters(self):
        """Returns available chapters"""
        content = uriopen(self.title_uri).decode('utf-8')
        doc = html.fromstring(content)
        _chapters = doc.cssselect(self._chapters_css)
        if self.descending_list:
            _chapters = reversed(_chapters)

        chapters = []
        for _chapter in _chapters:
            number = self._get_chapter_number(_chapter)
            location = _chapter.get('href')
            name = self._get_chapter_name(str(number), location)
            uri = self._get_chapter_uri(location)
            chapters.append(Chapter(number, name, uri))

        if chapters:
            return chapters
        else:
            raise MangaException("There is no chapter available.")

    def get_pages(self, chapter_uri):
        """Returns a list of available pages of a chapter"""
        content = uriopen(chapter_uri).decode('utf-8')
        doc = html.fromstring(content)
        _pages = doc.cssselect(self._pages_css)
        pages = []
        for _page in _pages:
            page = self._get_page_number(_page.text)
            if not page:
                continue
            uri = self._get_page_uri(chapter_uri, page)
            pages.append(Page(page, uri))
        return pages

    def get_image_uri(self, page_uri):
        """Returns uri of image from a chapter page"""
        content = uriopen(page_uri).decode('utf-8')
        doc = html.fromstring(content)
        image_uri = doc.cssselect(self._image_css)[0].get('src')
        # workaround for mangahere which have trailing query on it's image url.
        query = image_uri.find('?')
        if query != -1:
            return image_uri[:query]
        return image_uri

    @staticmethod
    def _get_chapter_number(chapter):
        """Returns chapter's number"""
        # different for each sites
        # the simplest one is getting the last word from a href section.
        # used by: animea, mangareader, mangatown
        return chapter.text.strip().split(' ')[-1]

    def _get_chapter_name(self, number, location):
        """Returns the appropriate name for the chapter for achive name"""
        # title_vXXcXX.cbz if volume number is available, or else just use title_cXX.cbz.
        try:
            volume = re.search(r'v[0-9]+', location).group()
        except AttributeError:
            name = "{0}_c{1}".format(self.title, number.zfill(3))
        else:
            name = "{0}_{1}c{2}".format(self.title, volume, number.zfill(3))
        return name

    @staticmethod
    def _get_chapter_uri(location):
        """Returns uri of chapter's first page from location"""
        # needed because mangareader & animea use relative urls as location on their chapter list,
        # and the other sites uses absolute one.
        return location

    @staticmethod
    def _get_page_uri(chapter_uri, page_number):
        """Returns manga image page url"""
        # every sites use different format for their urls, this is a sample.
        # used by: mangahere, mangatown
        return "{0}{1}.html".format(chapter_uri, page_number)

    @staticmethod
    def _get_page_number(page_text):
        """Returns page number"""
        # normally page listing from each chapter only has numbers in it, but..
        # - mangafox has comment section
        # - mangastream's cssselect return false positive
        return page_text


class MangaFox(MangaSite):
    """class for mangafox site"""
    site_uri = "http://mangafox.me"

    _chapters_css = "a.tips"
    _pages_css = "#top_bar option"
    _image_css = "img#image"

    @staticmethod
    def _get_chapter_number(chapter):
        """Returns chapter's number"""
        num = chapter.get('href').split('/')[-2].lstrip('c').lstrip('0')
        return num if num else 0

    @staticmethod
    def _get_page_number(page_text):
        """Returns page number"""
        # mangafox has comments section in it's page listing
        if page_text == 'Comments':
            return None
        return page_text

    @staticmethod
    def _get_page_uri(chapter_uri, page_number):
        """Returns manga image page url"""
        return re.sub(r'[0-9]+.html$', "{0}.html".format(page_number), chapter_uri)


class MangaStream(MangaSite):
    """class for mangastream site"""
    site_uri = "http://mangastream.com"

    _chapters_css = "td a"
    _pages_css = "div.btn-group ul.dropdown-menu li a"
    _image_css = "img#manga-page"

    @staticmethod
    def _get_chapter_number(chapter):
        """Returns chapter's number"""
        return chapter.text.split(' - ')[0]

    @staticmethod
    def _get_page_number(page_text):
        """Returns page number"""
        # page list is not the only dropdown menu on the page, so there are a few false positives.
        if not page_text or page_text == 'Full List':
            return None
        return re.search('[0-9]+', page_text).group(0)

    @staticmethod
    def _get_page_uri(chapter_uri, page_number):
        """Returns manga image page url"""
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
        return re.sub(r'[^\-_a-z0-9]+', '', re.sub(r'\s', '_', self.input_title))

    @property
    def title_uri(self):
        """Returns the index page's url of manga title"""
        return "{0}/{1}/".format(self.site_uri, self.title)

    @staticmethod
    def _get_chapter_number(chapter):
        """Returns chapter's number"""
        return chapter.get('href').split('/')[-2].split('-')[-1]

    @staticmethod
    def _get_page_uri(chapter_uri, page_number=None):
        """Returns manga image page url"""
        if page_number:
            return "{0}{1}".format(chapter_uri, page_number)
        else:
            return chapter_uri


class MangaHere(MangaSite):
    """class for mangahere site"""
    site_uri = "http://www.mangahere.com"

    _chapters_css = "div.detail_list ul li a"
    _pages_css = "section.readpage_top div.go_page select option"
    _image_css = "img#image"

    @staticmethod
    def _get_chapter_number(chapter):
        """Returns chapter's number"""
        num = chapter.get('href').split('/')[-2].lstrip('c').lstrip('0')
        return num if num else 0


class MangaAnimea(MangaSite):
    """class for manga animea site"""
    site_uri = "http://manga.animea.net"

    _chapters_css = "ul.chapterlistfull li a"
    _pages_css = "div.float-left select.pageselect option"
    _image_css = "img#scanmr"

    @property
    def title(self):
        """Returns the right manga title from user input"""
        return re.sub(r'[^a-z0-9_]+', '-', self.input_title)

    @property
    def title_uri(self):
        """Returns the index page's url of manga title"""
        return "{0}/{1}.html?skip=1".format(self.site_uri, self.title)

    def _get_chapter_uri(self, location):
        """Returns uri of chapter's first page"""
        return "{0}{1}".format(self.site_uri, location)

    @staticmethod
    def _get_page_uri(chapter_uri, page_number=1):
        """Returns manga image page url"""
        return re.sub(r'.html$', '-page-{0}.html'.format(page_number), chapter_uri)


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
        return re.sub(r'[^\-a-z0-9]', '', re.sub(r'[ _]', '-', self.input_title))

    @property
    def title_uri(self):
        """Returns the index page's url of manga title"""
        try:
            content = uriopen("{0}/alphabetical".format(self.site_uri)).decode('utf-8')
            page = re.findall(r'[0-9]+/' + self.title + '.html', content)[0]
            uri = "{0}/{1}".format(self.site_uri, page)
        except IndexError:
            uri = "{0}/{1}".format(self.site_uri, self.title)
        return uri

    def _get_chapter_uri(self, location):
        """Returns uri of chapter's first page"""
        return "{0}{1}".format(self.site_uri, location)

    @staticmethod
    def _get_page_uri(chapter_uri, page_number='1'):
        """Returns manga image page url"""
        if chapter_uri.endswith('.html'):
            page = re.sub(r'\-[0-9]+/', "-{0}/".format(page_number), chapter_uri)
            return "{0}{1}".format(chapter_uri, page)
        else:
            return "{0}/{1}".format(chapter_uri, page_number)


class MangaTown(MangaSite):
    """class for mangatown site"""
    site_uri = "http://www.mangatown.com"

    _chapters_css = "div.chapter_content ul.chapter_list li a"
    _pages_css = "div.page_select select option"
    _image_css = "img#image"


SITES = dict(animea=MangaAnimea,
             mangable=MangaBle,
             mangafox=MangaFox,
             mangahere=MangaHere,
             mangareader=MangaReader,
             mangatown=MangaTown)


def uriopen(url):
    """Returns data available (html or image file) from a url"""
    request = Request(url)
    request.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_1) '
                       'AppleWebKit/537.73.11 (KHTML, like Gecko) Version/7.0.1 Safari/537.73.11')
    request.add_header('Accept-encoding', 'gzip')

    data = None
    retry = 0
    while retry < 5:
        try:
            response = urlopen(request, timeout=15)
            data = response.read()
        except HTTPError as msg:
            raise MangaException("HTTP Error: {0} - {1}\n".format(msg.code, url))
        except Exception:
            # what may goes here: urllib2.URLError, socket.timeout,
            #                    httplib.BadStatusLine
            retry += 1
        else:
            if 'content-length' in response.headers.keys():
                if len(data) == int(response.headers.getheader('content-length')):
                    retry = 5
                else:
                    data = None
                    retry += 1
            else:
                retry = 5
            if ('Content-Encoding', 'gzip') in response.headers.items():
                compressed = BytesIO(data)
                data = GzipFile(fileobj=compressed).read()
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
