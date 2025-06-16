"""O2H - Convert Obsidian notes to Hugo/Zola posts."""

__version__ = "0.3.7"
__title__ = "O2H"
__author__ = "nodewee@gmail.com"
__license__ = "MIT"

from .converter import ObsidianToHugoConverter
from .models import ConversionConfig
from .linker import InternalLinker

__all__ = [
    "ObsidianToHugoConverter",
    "ConversionConfig", 
    "InternalLinker",
    "__version__",
    "__title__",
] 