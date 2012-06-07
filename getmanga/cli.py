# -*- coding: utf8 -*-
# Copyright (c) 2010, Jamaludin Ahmad
# Released subject to the MIT License.
# Please see http://en.wikipedia.org/wiki/MIT_License

import ConfigParser
import os
import sys
import pkg_resources

try:
    import argparse
except ImportError:
    sys.exit('You need to have "argparse" module installed '
             'to run this script')

from getmanga import SITES, MangaException, GetManga


version = pkg_resources.require("GetManga")[0].version


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
                        version='%s %s' % (parser.prog, version),
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


def main():
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
