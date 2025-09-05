"""O2H - Convert Obsidian notes to Hugo/Zola posts."""

__version__ = "0.3.8"
__title__ = "O2H"
__author__ = "nodewee@gmail.com"
__license__ = "MIT"

from .converter import ObsidianToHugoConverter
from .models import ConversionConfig
from .linker import InternalLinker
from .code_block_detector import CodeBlockDetector, detect_code_blocks, is_position_in_code_block, is_range_in_code_block
from .ssg_detector import SSGDetector, SSGType, detect_ssg_type

__all__ = [
    "ObsidianToHugoConverter",
    "ConversionConfig", 
    "InternalLinker",
    "CodeBlockDetector",
    "detect_code_blocks",
    "is_position_in_code_block", 
    "is_range_in_code_block",
    "SSGDetector",
    "SSGType",
    "detect_ssg_type",
    "__version__",
    "__title__",
]