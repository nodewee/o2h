"""Link processing utilities for O2H converter."""

import html
import re
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .logger import logger
from .models import InlineLink, LinkType
from .utils import slugify_path


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
        
        # Find all markdown links
        link_pattern = r"\[.*?\]\((.*?)\)"
        for original_uri in re.findall(link_pattern, content):
            self._process_link(original_uri, note_folder, note_filepath)
        
        return content
    
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
                    content = content.replace(f"]({original_uri})", f"]({dest_uri})")
                    
            elif link.link_type == LinkType.ANCHOR:
                dest_uri = f"#{link.anchor}"
                content = content.replace(f"]({original_uri})", f"]({dest_uri})")
                
            elif link.link_type == LinkType.NOTE:
                dest_uri = self._get_note_uri(link, note_files_map, content_dir)
                if link.anchor:
                    dest_uri += f"#{link.anchor}"
                content = content.replace(f"]({original_uri})", f"](/{dest_uri})")
        
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