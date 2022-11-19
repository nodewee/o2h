import datetime
import html.parser
import itertools
import os
import re
import sys
import time


def get_file_creation_time(file_path):
    if sys.platform.startswith("win"):
        return os.path.getctime(file_path)
    else:
        return os.stat(file_path).st_birthtime


def time_to_readable(t, utc_offset_hour: int = None, format_template: str = None):
    """
    VERSION: 0.3.4
    format_temple cheatsheet: https://strftime.org/
    """
    if not format_template:
        format_template = "%Y-%m-%dT%H:%M:%S.%fZ"

    mark_utc = False
    if utc_offset_hour is None:
        utc_offset_hour = 0
    else:
        mark_utc = True
        utc_offset_hour = int(utc_offset_hour)

    readable = None
    if type(t) in [float, int]:  # timestamp
        t += utc_offset_hour * 3600
        dt = datetime.datetime.fromtimestamp(t)
        readable = datetime.datetime.strftime(dt, format_template)
    elif type(t) is datetime.datetime:
        t = t + datetime.timedelta(hours=utc_offset_hour)
        readable = datetime.datetime.strftime(t, format_template)
    elif type(t) is time.struct_time:
        t = datetime.datetime(t[0], t[1], t[2], t[3], t[4], t[5], t[6])
        t = t + datetime.timedelta(hours=utc_offset_hour)
        readable = datetime.datetime.strftime(t, format_template)
    else:
        raise ValueError(f"Unknown type:{type(t)}")

    if not readable:
        return

    if not mark_utc:
        return readable

    if utc_offset_hour >= 0:
        readable += f" UTC+{utc_offset_hour}"
    else:
        readable += f" UTC{utc_offset_hour}"
    return readable


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


def list_subfolders(dir: str, recursive: bool = True):
    """
    Args:
        - dir, directory path.
        - recursive, Default is True, will list files in subfolders.

    Tips:
        - How to get relative path of a folder: os.path.relpath(subfolder_path, dir_path)
    """
    for f in os.scandir(dir):
        if recursive:
            if f.is_dir():
                for item in list_subfolders(f.path, recursive):
                    yield item
                yield f.path


def list_files(dir: str, ext: list = None, recursive: bool = True):
    """
    Args:
        - dir, directory path.
        - ext, file extension list, lowercase letters. Default is None, which means all files.
        - recursive, Default is True, will list files in subfolders.

    Tips:
        - How to get relative path of a file: os.path.relpath(file_path, dir_path)
    """
    for f in os.scandir(dir):
        if recursive:
            if f.is_dir():
                for item in list_files(f.path, ext, recursive):
                    yield item

        if f.is_file():
            if ext is None:
                yield f.path
            else:
                if os.path.splitext(f.name)[1].lower() in ext:
                    yield f.path
