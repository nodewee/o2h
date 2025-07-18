"""Internal linking functionality for O2H converter."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import frontmatter

from .code_block_detector import is_range_in_code_block
from .logger import logger
from .models import InternalLinkRegistry, LinkWord, NoteMetadata


class InternalLinker:
    """Handles internal linking between articles based on link_words."""
    
    def __init__(self, max_links_per_article: int = 1):
        """Initialize internal linker.
        
        Args:
            max_links_per_article: Maximum number of links per word per article
        """
        self.registry = InternalLinkRegistry()
        self.max_links_per_article = max_links_per_article
        self.total_links_added = 0
        
    def build_link_registry(
        self, 
        note_files_map: Dict[Path, Path], 
        content_dir: Path
    ) -> None:
        """Build the internal link registry from all notes.
        
        Args:
            note_files_map: Mapping of note paths to post paths
            content_dir: Content directory path for URL generation
        """
        logger.info("Building internal link registry...")
        
        for note_path, post_path in note_files_map.items():
            if not post_path:  # Skip notes that won't be converted
                continue
                
            try:
                # Read and parse note
                note_content = note_path.read_text(encoding="utf-8")
                note = frontmatter.loads(note_content)
                
                # Extract link_words from frontmatter
                link_words = NoteMetadata.extract_link_words(note.metadata)
                if not link_words:
                    continue
                    
                # Ensure link_words is a list
                if isinstance(link_words, str):
                    link_words = [link_words]
                elif not isinstance(link_words, list):
                    logger.warning(f"Invalid link_words format in {note_path}: {link_words}")
                    continue
                
                # Generate target URL for this note
                target_url = self._generate_note_url(note, post_path, content_dir)
                
                # Add words to registry
                self.registry.add_words_from_note(
                    words=link_words,
                    target_url=target_url,
                    source_note_path=note_path
                )
                
                logger.debug(f"Added {len(link_words)} link words from {note_path.name}")
                
            except Exception as e:
                logger.error(f"Failed to process link words from {note_path}: {e}")
        
        logger.info(f"Built registry with {len(self.registry.link_words)} unique link words")
        
        # Report conflicts
        if self.registry.conflicts:
            logger.warning(f"Found {len(self.registry.conflicts)} link word conflicts")
            for word, conflicts in self.registry.conflicts:
                sources = [str(lw.source_note_path.name) for lw in conflicts]
                logger.warning(f"  '{word}' conflicts between: {', '.join(sources)}")
    
    def _generate_note_url(
        self, 
        note: frontmatter.Post, 
        post_path: Path, 
        content_dir: Path
    ) -> str:
        """Generate URL for a note.
        
        Args:
            note: Parsed frontmatter post
            post_path: Destination post path
            content_dir: Content directory path
            
        Returns:
            Generated URL string
        """
        # Get language from metadata
        lang = note.metadata.get("lang")
        
        # Get relative path from content directory
        rel_path = post_path.relative_to(content_dir)
        url_path = str(rel_path.with_suffix(""))
        
        # Handle language prefix for multilingual sites
        if lang:
            if url_path.endswith(f".{lang}"):
                url_path = url_path[:-len(f".{lang}")]
            url_path = f"{lang}/{url_path}"
        
        return f"/{url_path}/"
    
    def apply_internal_links(
        self, 
        content: str, 
        current_note_path: Path,
        current_note_metadata: NoteMetadata
    ) -> str:
        """Apply internal links to content.
        
        Args:
            content: Article content
            current_note_path: Path of current note being processed
            current_note_metadata: Metadata of current note
            
        Returns:
            Content with internal links applied
        """
        if not self.registry.link_words:
            return content
            
        # Get link words defined by current note to avoid self-linking
        current_link_words = set(word.lower() for word in current_note_metadata.link_words)
        
        # Track links added to this article
        links_added_this_article = {}
        modified_content = content
        
        # Sort link words by length (longest first) to avoid partial matches
        sorted_link_words = sorted(
            self.registry.link_words.items(),
            key=lambda x: len(x[1].word),
            reverse=True
        )
        
        for word_key, link_word in sorted_link_words:
            # Skip if this word is defined by current note
            if word_key in current_link_words:
                continue
                
            # Skip if we've already added max links for this word
            if links_added_this_article.get(word_key, 0) >= self.max_links_per_article:
                continue
            
            # Find and replace first occurrence
            modified_content, added = self._replace_word_with_link(
                modified_content, 
                link_word.word, 
                link_word.target_url,
                current_note_path
            )
            
            if added:
                links_added_this_article[word_key] = links_added_this_article.get(word_key, 0) + 1
                self.total_links_added += 1
        
        return modified_content
    
    def _replace_word_with_link(
        self, 
        content: str, 
        word: str, 
        target_url: str,
        current_note_path: Path
    ) -> Tuple[str, bool]:
        """Replace first occurrence of word with link.
        
        Args:
            content: Content to modify
            word: Word to replace
            target_url: URL to link to
            current_note_path: Current note path for logging
            
        Returns:
            Tuple of (modified_content, was_replaced)
        """
        # Skip if word is already a link
        if self._is_word_already_linked(content, word):
            return content, False
        
        # Create regex pattern for word boundary matching
        pattern = self._create_word_boundary_pattern(word)
        
        # Find all matches
        matches = list(re.finditer(pattern, content, re.IGNORECASE))
        if not matches:
            return content, False
        
        # Check each match to see if it's in a safe location (not in code blocks)
        for match in matches:
            start, end = match.span()
            
            # Check if this match is inside a code block using the new detector
            if is_range_in_code_block(content, start, end):
                continue
            
            # Replace this occurrence
            matched_word = match.group(0)
            replacement = f"[{matched_word}]({target_url})"
            modified_content = content[:start] + replacement + content[end:]
            
            logger.debug(f"Added internal link for '{word}' in {current_note_path.name}")
            return modified_content, True
        
        return content, False
    
    def _create_word_boundary_pattern(self, word: str) -> str:
        """Create regex pattern for word boundary matching.
        
        Args:
            word: Word to create pattern for
            
        Returns:
            Regex pattern string
        """
        # Escape special regex characters
        escaped_word = re.escape(word)
        
        # Check if word contains both Chinese and English characters
        has_chinese = self._contains_chinese(word)
        has_english = any(c.isalpha() for c in word)
        
        if has_chinese and has_english:
            # Mixed Chinese-English: use more flexible boundaries
            return escaped_word
        elif has_chinese:
            # Pure Chinese: no word boundaries needed
            return escaped_word
        else:
            # Pure English: use strict word boundaries
            return rf"\b{escaped_word}\b"
    
    def _contains_chinese(self, text: str) -> bool:
        """Check if text contains Chinese characters.
        
        Args:
            text: Text to check
            
        Returns:
            True if contains Chinese characters
        """
        # Check for CJK Unified Ideographs and Extensions
        return any(
            '\u4e00' <= char <= '\u9fff' or  # CJK Unified Ideographs
            '\u3400' <= char <= '\u4dbf' or  # CJK Extension A
            '\uf900' <= char <= '\ufaff' or  # CJK Compatibility Ideographs
            '\u20000' <= char <= '\u2a6df' or  # CJK Extension B
            '\u2a700' <= char <= '\u2b73f' or  # CJK Extension C
            '\u2b740' <= char <= '\u2b81f' or  # CJK Extension D
            '\u2b820' <= char <= '\u2ceaf'     # CJK Extension E
            for char in text
        )
    
    def _is_word_already_linked(self, content: str, word: str) -> bool:
        """Check if word is already part of a link.
        
        Args:
            content: Content to check
            word: Word to check
            
        Returns:
            True if word is already linked
        """
        # Escape the word for regex
        escaped_word = re.escape(word)
        
        # Create pattern to match word boundaries (for English) or exact match (for Chinese)
        if self._contains_chinese(word):
            word_pattern = escaped_word
        else:
            word_pattern = rf"\b{escaped_word}\b"
        
        # Look for the word within markdown link syntax
        # Pattern: [text containing word](url)
        link_pattern = rf'\[([^\]]*{word_pattern}[^\]]*)\]\([^)]+\)'
        
        # Also check for HTML links: <a href="...">text containing word</a>
        html_link_pattern = rf'<a[^>]*>([^<]*{word_pattern}[^<]*)</a>'
        
        return bool(
            re.search(link_pattern, content, re.IGNORECASE) or
            re.search(html_link_pattern, content, re.IGNORECASE)
        )
    
    def get_statistics(self) -> Dict[str, int]:
        """Get internal linking statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "total_link_words": len(self.registry.link_words),
            "total_conflicts": len(self.registry.conflicts),
            "total_links_added": self.total_links_added
        }