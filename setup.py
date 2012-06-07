#!/usr/bin/env python

from setuptools import setup, find_packages
import sys, os

version = '0.5'

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
      install_requires=['lxml'],
      entry_points="""
      [console_scripts]
      getmanga = getmanga.cli:main
      """
      )
