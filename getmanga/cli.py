# -*- coding: utf8 -*-
# Copyright (c) 2010-2014, Jamaludin Ahmad
# Released subject to the MIT License.
# Please see http://en.wikipedia.org/wiki/MIT_License

import os
import sys
try:
    import configparser
except ImportError:
    import ConfigParser as configparser

import pkg_resources

try:
    import argparse
except ImportError:
    sys.exit('You need to have "argparse" module installed to run this script')

from getmanga import SITES, MangaException, GetManga


version = pkg_resources.require("GetManga")[0].version


def cmdparse():
    """Returns parsed arguments from command line"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', type=str, help="%(prog)s config file")
    parser.add_argument('title', type=str, help="manga title to download")
    parser.add_argument('-s', '--site', choices=SITES.keys(), default='mangahere',
                        help="manga site to download from")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', '--all', action='store_true', help="download all chapters available")
    group.add_argument('-c', '--chapter', type=str, help="chapter(s) number to download")
    parser.add_argument('-d', '--dir', type=str, default='.', help='download directory')
    parser.add_argument('-v', '--version', action='version',
                        version='{0} {1}'.format(parser.prog, version),
                        help="show program version and exit")

    args = parser.parse_args()
    args.begin = None
    args.end = None

    if args.file:
        if not os.path.isfile(args.file):
            parser.print_usage()
            sys.exit("{0}: error: config file does not exit".format(parser.prog))
    if args.chapter:
        chapter = args.chapter.split('-')
        if len(chapter) == 2:
            args.chapter = None
            args.begin = chapter[0]
            args.end = chapter[1] if chapter[1] else None
        if args.begin and args.end and (int(args.begin) > int(args.end)):
            parser.print_usage()
            sys.exit("{0}: error: invalid chapter interval, the end "
                     "should be bigger than start".format(parser.prog))
    return args


def configparse(filepath):
    """Returns parsed config from an ini file"""
    parser = configparser.SafeConfigParser()
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
    try:
        manga = GetManga(args.site, args.title)

        if args.file:
            config = configparse(args.file)
            for (site, title, path, new) in config:
                manga = GetManga(site, title)
                manga.path = path
                manga.get(manga.latest)

        if args.all:
            for chapter in manga.chapters:
                manga.get(chapter)

        elif args.chapter:
            # single chapter
            for chapter in manga.chapters:
                if chapter.number == args.chapter:
                    manga.get(chapter)
                    break
            else:
                sys.exit("Chapter doesn't exist.")

        elif args.begin:
            # download range
            start = None
            stop = None
            for index, chapter in enumerate(manga.chapters):
                if chapter.number == args.begin:
                    start = index
                if args.end and chapter.number == args.end:
                    stop = index + 1
            for chapter in manga.chapters[start:stop]:
                manga.get(chapter)

        else:
            # last chapter
            manga.get(manga.latest)

    except MangaException as msg:
        sys.exit(msg)


if __name__ == '__main__':
    main()
