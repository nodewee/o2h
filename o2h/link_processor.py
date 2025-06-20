"""Link processing utilities for O2H converter."""

import html
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .code_block_detector import is_range_in_code_block
from .logger import logger
from .models import InlineLink, LinkType
from .utils import slugify_path


# Frontmatter fields to ignore during link processing
IGNORED_FRONTMATTER_FIELDS = {
    "title",
    "description", 
    "slug",
    "date",
    "taxonomies",
    "tags"
}


class LinkProcessor:
    """Processes links in Obsidian markdown content."""
    
    def __init__(self, obsidian_vault_path: Path):
        """Initialize link processor.
        
        Args:
            obsidian_vault_path: Path to Obsidian vault
        """
        self.obsidian_vault_path = obsidian_vault_path
        self.inline_links: Dict[str, InlineLink] = {}
    
    def extract_links_from_content(
        self, 
        content: str, 
        note_folder: Path, 
        note_filepath: str
    ) -> str:
        """Extract links from note content and convert wiki links to markdown.
        
        Args:
            content: Note content
            note_folder: Directory containing the note
            note_filepath: Path to the note file
            
        Returns:
            Content with wiki links converted to markdown links
        """
        # Convert wiki links to markdown links: [[file_path]] -> [file_path](file_path)
        content = re.sub(r"\[\[(.*?)\]\]", r"[\1](\1)", content)
        
        # Find all markdown links and check if they're in code blocks
        link_pattern = r"\[.*?\]\((.*?)\)"
        for match in re.finditer(link_pattern, content):
            original_uri = match.group(1)
            link_start = match.start()
            link_end = match.end()
            
            # Check if this link is inside a code block
            if not is_range_in_code_block(content, link_start, link_end):
                self._process_link(original_uri, note_folder, note_filepath)
        
        return content
    
    def extract_links_from_frontmatter(
        self,
        metadata: Dict[str, Any],
        note_folder: Path,
        note_filepath: str
    ) -> None:
        """Extract links from frontmatter metadata.
        
        Args:
            metadata: Frontmatter metadata dictionary
            note_folder: Directory containing the note
            note_filepath: Path to the note file
        """
        # Recursively search for links in metadata values, skipping ignored fields
        self._extract_links_from_metadata_dict(metadata, note_folder, note_filepath)
    
    def _extract_links_from_metadata_dict(
        self,
        metadata_dict: Dict[str, Any],
        note_folder: Path,
        note_filepath: str
    ) -> None:
        """Extract links from metadata dictionary, skipping ignored fields.
        
        Args:
            metadata_dict: Metadata dictionary to process
            note_folder: Directory containing the note
            note_filepath: Path to the note file
        """
        for key, value in metadata_dict.items():
            # Skip ignored fields
            if key.lower() in IGNORED_FRONTMATTER_FIELDS:
                continue
            
            self._extract_links_from_metadata_value(value, note_folder, note_filepath)
    
    def _extract_links_from_metadata_value(
        self,
        value: Any,
        note_folder: Path,
        note_filepath: str
    ) -> None:
        """Recursively extract links from metadata values.
        
        Args:
            value: Value to search for links
            note_folder: Directory containing the note
            note_filepath: Path to the note file
        """
        if isinstance(value, str):
            # Look for markdown links in string values
            link_pattern = r"\[.*?\]\((.*?)\)"
            for match in re.finditer(link_pattern, value):
                original_uri = match.group(1)
                link_start = match.start()
                link_end = match.end()
                
                # Check if this link is inside a code block (for multiline frontmatter values)
                if not is_range_in_code_block(value, link_start, link_end):
                    self._process_link(original_uri, note_folder, note_filepath)
            
            # Also check if the string itself is a file path (direct file reference)
            # But only if it's not inside a code block
            if self._is_potential_file_path(value) and not is_range_in_code_block(value, 0, len(value)):
                self._process_link(value, note_folder, note_filepath)
                
        elif isinstance(value, list):
            # Recursively process list items
            for item in value:
                self._extract_links_from_metadata_value(item, note_folder, note_filepath)
        elif isinstance(value, dict):
            # Recursively process dictionary values (no field filtering here since this is nested)
            for item_value in value.values():
                self._extract_links_from_metadata_value(item_value, note_folder, note_filepath)
    
    def _is_potential_file_path(self, text: str) -> bool:
        """Check if a string could be a file path that needs processing.
        
        Args:
            text: String to check
            
        Returns:
            True if string looks like a file path
        """
        if not text or len(text.strip()) == 0:
            return False
            
        text = text.strip()
        
        # Skip if it's a URL (external link)
        if self._is_external_link(text):
            return False
            
        # Skip if it's just an anchor
        if text.startswith("#"):
            return False
            
        # Check for common file path patterns
        # Relative paths starting with ./ or ../
        if text.startswith("./") or text.startswith("../"):
            return True
            
        # Paths that contain file extensions
        if "." in text:
            potential_ext = text.split(".")[-1].lower()
            # Common file extensions that might be in frontmatter
            common_extensions = {
                # Images
                "jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "tiff", "ico",
                # Documents
                "pdf", "md", "markdown", "txt", "doc", "docx",
                # Media
                "mp4", "webm", "ogg", "mp3", "wav", "flac",
                # Other assets
                "css", "js", "json", "xml", "yaml", "yml", "toml"
            }
            if potential_ext in common_extensions:
                # Further check: should not contain spaces (unless quoted) and should not be too long
                if len(text) < 200 and (" " not in text or (text.startswith('"') and text.endswith('"'))):
                    return True
                    
        # Paths that look like directory/file patterns (contain /)
        if "/" in text and not text.startswith("http") and len(text) < 200:
            # Check if it could be a file path
            parts = text.split("/")
            if len(parts) >= 2 and all(part for part in parts):  # No empty parts
                return True
                
        return False
    
    def _process_link(
        self, 
        original_uri: str, 
        note_folder: Path, 
        note_filepath: str
    ) -> None:
        """Process a single link.
        
        Args:
            original_uri: Original URI from the markdown link
            note_folder: Directory containing the note
            note_filepath: Path to the note file
        """
        if original_uri in self.inline_links:
            return
            
        if not original_uri:
            logger.warning(f"Found empty link in {note_filepath}")
            return
            
        if self._is_external_link(original_uri):
            return
            
        link = self._create_link_object(original_uri, note_folder)
        if link:
            self.inline_links[original_uri] = link
    
    def _is_external_link(self, uri: str) -> bool:
        """Check if URI is an external link."""
        return ":" in uri and not uri.startswith("#")
    
    def _create_link_object(
        self, 
        original_uri: str, 
        note_folder: Path
    ) -> Optional[InlineLink]:
        """Create InlineLink object from URI.
        
        Args:
            original_uri: Original URI from markdown
            note_folder: Directory containing the note
            
        Returns:
            InlineLink object or None if invalid
        """
        # Parse anchor
        parts = list(urllib.parse.urlsplit(original_uri))
        anchor = self._transform_anchor(parts[4]) if parts[4] else None
        
        # Handle anchor-only links
        if original_uri.startswith("#"):
            return InlineLink(
                original_uri=original_uri,
                link_type=LinkType.ANCHOR,
                anchor=anchor
            )
        
        # Resolve file path
        unquoted_uri_path = urllib.parse.unquote(original_uri.split("#")[0])
        source_path = self._resolve_file_path(unquoted_uri_path, note_folder)
        
        if not source_path:
            logger.warning(f"Cannot resolve link: {original_uri}")
            return None
        
        # Determine link type
        if source_path.suffix.lower() in [".md", ".markdown"]:
            link_type = LinkType.NOTE
        else:
            link_type = LinkType.FILE
            
        return InlineLink(
            original_uri=original_uri,
            link_type=link_type,
            source_path=source_path,
            anchor=anchor
        )
    
    def _resolve_file_path(
        self, 
        uri_path: str, 
        note_folder: Path
    ) -> Optional[Path]:
        """Resolve file path from URI.
        
        Args:
            uri_path: Unquoted URI path
            note_folder: Directory containing the note
            
        Returns:
            Resolved Path object or None if not found
        """
        # Try absolute path from vault root
        absolute_path = self.obsidian_vault_path / uri_path
        if absolute_path.exists():
            return absolute_path
            
        # Try relative path from note folder
        relative_path = note_folder / uri_path
        if relative_path.exists():
            return relative_path
            
        return None
    
    def _transform_anchor(self, anchor: str) -> str:
        """Transform URL anchor to Hugo/Zola format.
        
        Args:
            anchor: Original anchor string
            
        Returns:
            Transformed anchor string
        """
        anchor = anchor.strip().lower()
        if not anchor:
            return ""
            
        # URL decode and replace spaces with hyphens
        decoded = urllib.parse.unquote(anchor).replace(" ", "-")
        return urllib.parse.quote(decoded)
    
    def replace_links_in_frontmatter(
        self,
        metadata: Dict[str, Any],
        note_files_map: Dict[Path, Path],
        hugo_project_path: Path,
        attachment_folder_name: str,
    ) -> Dict[str, Any]:
        """Replace links in frontmatter metadata with final URLs.
        
        Args:
            metadata: Original frontmatter metadata
            note_files_map: Mapping of note paths to post paths
            hugo_project_path: Hugo project root path
            attachment_folder_name: Name of attachment folder
            
        Returns:
            Metadata with replaced links
        """
        if not metadata:
            return metadata
            
        content_dir = hugo_project_path / "content"
        attachment_rel_path = f"/{attachment_folder_name.strip('/')}/"
        
        # Create a deep copy of metadata to avoid modifying the original
        import copy
        processed_metadata = copy.deepcopy(metadata)
        
        # Process metadata values, skipping ignored fields
        self._replace_links_in_metadata_dict(
            processed_metadata,
            note_files_map,
            content_dir,
            attachment_rel_path
        )
        
        return processed_metadata
    
    def _replace_links_in_metadata_dict(
        self,
        metadata_dict: Dict[str, Any],
        note_files_map: Dict[Path, Path],
        content_dir: Path,
        attachment_rel_path: str
    ) -> None:
        """Replace links in metadata dictionary, skipping ignored fields.
        
        Args:
            metadata_dict: Metadata dictionary to process (modified in place)
            note_files_map: Mapping of note paths to post paths
            content_dir: Content directory path
            attachment_rel_path: Attachment relative path
        """
        for key, value in metadata_dict.items():
            # Skip ignored fields
            if key.lower() in IGNORED_FRONTMATTER_FIELDS:
                continue
                
            if isinstance(value, str):
                metadata_dict[key] = self._replace_links_in_string(
                    value, note_files_map, content_dir, attachment_rel_path
                )
            else:
                self._replace_links_in_metadata_value(
                    value, note_files_map, content_dir, attachment_rel_path
                )
    
    def _replace_links_in_metadata_value(
        self,
        value: Any,
        note_files_map: Dict[Path, Path],
        content_dir: Path,
        attachment_rel_path: str
    ) -> None:
        """Recursively replace links in metadata values.
        
        Args:
            value: Value to process (modified in place)
            note_files_map: Mapping of note paths to post paths
            content_dir: Content directory path
            attachment_rel_path: Attachment relative path
        """
        if isinstance(value, str):
            # This is a string, but we need to modify the parent container
            # This method is called on container values, not leaf strings
            pass
        elif isinstance(value, list):
            # Process list items
            for i, item in enumerate(value):
                if isinstance(item, str):
                    value[i] = self._replace_links_in_string(
                        item, note_files_map, content_dir, attachment_rel_path
                    )
                else:
                    self._replace_links_in_metadata_value(
                        item, note_files_map, content_dir, attachment_rel_path
                    )
        elif isinstance(value, dict):
            # Process nested dictionary values (no field filtering for nested dicts)
            for key, item_value in value.items():
                if isinstance(item_value, str):
                    value[key] = self._replace_links_in_string(
                        item_value, note_files_map, content_dir, attachment_rel_path
                    )
                else:
                    self._replace_links_in_metadata_value(
                        item_value, note_files_map, content_dir, attachment_rel_path
                    )
    
    def _replace_links_in_string(
        self,
        text: str,
        note_files_map: Dict[Path, Path],
        content_dir: Path,
        attachment_rel_path: str
    ) -> str:
        """Replace links in a string value.
        
        Args:
            text: String to process
            note_files_map: Mapping of note paths to post paths
            content_dir: Content directory path
            attachment_rel_path: Attachment relative path
            
        Returns:
            String with replaced links
        """
        # Convert wiki links to markdown links first
        modified_text = re.sub(r"\[\[(.*?)\]\]", r"[\1](\1)", text)
        
        # Replace markdown-format links
        for original_uri, link in self.inline_links.items():
            if f"]({original_uri})" not in modified_text:
                continue
                
            if link.link_type == LinkType.FILE:
                dest_uri = attachment_rel_path + link.dest_filename
                if link.anchor:
                    dest_uri += f"#{link.anchor}"
                modified_text = modified_text.replace(f"]({original_uri})", f"]({dest_uri})")
                
            elif link.link_type == LinkType.ANCHOR:
                dest_uri = f"#{link.anchor}"
                modified_text = modified_text.replace(f"]({original_uri})", f"]({dest_uri})")
                
            elif link.link_type == LinkType.NOTE:
                dest_uri = self._get_note_uri(link, note_files_map, content_dir)
                if link.anchor:
                    dest_uri += f"#{link.anchor}"
                modified_text = modified_text.replace(f"]({original_uri})", f"](/{dest_uri})")
        
        # Replace direct file path references (not in markdown link format)
        for original_uri, link in self.inline_links.items():
            # Skip if this is in markdown format (already handled above)
            if f"]({original_uri})" in text or f"[" in original_uri:
                continue
                
            # Check if the original URI appears as a direct string in the text
            if original_uri in modified_text:
                if link.link_type == LinkType.FILE:
                    # For files, replace with the attachment path
                    dest_uri = attachment_rel_path + link.dest_filename
                    # Remove leading slash if present since frontmatter values usually don't start with /
                    if dest_uri.startswith("/"):
                        dest_uri = dest_uri[1:]
                    modified_text = self._safe_replace_direct_path(modified_text, original_uri, dest_uri)
                    
                elif link.link_type == LinkType.NOTE:
                    # For notes, replace with the note path  
                    dest_uri = self._get_note_uri(link, note_files_map, content_dir)
                    # For frontmatter, usually we want relative paths or absolute paths starting with /
                    if not dest_uri.startswith("/"):
                        dest_uri = f"/{dest_uri}"
                    modified_text = self._safe_replace_direct_path(modified_text, original_uri, dest_uri)
        
        return modified_text
    
    def _safe_replace_direct_path(self, text: str, old_path: str, new_path: str) -> str:
        """Safely replace a direct file path in text.
        
        This is more careful than simple string replacement to avoid replacing
        parts of longer paths or URLs.
        
        Args:
            text: Text to process
            old_path: Old file path
            new_path: New file path
            
        Returns:
            Text with path replaced
        """
        if old_path not in text:
            return text
            
        # Handle quoted paths
        if f'"{old_path}"' in text:
            return text.replace(f'"{old_path}"', f'"{new_path}"')
        if f"'{old_path}'" in text:
            return text.replace(f"'{old_path}'", f"'{new_path}'")
            
        # For unquoted paths, be more careful
        # Split text and check each occurrence
        parts = text.split(old_path)
        if len(parts) < 2:
            return text
            
        # Rebuild text, replacing only standalone occurrences
        result = parts[0]
        for i in range(1, len(parts)):
            # Check characters before and after to ensure it's a standalone path
            char_before = parts[i-1][-1] if parts[i-1] else " "
            char_after = parts[i][0] if parts[i] else " "
            
            # Replace if it's bounded by whitespace, quotes, or start/end of string
            if (char_before in " \t\n:=" or char_before in '"\'') and \
               (char_after in " \t\n" or char_after in '"\''):
                result += new_path + parts[i]
            else:
                # Don't replace, keep original
                result += old_path + parts[i]
                
        return result
    
    def replace_links_in_content(
        self,
        content: str,
        note_files_map: Dict[Path, Path],
        hugo_project_path: Path,
        attachment_folder_name: str,
    ) -> str:
        """Replace links in content with final URLs.
        
        Args:
            content: Original content
            note_files_map: Mapping of note paths to post paths
            hugo_project_path: Hugo project root path
            attachment_folder_name: Name of attachment folder
            
        Returns:
            Content with replaced links
        """
        # Convert wiki links to markdown links first
        content = re.sub(r"\[\[(.*?)\]\]", r"[\1](\1)", content)
        
        content_dir = hugo_project_path / "content"
        attachment_rel_path = f"/{attachment_folder_name.strip('/')}/"
        
        video_extensions = {".mp4", ".webm", ".ogg"}
        video_template = self._get_video_template()
        
        for original_uri, link in self.inline_links.items():
            if link.link_type == LinkType.FILE:
                dest_uri = attachment_rel_path + link.dest_filename
                
                # Handle video files specially  
                if link.source_path and link.source_path.suffix.lower() in video_extensions:
                    content = self._replace_video_link(content, original_uri, dest_uri, video_template)
                else:
                    if link.anchor:
                        dest_uri += f"#{link.anchor}"
                    content = self._safe_replace_link(content, f"]({original_uri})", f"]({dest_uri})")
                    
            elif link.link_type == LinkType.ANCHOR:
                dest_uri = f"#{link.anchor}"
                content = self._safe_replace_link(content, f"]({original_uri})", f"]({dest_uri})")
                
            elif link.link_type == LinkType.NOTE:
                dest_uri = self._get_note_uri(link, note_files_map, content_dir)
                if link.anchor:
                    dest_uri += f"#{link.anchor}"
                content = self._safe_replace_link(content, f"]({original_uri})", f"](/{dest_uri})")
        
        return content
    
    def _get_video_template(self) -> str:
        """Get HTML template for video tags."""
        return """
<video controls style="width:100%; max-height:480px;border:1px solid #ccc;border-radius:5px;">
    <source src="{uri}" type="video/mp4">
</video>
"""
    
    def _replace_video_link(
        self, 
        content: str, 
        original_uri: str, 
        dest_uri: str, 
        template: str
    ) -> str:
        """Replace markdown video link with HTML video tag.
        
        Args:
            content: Original content
            original_uri: Original URI
            dest_uri: Destination URI
            template: HTML template
            
        Returns:
            Content with video link replaced
        """
        pos = self._find_markdown_link_position(content, original_uri)
        if not pos:
            return content
            
        pos_start, pos_end = pos
        tag_html = template.format(uri=dest_uri)
        return content[:pos_start] + tag_html + content[pos_end + 1:]
    
    def _find_markdown_link_position(self, content: str, uri: str) -> Optional[Tuple[int, int]]:
        """Find position of markdown link in content.
        
        Args:
            content: Content to search in
            uri: URI to find
            
        Returns:
            Tuple of (start, end) positions or None if not found
        """
        pos = content.find(f"]({uri}")
        if pos == -1:
            return None
            
        pos_end = content.find(")", pos)
        pos_start = content.rfind("![", 0, pos)
        return (pos_start, pos_end)
    
    def _get_note_uri(
        self, 
        link: InlineLink, 
        note_files_map: Dict[Path, Path], 
        content_dir: Path
    ) -> str:
        """Get URI for note link.
        
        Args:
            link: InlineLink object
            note_files_map: Mapping of note paths to post paths
            content_dir: Content directory path
            
        Returns:
            URI string
        """
        if not link.source_path:
            return "#"
            
        post_path = note_files_map.get(link.source_path)
        if not post_path:
            return "#"
            
        # Read target note to check for lang field
        try:
            import frontmatter
            target_note_content = link.source_path.read_text(encoding="utf-8")
            target_note = frontmatter.loads(target_note_content)
            target_lang = target_note.metadata.get("lang")
        except Exception:
            target_lang = None
            
        dest_rel_path = post_path.relative_to(content_dir)
        dest_uri = str(dest_rel_path.with_suffix(""))
        
        # Handle language prefix for multilingual sites
        if target_lang:
            if dest_uri.endswith(f".{target_lang}"):
                dest_uri = dest_uri[:-len(f".{target_lang}")]
            dest_uri = f"{target_lang}/{dest_uri}"
            
        return urllib.parse.quote(dest_uri)
    
    def _safe_replace_link(self, content: str, old_text: str, new_text: str) -> str:
        """Safely replace link text, avoiding code blocks.
        
        Args:
            content: Content to process
            old_text: Text to replace
            new_text: Replacement text
            
        Returns:
            Content with safe replacements
        """
        if old_text not in content:
            return content
            
        # Find all occurrences of the old text
        start = 0
        while True:
            pos = content.find(old_text, start)
            if pos == -1:
                break
                
            # Check if this position is in a code block using the new detector
            if not is_range_in_code_block(content, pos, pos + len(old_text)):
                # Safe to replace
                content = content[:pos] + new_text + content[pos + len(old_text):]
                start = pos + len(new_text)
            else:
                # Skip this occurrence
                start = pos + len(old_text)
                
        return content 