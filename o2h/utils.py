import datetime
import html.parser
import itertools
import os
import re
import sys
import time


def get_file_creation_time(file_path):
    if sys.platform.startswith("win"):
        t = os.path.getctime(file_path)
    else:
        t = os.stat(file_path).st_birthtime

    return _format_to_date(t)


def get_file_modification_time(file_path):
    t = os.path.getmtime(file_path)

    return _format_to_date(t)


def _format_to_date(t):
    if isinstance(t, (int, float)):
        t = datetime.datetime.fromtimestamp(t).date()
    elif isinstance(t, datetime.date):
        pass
    elif isinstance(t, datetime.datetime):
        t = t.date()
    else:
        raise TypeError("t must be a int, float, datetime.date or datetime.datetime")

    return t


class LinkParser(html.parser.HTMLParser):
    """
    Usage:
    ```
    parser = LinkParser()
    parser.feed(html)
    # print(next(parser.links))
    for link in parser.links:
        print(link)
    ```
    """

    def reset(self):
        super().reset()
        self.links = iter([])
        self.in_link = False
        self.cur_link_text = ""
        self.cur_link_href = ""

    def handle_data(self, data: str) -> None:
        if not self.in_link:
            return
        self.cur_link_text = data

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return

        self.in_link = True
        for (name, value) in attrs:
            if name == "href":
                self.cur_link_href = value

    def handle_endtag(self, tag: str):
        if tag == "a":
            self.in_link = False
            self.links = itertools.chain(
                self.links, [(self.cur_link_text, self.cur_link_href)]
            )


class ImgSrcParser(html.parser.HTMLParser):
    """ """

    def reset(self):
        super().reset()
        self.imgs = iter([])

    def handle_starttag(self, tag, attrs):
        if tag != "img":
            return

        for (name, value) in attrs:
            if name == "src":
                self.imgs = itertools.chain(self.imgs, [value])


def yield_subfolders(dir_path: str, recursive: bool = True, excludes: list = None):
    """
    Args:
        - dir, directory path.
        - recursive, Default is True, will list files in subfolders.
        - excludes, exclude folder or file name list, regexp pattern string.

    Tips:
        - How to get relative path of a folder: os.path.relpath(subfolder_path, dir_path)
        - How to get absolute path of a folder: os.path.join(dir_path, subfolder_path)
    """
    for f in os.scandir(dir_path):
        if not f.is_dir():
            continue

        if excludes:
            # matching dir name
            is_ignore = False
            for pat in excludes:
                if re.search(pat, f.name):
                    is_ignore = True
                    break
            if is_ignore:
                continue

        if recursive:
            for item in yield_subfolders(f.path, recursive, excludes):
                yield item

        yield f.path


def yield_files(
    dir: str,
    ext: list or str = None,
    recursive: bool = True,
    excludes: list = None,
):
    """
    Args:
        - dir, directory path.
        - ext, file extension list, lowercase letters, such as ".txt". Default is None, which means all files.
        - recursive, Default is True, will list files in subfolders.
        - excludes, exclude folder or file name list, regexp pattern string.

    Tips:
        - How to get relative path of a file: os.path.relpath(file_path, dir_path)
        - How to get only name of a file: os.path.basename(file_path)

    Version:
        v0.2.1 (2023-01-15)
        https://gist.github.com/nodewee/eae12e2b74beb82162b8b488648f1fdd
    """

    if not ext:
        ext = None
    else:
        if not isinstance(ext, list):
            raise TypeError("ext must be a list or None")

    for f in os.scandir(dir):
        if excludes:
            is_ignore = False
            for pat in excludes:
                if re.search(pat, f.name):
                    is_ignore = True
                    break
            if is_ignore:
                continue

        if recursive:
            if f.is_dir():
                for item in yield_files(f.path, ext, recursive, excludes):
                    yield item

        if f.is_file():
            if ext is None:
                yield f.path
            else:
                if os.path.splitext(f.name)[1].lower() in ext:
                    yield f.path
