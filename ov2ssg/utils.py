"""Utility functions for OV2SSG converter."""

import datetime
import hashlib
import html.parser
import itertools
import os
import re
import sys
import time
from pathlib import Path
from typing import Generator, List, Optional, Tuple, Union

from slugify import slugify

from .add_spaces import add_spaces_to_content


def calc_file_md5(file_path: Path) -> str:
    """Calculate MD5 hash of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        MD5 hash as hexadecimal string
    """
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def get_file_creation_time(file_path: Path) -> str:
    """Get file creation time.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Formatted creation time string
    """
    if sys.platform.startswith("win"):
        timestamp = os.path.getctime(file_path)
    else:
        timestamp = os.stat(file_path).st_birthtime
    return format_time(timestamp, format_template="%Y-%m-%d", show_utc=False)


def get_file_modification_time(file_path: Path) -> str:
    """Get file modification time.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Formatted modification time string
    """
    timestamp = os.path.getmtime(file_path)
    return format_time(timestamp, format_template="%Y-%m-%d", show_utc=False)


def format_time(
    timestamp: Union[float, int, datetime.datetime, datetime.date, time.struct_time],
    utc_offset_hour: Optional[int] = None,
    format_template: str = "%Y-%m-%dT%H:%M:%S.%fZ",
    show_utc: bool = True,
) -> str:
    """Format timestamp to string.
    
    Args:
        timestamp: Time value to format
        utc_offset_hour: UTC offset in hours
        format_template: strftime format template
        show_utc: Whether to show UTC offset in output
        
    Returns:
        Formatted time string
        
    Raises:
        ValueError: If timestamp type is not supported
    """
    if utc_offset_hour is None:
        utc_offset_hour = 0
    else:
        utc_offset_hour = int(utc_offset_hour)

    # Convert to datetime object
    if isinstance(timestamp, (float, int)):
        adjusted_timestamp = timestamp + utc_offset_hour * 3600
        dt = datetime.datetime.fromtimestamp(adjusted_timestamp)
    elif isinstance(timestamp, (datetime.datetime, datetime.date)):
        dt = timestamp + datetime.timedelta(hours=utc_offset_hour)
    elif isinstance(timestamp, time.struct_time):
        dt = datetime.datetime(*timestamp[:6])
        dt = dt + datetime.timedelta(hours=utc_offset_hour)
    else:
        raise ValueError(f"Unsupported timestamp type: {type(timestamp)}")

    # Format the datetime
    formatted = dt.strftime(format_template)

    # Add UTC offset if requested
    if show_utc:
        if utc_offset_hour >= 0:
            formatted += f" UTC+{utc_offset_hour}"
        else:
            formatted += f" UTC{utc_offset_hour}"

    return formatted


def slugify_path(path_str: str) -> str:
    """Convert path string to slug format with space handling.
    
    Args:
        path_str: Path string to slugify
        
    Returns:
        Slugified path string
    """
    path_parts = path_str.split(os.sep)
    slugified_parts = [
        slugify(add_spaces_to_content(part)) 
        for part in path_parts 
        if part
    ]
    return os.sep.join(slugified_parts)


def yield_subfolders(
    dir_path: Path, 
    recursive: bool = True, 
    excludes: Optional[List[str]] = None
) -> Generator[Path, None, None]:
    """Yield subfolders from a directory.
    
    Args:
        dir_path: Directory path to scan
        recursive: Whether to scan recursively
        excludes: List of regex patterns to exclude
        
    Yields:
        Path objects for each subfolder
    """
    if excludes is None:
        excludes = []
        
    for entry in os.scandir(dir_path):
        if not entry.is_dir():
            continue

        # Check if folder should be excluded
        if _should_exclude_path(entry.name, excludes):
            continue

        # Yield current folder
        folder_path = Path(entry.path)
        yield folder_path
        
        # Recursively yield subfolders
        if recursive:
            yield from yield_subfolders(folder_path, recursive, excludes)


def yield_files(
    dir_path: Path,
    extensions: Optional[List[str]] = None,
    recursive: bool = True,
    excludes: Optional[List[str]] = None,
) -> Generator[Path, None, None]:
    """Yield files from a directory.
    
    Args:
        dir_path: Directory path to scan
        extensions: List of file extensions to include (e.g., ['.md', '.txt'])
        recursive: Whether to scan recursively
        excludes: List of regex patterns to exclude
        
    Yields:
        Path objects for each matching file
    """
    if excludes is None:
        excludes = []
        
    for entry in os.scandir(dir_path):
        # Check if item should be excluded
        if _should_exclude_path(entry.name, excludes):
            continue

        if entry.is_file():
            file_path = Path(entry.path)
            
            # Check file extension
            if extensions is None or file_path.suffix.lower() in extensions:
                yield file_path
                
        elif entry.is_dir() and recursive:
            # Recursively scan subdirectories
            yield from yield_files(
                Path(entry.path), 
                extensions, 
                recursive, 
                excludes
            )


def _should_exclude_path(name: str, exclude_patterns: List[str]) -> bool:
    """Check if a path should be excluded based on patterns.
    
    Args:
        name: Path name to check
        exclude_patterns: List of regex patterns
        
    Returns:
        True if path should be excluded
    """
    return any(re.search(pattern, name) for pattern in exclude_patterns)


class LinkParser(html.parser.HTMLParser):
    """HTML parser for extracting links."""

    def __init__(self) -> None:
        """Initialize parser."""
        super().__init__()
        self.reset()

    def reset(self) -> None:
        """Reset parser state."""
        super().reset()
        self.links = iter([])
        self.in_link = False
        self.cur_link_text = ""
        self.cur_link_href = ""

    def handle_data(self, data: str) -> None:
        """Handle text data within HTML tags.
        
        Args:
            data: Text data
        """
        if self.in_link:
            self.cur_link_text = data

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        """Handle opening HTML tags.
        
        Args:
            tag: Tag name
            attrs: Tag attributes
        """
        if tag == "a":
            self.in_link = True
            for name, value in attrs:
                if name == "href" and value:
                    self.cur_link_href = value

    def handle_endtag(self, tag: str) -> None:
        """Handle closing HTML tags.
        
        Args:
            tag: Tag name
        """
        if tag == "a":
            self.in_link = False
            self.links = itertools.chain(
                self.links, 
                [(self.cur_link_text, self.cur_link_href)]
            )


class ImgSrcParser(html.parser.HTMLParser):
    """HTML parser for extracting image sources."""

    def __init__(self) -> None:
        """Initialize parser."""
        super().__init__()
        self.reset()

    def reset(self) -> None:
        """Reset parser state."""
        super().reset()
        self.imgs = iter([])

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        """Handle opening HTML tags.
        
        Args:
            tag: Tag name  
            attrs: Tag attributes
        """
        if tag == "img":
            for name, value in attrs:
                if name == "src" and value:
                    self.imgs = itertools.chain(self.imgs, [value])
