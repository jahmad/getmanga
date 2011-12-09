#getmanga
**Yet another (multi-site) manga downloader.**

getmanga is a program to download manga from an online manga reader
and save it to a .cbz format.

Currently supported sites:

* manga.animea.net
* mangable.com
* mangafox.com
* mangareader.net
* mangastream.com

##Usage:
* Download all manga chapters available:

  `getmanga.py -s {site} -t {title}`

  example: `getmanga.py -s mangable -t 'fairy tail'`

* Download the last chapter of a title:

  `getmanga.py -s {site} -t {title} -n`

  example: `getmanga.py -s mangastream -t one_piece -n`

* Download specific chapter(s) of a title:

  `getmanga.py -s {site} -t {title} -c {chapter}`

   example:

   * `getmanga.py -s mangareader -t bleach -c 300`: download only chapter 300

   * `getmanga.py -s mangareader -t bleach -c 300-310`: download chapters
     from 300 until 310

   * `getmanga.py -s mangareader -t bleach -c 300-`: download chapters from
     300 until the end

**Optional arguments:**

* -d/--dir: to save downloaded chapter to another directory.
* -l/--limit: set concurrent connection limit, default 4 connections.
* -f/--file: load config file instead of using command arguments.
  (example file included)

  *Note: only support downloading all or new chapter with this mode.*

##Known Issues:
* Currently doesn't support downloading a single chapter with dot
  in it (normally side stories).

##Credits:
* yudha-gunslinger for [progressbar](http://gunslingerc0de.wordpress.com/2010/08/13/python-command-line-progress-bar/)

##License:

The MIT License:
Copyright (c) 2010 Jamaludin Ahmad <j.ahmad at gmx.net>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
