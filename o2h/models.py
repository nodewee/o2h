"""Data models for O2H converter."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple


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
    attachment_target_path: Optional[Path] = None  # New field for custom attachment path
    attachment_host: Optional[str] = None  # New field for attachment host domain
    folder_name_map: Dict[str, str] = field(default_factory=dict)
    clean_dest_dirs: bool = False
    md5_attachment: bool = False
    frontmatter_format: FrontmatterFormat = FrontmatterFormat.YAML
    excluded_dirs: List[str] = field(default_factory=lambda: [r"^\."])
    # Internal linking configuration
    enable_internal_linking: bool = True
    internal_link_max_per_article: int = 1
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.obsidian_vault_path.exists():
            raise FileNotFoundError(f"Obsidian vault not found: {self.obsidian_vault_path}")
        if not self.hugo_project_path.exists():
            raise FileNotFoundError(f"Hugo/Zola project not found: {self.hugo_project_path}")
        
        # Validate internal linking configuration
        if self.internal_link_max_per_article < 0:
            raise ValueError("internal_link_max_per_article must be non-negative")
        if self.internal_link_max_per_article > 100:
            import warnings
            warnings.warn("internal_link_max_per_article > 100 may cause performance issues")


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
class LinkWord:
    """Represents a link word for internal linking."""
    
    word: str
    target_url: str
    source_note_path: Path
    priority: int = 0  # Higher priority wins in case of conflicts
    
    def __hash__(self) -> int:
        """Make LinkWord hashable for use in sets."""
        return hash(self.word.lower())
    
    def __eq__(self, other) -> bool:
        """Compare LinkWords by word (case-insensitive)."""
        if not isinstance(other, LinkWord):
            return False
        return self.word.lower() == other.word.lower()


@dataclass
class InternalLinkRegistry:
    """Registry for managing internal link words."""
    
    link_words: Dict[str, LinkWord] = field(default_factory=dict)
    conflicts: List[Tuple[str, List[LinkWord]]] = field(default_factory=list)
    
    def add_words_from_note(
        self, 
        words: List[str], 
        target_url: str, 
        source_note_path: Path,
        priority: int = 0
    ) -> None:
        """Add link words from a note to the registry.
        
        Args:
            words: List of words to link to this note
            target_url: URL to link to
            source_note_path: Path of the source note
            priority: Priority for conflict resolution
        """
        for word in words:
            if not word or not word.strip():
                continue
                
            word_key = word.strip().lower()
            new_link_word = LinkWord(
                word=word.strip(),
                target_url=target_url,
                source_note_path=source_note_path,
                priority=priority
            )
            
            if word_key in self.link_words:
                existing = self.link_words[word_key]
                if existing.target_url != target_url:
                    # Handle conflict - use higher priority or first occurrence
                    if new_link_word.priority > existing.priority:
                        self.link_words[word_key] = new_link_word
                    # Record conflict for reporting
                    self._record_conflict(word_key, [existing, new_link_word])
            else:
                self.link_words[word_key] = new_link_word
    
    def _record_conflict(self, word: str, conflicting_words: List[LinkWord]) -> None:
        """Record a conflict for reporting."""
        # Check if conflict already recorded
        for existing_word, existing_conflicts in self.conflicts:
            if existing_word == word:
                # Add only new conflicts that aren't already recorded
                for new_conflict in conflicting_words:
                    if new_conflict not in existing_conflicts:
                        existing_conflicts.append(new_conflict)
                return
        self.conflicts.append((word, conflicting_words))
    
    def get_link_for_word(self, word: str) -> Optional[LinkWord]:
        """Get link word entry for a given word.
        
        Args:
            word: Word to search for
            
        Returns:
            LinkWord if found, None otherwise
        """
        return self.link_words.get(word.lower())


@dataclass
class NoteMetadata:
    """Metadata extracted from Obsidian notes."""
    
    title: Optional[str] = None
    date: Optional[str] = None
    lastmod: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    slug: Optional[str] = None
    lang: Optional[str] = None
    link_words: List[str] = field(default_factory=list)  # New field for internal linking
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
        if self.link_words:
            data["link_words"] = self.link_words
            
        return data


@dataclass
class ConversionResult:
    """Result of a conversion operation."""
    
    converted_notes: int = 0
    copied_attachments: int = 0
    internal_links_added: int = 0  # New field for internal linking stats
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    @property
    def success(self) -> bool:
        """Check if conversion was successful."""
        return len(self.errors) == 0 