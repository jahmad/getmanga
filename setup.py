#!/usr/bin/env python

from setuptools import setup
import sys


version = '0.5'

if sys.version_info < (2, 6, 0):
    sys.exit("Python 2.6 or newer is required to run this program.")

setup(name='getmanga',
      version=version,
      description='Yet another (multi-site) manga downloader',
      long_description='getmanga is a program to download manga from an online '
                       'manga reader and save it to a .cbz format.',
      classifiers=[],
      keywords='',
      author='Jamaludin Ahmad',
      author_email='j.ahmad@gmx.net',
      url='',
      license='MIT',
      packages=['getmanga'],
      zip_safe=False,
      install_requires=['requests', 'lxml', 'cssselect'],
      entry_points="""
      [console_scripts]
      getmanga = getmanga.cli:main
      """
      )
