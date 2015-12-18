# -*- coding: utf8 -*-
# Copyright (c) 2010-2015, Jamaludin Ahmad
# Released subject to the MIT License.
# Please see http://en.wikipedia.org/wiki/MIT_License

from __future__ import division

import os
import re
import sys

if sys.version_info >= (3, 0, 0):
    from queue import Queue
else:
    from Queue import Queue

from collections import namedtuple
from threading import Semaphore, Thread
from zipfile import ZIP_DEFLATED, ZipFile

import requests
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
                if not name:
                    raise MangaException(image)
                cbz.writestr(name, image)
                progress(len(cbz.filelist), len(pages))
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
            image = self.manga.download(uri)
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
        self.input_title = title.strip().lower()
        self.session = requests.Session()

    @property
    def title(self):
        """Returns the right manga title from user input"""
        # combination of alphanumeric and underscore only is the most used format.
        # used by: mangafox, mangastream, mangahere
        return re.sub(r'[^a-z0-9]+', '_', re.sub(r'^[^a-z0-9]+|[^a-z0-9]+$', '', self.input_title))

    @property
    def title_uri(self):
        """Returns the index page's url of manga title"""
        # this is the most common url for manga title
        # used by: mangafox, mangastream, mangahere
        return "{0}/manga/{1}/".format(self.site_uri, self.title)

    @property
    def chapters(self):
        """Returns available chapters"""
        content = self.session.get(self.title_uri).text
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

        if not chapters:
            raise MangaException("There is no chapter available.")
        return chapters

    def get_pages(self, chapter_uri):
        """Returns a list of available pages of a chapter"""
        content = self.session.get(chapter_uri).text
        doc = html.fromstring(content)
        _pages = doc.cssselect(self._pages_css)
        pages = []
        for _page in _pages:
            name = self._get_page_name(_page.text)
            if not name:
                continue
            uri = self._get_page_uri(chapter_uri, name)
            pages.append(Page(name, uri))
        return pages

    def get_image_uri(self, page_uri):
        """Returns uri of image from a chapter page"""
        content = self.session.get(page_uri).text
        doc = html.fromstring(content)
        image_uri = doc.cssselect(self._image_css)[0].get('src')
        # mangahere have trailing query on it's image url, which make downloading it
        # failed, strip it here.
        query = image_uri.find('?')
        if query != -1:
            return image_uri[:query]
        return image_uri

    def download(self, image_uri):
        content = None
        retry = 0
        while retry < 5:
            resp = self.session.get(image_uri)
            if str(resp.status_code).startswith('4'):
                retry = 5
            elif str(resp.status_code).startswith('5'):
                retry += 1
            elif len(resp.content) != int(resp.headers['content-length']):
                retry += 1
            else:
                retry = 5
                content = resp.content
        if not content:
            raise MangaException("Failed to retrieve {0}".format(image_uri))
        return content

    @staticmethod
    def _get_chapter_number(chapter):
        """Returns chapter's number from a chapter's HtmlElement"""
        # the most common one is getting the last word from a href section.
        # used by: animea, mangafox, mangahere, mangareader
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

    def _get_chapter_uri(self, location):
        """Returns absolute url of chapter's page from location"""
        # some sites already use absolute url on their chapter list, some have relative urls.
        if location.startswith('http://'):
            return location
        else:
            return "{0}{1}".format(self.site_uri, location)

    @staticmethod
    def _get_page_name(page_text):
        """Returns page name from text available or None if it's not a valid page"""
        # typical name: page's number, double page (eg. 10-11), or credits
        # normally page listing from each chapter only has it's name in it, but..
        # - mangafox has comment section
        return page_text

    @staticmethod
    def _get_page_uri(chapter_uri, page_name):
        """Returns manga image page url"""
        # every sites use different format for their urls, this is a sample.
        # used by: mangahere
        return "{0}{1}.html".format(chapter_uri, page_name)


class MangaHere(MangaSite):
    """class for mangahere site"""
    site_uri = "http://www.mangahere.co"

    _chapters_css = "div.detail_list ul li a"
    _pages_css = "section.readpage_top div.go_page select option"
    _image_css = "img#image"


class MangaFox(MangaSite):
    """class for mangafox site"""
    # their slogan should be: "we are not the best, but we are the first"
    site_uri = "http://mangafox.me"

    _chapters_css = "a.tips"
    _pages_css = "#top_bar option"
    _image_css = "img#image"

    @staticmethod
    def _get_page_name(page_text):
        """Returns page name from text available"""
        # mangafox has comments section in it's page listing
        if page_text == 'Comments':
            return None
        return page_text

    @staticmethod
    def _get_page_uri(chapter_uri, page_name):
        """Returns manga image page url"""
        # chapter's page already has the first page's name in it.
        return re.sub(r'[0-9]+.html$', "{0}.html".format(page_name), chapter_uri)


class MangaStream(MangaSite):
    """class for mangastream site"""
    # a real scanlation group, not distro sites like the others here,
    # currently doesn't utilize _get_page_name and override get_pages instead.
    site_uri = "http://mangastream.com"

    _chapters_css = "td a"
    _pages_css = "div.btn-group ul.dropdown-menu li a"
    _image_css = "img#manga-page"

    def get_pages(self, chapter_uri):
        """Returns a list of available pages of a chapter"""
        content = self.session.get(chapter_uri).text
        doc = html.fromstring(content)
        _pages = doc.cssselect(self._pages_css)
        for _page in _pages:
            page_text = _page.text
            if not page_text:
                continue
            if 'Last Page' in page_text:
                last_page = re.search('[0-9]+', page_text).group(0)

        pages = []
        for num in range(1, int(last_page) + 1):
            name = str(num)
            uri = self._get_page_uri(chapter_uri, name)
            pages.append(Page(name, uri))
        return pages

    @staticmethod
    def _get_chapter_number(chapter):
        """Returns chapter's number from a chapter's HtmlElement"""
        return chapter.text.split(' - ')[0]

    @staticmethod
    def _get_page_uri(chapter_uri, page_name):
        """Returns manga image page url"""
        return re.sub('[0-9]+$', page_name, chapter_uri)


class MangaAnimea(MangaSite):
    """class for manga animea site"""
    site_uri = "http://manga.animea.net"

    _chapters_css = "ul.chapterlistfull li a"
    _pages_css = "div.float-left select.pageselect option"
    _image_css = "img#scanmr"

    @property
    def title(self):
        """Returns the right manga title from user input"""
        return re.sub(r'[^a-z0-9]+', '-', self.input_title)

    @property
    def title_uri(self):
        """Returns the index page's url of manga title"""
        return "{0}/{1}.html".format(self.site_uri, self.title)

    @staticmethod
    def _get_page_uri(chapter_uri, page_name):
        """Returns manga image page url"""
        return re.sub(r'.html$', '-page-{0}.html'.format(page_name), chapter_uri)


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
        # some title's page is in the root, others hidden in a random numeric subdirectory,
        # so we need to search the manga list to get the correct url.
        try:
            content = self.session.get("{0}/alphabetical".format(self.site_uri)).text
            page = re.findall(r'[0-9]+/' + self.title + '.html', content)[0]
            uri = "{0}/{1}".format(self.site_uri, page)
        except IndexError:
            uri = "{0}/{1}".format(self.site_uri, self.title)
        return uri

    @staticmethod
    def _get_page_uri(chapter_uri, page_name='1'):
        """Returns manga image page url"""
        # older stuff, the one in numeric subdirectory, typically named "chapter-X.html",
        # while the new stuff only use number.
        if chapter_uri.endswith('.html'):
            page = re.sub(r'\-[0-9]+/', "-{0}/".format(page_name), chapter_uri)
            return "{0}{1}".format(chapter_uri, page)
        else:
            return "{0}/{1}".format(chapter_uri, page_name)


SITES = dict(animea=MangaAnimea,
             mangafox=MangaFox,
             mangahere=MangaHere,
             mangareader=MangaReader,
             mangastream=MangaStream)


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
