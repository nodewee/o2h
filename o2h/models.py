"""Data models for O2H converter."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class FrontmatterFormat(Enum):
    """Supported frontmatter formats."""
    YAML = "yaml"
    TOML = "toml"


class LinkType(Enum):
    """Types of inline links."""
    FILE = "file"
    NOTE = "note"
    ANCHOR = "anchor"


@dataclass
class ConversionConfig:
    """Configuration for Obsidian to Hugo/Zola conversion."""
    
    obsidian_vault_path: Path
    hugo_project_path: Path
    attachment_folder_name: str = "attachments"
    folder_name_map: Dict[str, str] = field(default_factory=dict)
    clean_dest_dirs: bool = False
    md5_attachment: bool = False
    frontmatter_format: FrontmatterFormat = FrontmatterFormat.YAML
    excluded_dirs: List[str] = field(default_factory=lambda: [r"^\."])
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.obsidian_vault_path.exists():
            raise FileNotFoundError(f"Obsidian vault not found: {self.obsidian_vault_path}")
        if not self.hugo_project_path.exists():
            raise FileNotFoundError(f"Hugo/Zola project not found: {self.hugo_project_path}")


@dataclass
class InlineLink:
    """Represents an inline link in Obsidian notes."""
    
    original_uri: str
    link_type: LinkType
    source_path: Optional[Path] = None
    dest_filename: Optional[str] = None
    anchor: Optional[str] = None
    
    @property
    def is_external(self) -> bool:
        """Check if this is an external link."""
        return ":" in self.original_uri and not self.original_uri.startswith("#")


@dataclass
class NoteMetadata:
    """Metadata extracted from Obsidian notes."""
    
    title: Optional[str] = None
    date: Optional[str] = None
    lastmod: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    slug: Optional[str] = None
    lang: Optional[str] = None
    # Store all original metadata to preserve unknown fields
    _original_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for frontmatter, preserving all original fields."""
        # Start with original metadata to preserve all fields
        data = self._original_metadata.copy()
        
        # Override with processed values
        if self.title:
            data["title"] = self.title
        if self.date:
            data["date"] = self.date
        if self.lastmod:
            data["lastmod"] = self.lastmod
        if self.tags:
            data["tags"] = self.tags
        if self.slug:
            data["slug"] = self.slug
        if self.lang:
            data["lang"] = self.lang
            
        return data


@dataclass
class ConversionResult:
    """Result of a conversion operation."""
    
    converted_notes: int = 0
    copied_attachments: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    @property
    def success(self) -> bool:
        """Check if conversion was successful."""
        return len(self.errors) == 0 