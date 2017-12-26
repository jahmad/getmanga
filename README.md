#getmanga
**Yet another (multi-site) manga downloader.**

getmanga is a program to download manga from an online manga reader
and save it to a .cbz format.

Currently supported sites:

* manga.animea.net
* mangafox.me
* mangahere.co
* mangareader.net
* mangastream.com
* mangatown.com

##Usage:
* The simplest way:

  `getmanga {title}`

  will download the latest chapter of that title from the default site
  (mangahere.co)

* Or if you want to get from specific site:

  `getmanga {title} -s {site}`

  example: `getmanga 'fairy tail' -s animea`

* Download all chapters of a title:

  `getmanga {title} -s {site} -a`

  example: `getmanga one_piece -s mangastream -n`

* Download specific chapter(s) of a title:

  `getmanga {title} -s {site} -c {chapter}`

   example:

   * `getmanga bleach -s mangareader -c 300`: download only chapter 300

   * `getmanga bleach -s mangareader -c 300-310`: download chapters
     from 300 until 310

   * `getmanga bleach -s mangareader -c 300-`: download chapters from
     300 until the end

**Optional arguments:**

* -d/--dir: to save downloaded chapter to another directory.
* -f/--file: load config file instead of using command arguments.
  (example file included)

  *Note: only support downloading all or new chapter with this mode.*

##Credits:
* yudha-gunslinger for [progressbar](http://gunslingerc0de.wordpress.com/2010/08/13/python-command-line-progress-bar/)

##License:

The MIT License:
Copyright (c) 2010-2017 Jamaludin Ahmad <j.ahmad at gmx.net>

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
