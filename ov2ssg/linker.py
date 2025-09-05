"""Internal linking functionality for OV2SSG converter."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from functools import lru_cache

import frontmatter

from .code_block_detector import is_range_in_code_block
from .logger import logger
from .models import InternalLinkRegistry, LinkWord, NoteMetadata
from .hugo_config import HugoConfigReader


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
        self.hugo_project_path: Optional[Path] = None
        
        # Pre-compile regex patterns for better performance
        self._code_block_pattern = re.compile(r'```.*?```|``.*?``|`.*?`', re.DOTALL)
        self._markdown_link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        self._html_link_pattern = re.compile(r'<a\s+[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', re.IGNORECASE)
        
    def build_link_registry(
        self, 
        note_files_map: Dict[Path, Path], 
        content_dir: Path,
        hugo_project_path: Optional[Path] = None
    ) -> None:
        """Build the internal link registry from all notes.
        
        Args:
            note_files_map: Mapping of note paths to post paths
            content_dir: Content directory path for URL generation
            hugo_project_path: Path to the Hugo project directory
        """
        logger.info("Building internal link registry...")
        
        if hugo_project_path:
            self.hugo_project_path = hugo_project_path
        
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
    
    @lru_cache(maxsize=512)
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
        
        # Extract slug from filename or use title
        slug = note.metadata.get("slug", Path(rel_path).stem)
        
        # Extract section from path
        section = "posts"
        if len(rel_path.parts) > 1:
            section = rel_path.parts[0]
        
        # Get date from metadata
        date = note.metadata.get("date", "")
        
        # Get title from metadata
        title = note.metadata.get("title", slug)
        
        # Determine the permalink pattern
        if self.hugo_project_path and self.hugo_project_path.exists():
            pattern = HugoConfigReader.get_permalink_pattern(self.hugo_project_path, section)
        else:
            pattern = "/posts/:slug"
        
        # Generate URL using the pattern
        url = HugoConfigReader.generate_url_from_pattern(
            pattern=pattern,
            slug=slug,
            date=date,
            title=title,
            section=section
        )
        
        # Handle language prefix for multilingual sites
        if lang:
            if url.startswith("/"):
                url = f"/{lang}{url}"
            else:
                url = f"/{lang}/{url}"
        
        # Ensure trailing slash for internal article links, handling anchors and query params
        if '?' in url or '#' in url:
            # Handle URLs with query params or anchors
            if '?' in url and '#' in url:
                # Both query and anchor
                parts = url.split('?', 1)
                if len(parts) == 2:
                    base_url, query_and_anchor = parts
                    if not base_url.endswith("/"):
                        base_url = base_url + "/"
                    url = base_url + "?" + query_and_anchor
            elif '?' in url:
                # Only query params
                parts = url.split('?', 1)
                if len(parts) == 2:
                    base_url, query = parts
                    if not base_url.endswith("/"):
                        base_url = base_url + "/"
                    url = base_url + "?" + query
            else:  # '#' in url
                # Only anchor
                parts = url.split('#', 1)
                if len(parts) == 2:
                    base_url, anchor = parts
                    if not base_url.endswith("/"):
                        base_url = base_url + "/"
                    url = base_url + "#" + anchor
        else:
            # Simple URL without query params or anchors
            if not url.endswith("/"):
                url = url + "/"
        
        return url
    
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
        
        # Check if word contains Chinese characters
        has_chinese = self._contains_chinese(word)
        
        if has_chinese:
            # Chinese content: use simple exact match for Chinese characters
            # The word boundaries in Chinese context are handled by context
            return escaped_word
        else:
            # English content: use strict word boundaries
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
        
        # Create pattern based on content type
        has_chinese = self._contains_chinese(word)
        if has_chinese:
            # Chinese content: use exact match
            word_pattern = escaped_word
        else:
            # English content: use word boundaries
            word_pattern = rf"\b{escaped_word}\b"
        
        # Check if the word appears in any link URL or link text
        # First, find all markdown links
        markdown_links = self._markdown_link_pattern.finditer(content)
        for match in markdown_links:
            link_text, link_url = match.groups()
            # Check if word appears in either link text or URL
            if re.search(word_pattern, link_text, re.IGNORECASE) or re.search(word_pattern, link_url, re.IGNORECASE):
                return True
        
        # Check HTML links
        html_links = self._html_link_pattern.finditer(content)
        for match in html_links:
            link_url, link_text = match.groups()
            if re.search(word_pattern, link_text, re.IGNORECASE) or re.search(word_pattern, link_url, re.IGNORECASE):
                return True
                
        return False
    
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