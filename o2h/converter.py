"""Main converter class for Obsidian to Hugo/Zola conversion."""

import html
import json
import logging
import os
import pathlib
import re
import shutil
import urllib.parse
import io
import toml
from pathlib import Path
from typing import Dict, List, Optional

import frontmatter
from o2h.add_spaces import add_spaces_to_content
from slugify import slugify
from o2h.utils import (
    calc_file_md5,
    format_time,
    get_file_creation_time,
    get_file_modification_time,
    slugify_path,
    yield_files,
    yield_subfolders,
)
from .link_processor import LinkProcessor
from .linker import InternalLinker
from .logger import logger
from .models import (
    ConversionConfig,
    ConversionResult,
    FrontmatterFormat,
    InlineLink,
    LinkType,
    NoteMetadata,
)


# Custom TOML handler for frontmatter
class CustomTOMLHandler:
    """Handler for TOML frontmatter."""

    def load(self, fm, text):
        """Parse TOML front matter. Returns the metadata and content."""
        try:
            metadata, content = self.split(text)
            if metadata:
                fm.metadata = toml.loads(metadata)
            else:
                fm.metadata = {}
            fm.content = content
        except Exception as e:
            logging.error(f"Error parsing frontmatter: {e}")
            fm.metadata = {}
            fm.content = text

    def split(self, text):
        """Split text into metadata and content parts."""
        if not text.startswith('+++'):
            return None, text

        # Find the end of the frontmatter section (marked by +++)
        end_index = text.find('+++', 3)
        if end_index == -1:
            return None, text

        metadata = text[3:end_index].strip()
        content = text[end_index+3:].lstrip()
        return metadata, content

    def export(self, metadata, content):
        """Format metadata and content for TOML frontmatter."""
        if not metadata:
            return content

        try:
            toml_metadata = toml.dumps(metadata)
            if not toml_metadata.strip():
                return content
            return f"+++\n{toml_metadata}+++\n\n{content}"
        except Exception as e:
            logging.error(f"Error exporting TOML frontmatter: {e}")
            return content

    def format(self, post, **kwargs):
        """Format a post for dumping."""
        return self.export(post.metadata, post.content)


class TOMLFrontmatterHandler:
    """Custom TOML handler for python-frontmatter."""

    def load(self, fm: frontmatter.Post, text: str) -> None:
        """Parse TOML frontmatter."""
        try:
            metadata, content = self._split_frontmatter(text)
            if metadata:
                fm.metadata = toml.loads(metadata)
            else:
                fm.metadata = {}
            fm.content = content
        except Exception as e:
            logger.error(f"Error parsing TOML frontmatter: {e}")
            fm.metadata = {}
            fm.content = text

    def _split_frontmatter(self, text: str) -> tuple[Optional[str], str]:
        """Split text into metadata and content."""
        if not text.startswith("+++"):
            return None, text

        end_index = text.find("+++", 3)
        if end_index == -1:
            return None, text

        metadata = text[3:end_index].strip()
        content = text[end_index + 3:].lstrip()
        return metadata, content

    def export(self, metadata: dict, content: str) -> str:
        """Export metadata and content as TOML frontmatter."""
        if not metadata:
            return content

        try:
            toml_metadata = toml.dumps(metadata)
            if not toml_metadata.strip():
                return content
            return f"+++\n{toml_metadata}+++\n\n{content}"
        except Exception as e:
            logger.error(f"Error exporting TOML frontmatter: {e}")
            return content

    def format(self, post: frontmatter.Post, **kwargs) -> str:
        """Format a post for output."""
        return self.export(post.metadata, post.content)


class ObsidianToHugoConverter:
    """Main converter class for Obsidian to Hugo/Zola conversion."""

    def __init__(self, config: ConversionConfig):
        """Initialize converter with configuration.
        
        Args:
            config: Conversion configuration
        """
        self.config = config
        self.link_processor = LinkProcessor(config.obsidian_vault_path)
        self.internal_linker = None
        if config.enable_internal_linking:
            self.internal_linker = InternalLinker(config.internal_link_max_per_article)
        self.result = ConversionResult()

    def convert(self) -> ConversionResult:
        """Perform the complete conversion process.
        
        Returns:
            Conversion result with statistics and any errors
        """
        try:
            logger.info("Starting conversion...")
            
            # Prepare folder mappings
            folder_map = self._prepare_folder_map()
            
            # Parse notes and extract links
            note_files_map = self._parse_notes(folder_map)
            
            # Clean destination directories if requested
            if self.config.clean_dest_dirs:
                self._clean_destination_directories(folder_map)
            
            # Copy attachments
            self._copy_attachments()
            
            # Build internal link registry if enabled
            if self.internal_linker:
                content_dir = self.config.hugo_project_path / "content"
                self.internal_linker.build_link_registry(note_files_map, content_dir)
            
            # Generate Hugo/Zola posts
            self._generate_posts(note_files_map, folder_map)
            
            # Update result with internal linking statistics
            if self.internal_linker:
                stats = self.internal_linker.get_statistics()
                self.result.internal_links_added = stats["total_links_added"]
            
            logger.info(f"Conversion completed! {self.result.converted_notes} notes converted.")
            if self.internal_linker:
                logger.info(f"Added {self.result.internal_links_added} internal links.")
            
        except Exception as e:
            error_msg = f"Conversion failed: {e}"
            logger.error(error_msg)
            self.result.errors.append(error_msg)
            
        return self.result

    def _prepare_folder_map(self) -> Dict[Path, Path]:
        """Prepare mapping of source folders to destination folders.
        
        Returns:
            Dictionary mapping source paths to destination paths
        """
        folder_map = {}
        
        # Get template folder from Obsidian config
        template_folder = self._get_template_folder()
        if template_folder:
            self.config.excluded_dirs.append(f"^(?:{template_folder})$")
        
        if self.config.folder_name_map:
            # Use specified folder mappings
            for src_folder, dest_folder in self.config.folder_name_map.items():
                src_path = self.config.obsidian_vault_path / src_folder
                dest_rel_path = slugify_path(dest_folder)
                dest_path = self.config.hugo_project_path / "content" / dest_rel_path
                folder_map[src_path] = dest_path
        else:
            # Use all folders in vault
            for folder_path in yield_subfolders(
                self.config.obsidian_vault_path,
                recursive=True,
                excludes=self.config.excluded_dirs,
            ):
                rel_path = folder_path.relative_to(self.config.obsidian_vault_path)
                dest_rel_path = slugify_path(str(rel_path))
                dest_path = self.config.hugo_project_path / "content" / dest_rel_path
                folder_map[folder_path] = dest_path
                
            # Add vault root folder
            folder_map[self.config.obsidian_vault_path] = (
                self.config.hugo_project_path / "content" / "posts"
            )
            
        return folder_map
    
    def _get_template_folder(self) -> Optional[str]:
        """Get template folder name from Obsidian configuration.
        
        Returns:
            Template folder name or None if not found
        """
        try:
            template_config_path = (
                self.config.obsidian_vault_path / ".obsidian" / "templates.json"
            )
            if template_config_path.exists():
                config_data = json.loads(template_config_path.read_text())
                return config_data.get("folder")
        except Exception as e:
            logger.warning(f"Could not read template configuration: {e}")
        return None

    def _parse_notes(self, folder_map: Dict[Path, Path]) -> Dict[Path, Path]:
        """Parse Obsidian notes and extract metadata and links.
        
        Args:
            folder_map: Mapping of source to destination folders
            
        Returns:
            Dictionary mapping note paths to post paths
        """
        note_files_map = {}
        
        for note_folder, post_folder in folder_map.items():
            for note_path in yield_files(
                note_folder, 
                extensions=[".md"], 
                recursive=False
            ):
                # Skip excluded directories
                if self._should_exclude_note(note_path):
                    continue
                    
                try:
                    # Parse note
                    note_content = note_path.read_text(encoding="utf-8")
                    note = frontmatter.loads(note_content)
                    
                    # Extract links from content
                    self.link_processor.extract_links_from_content(
                        note.content, note_folder, str(note_path)
                    )
                    
                    # Extract links from frontmatter
                    self.link_processor.extract_links_from_frontmatter(
                        note.metadata, note_folder, str(note_path)
                    )
                    
                    # Generate post path
                    post_path = self._generate_post_path(note, note_path, post_folder)
                    note_files_map[note_path] = post_path
                    
                except Exception as e:
                    error_msg = f"Failed to parse note {note_path}: {e}"
                    logger.error(error_msg)
                    self.result.errors.append(error_msg)
                    
        return note_files_map

    def _should_exclude_note(self, note_path: Path) -> bool:
        """Check if note should be excluded from conversion.
        
        Args:
            note_path: Path to the note
            
        Returns:
            True if note should be excluded
        """
        import re
        
        dir_name = note_path.parent.name
        return any(
            re.search(pattern, dir_name) 
            for pattern in self.config.excluded_dirs
        )

    def _generate_post_path(
        self, 
        note: frontmatter.Post, 
        note_path: Path, 
        post_folder: Path
    ) -> Path:
        """Generate destination path for a post.
        
        Args:
            note: Parsed frontmatter post
            note_path: Source note path
            post_folder: Destination folder
            
        Returns:
            Destination post path
        """
        # Get slug from metadata or generate from filename
        slug = note.metadata.get("slug")
        if not slug:
            filename = note_path.stem
            slug = slugify_path(add_spaces_to_content(filename))
        
        # Add language suffix if specified
        lang = note.metadata.get("lang")
        if lang:
            post_filename = f"{slug}.{lang}.md"
        else:
            post_filename = f"{slug}.md"
            
        return post_folder / post_filename

    def _clean_destination_directories(self, folder_map: Dict[Path, Path]) -> None:
        """Clean destination directories before conversion.
        
        Args:
            folder_map: Mapping of source to destination folders
        """
        logger.info("Cleaning destination directories...")
        
        dirs_to_clean = list(folder_map.values())
        
        # Add attachment directory
        if self.config.attachment_target_path:
            # Use custom attachment path
            attachment_dir = self.config.attachment_target_path
            if not attachment_dir.is_absolute():
                attachment_dir = attachment_dir.resolve()
        else:
            # Use original logic with static folder
            attachment_dir = self.config.hugo_project_path / "static"
            for part in self.config.attachment_folder_name.split("/"):
                attachment_dir = attachment_dir / part
                
        dirs_to_clean.append(attachment_dir)
        
        for dir_path in dirs_to_clean:
            # Avoid cleaning the Hugo project root
            if dir_path.resolve() == self.config.hugo_project_path.resolve():
                continue
                
            if dir_path.exists():
                logger.info(f"Cleaning directory: {dir_path}")
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file() and not file_path.name.startswith("_index."):
                        file_path.unlink()

    def _copy_attachments(self) -> None:
        """Copy attachment files to destination."""
        logger.info("Copying attachments...")
        
        # Determine destination directory
        if self.config.attachment_target_path:
            # Use custom attachment path
            dest_dir = self.config.attachment_target_path
            if not dest_dir.is_absolute():
                # If relative path, make it relative to current working directory
                dest_dir = dest_dir.resolve()
        else:
            # Use original logic with static folder
            dest_dir = self.config.hugo_project_path / "static"
            for part in self.config.attachment_folder_name.split("/"):
                dest_dir = dest_dir / part
                
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        for link in self.link_processor.inline_links.values():
            if link.link_type != LinkType.FILE or not link.source_path:
                continue
                
            try:
                # Generate destination filename
                if self.config.md5_attachment:
                    dest_filename = (
                        calc_file_md5(link.source_path) + link.source_path.suffix
                    )
                else:
                    rel_path = link.source_path.relative_to(self.config.obsidian_vault_path)
                    rel_dir = rel_path.parent
                    filename_base = f"{rel_dir}-{link.source_path.stem}".replace("/", "-")
                    slug_filename = slugify_path(add_spaces_to_content(filename_base))
                    dest_filename = slug_filename + link.source_path.suffix
                
                dest_path = dest_dir / dest_filename
                shutil.copyfile(link.source_path, dest_path)
                
                # Update link with destination filename
                link.dest_filename = dest_filename
                self.result.copied_attachments += 1
                
            except Exception as e:
                error_msg = f"Failed to copy attachment {link.source_path}: {e}"
                logger.error(error_msg)
                self.result.errors.append(error_msg)

    def _generate_posts(self, note_files_map: Dict[Path, Path], folder_map: Dict[Path, Path]) -> None:
        """Generate Hugo/Zola posts from Obsidian notes.
        
        Args:
            note_files_map: Mapping of note paths to post paths
            folder_map: Mapping of source to destination folders
        """
        # Check for linked notes that aren't being converted
        self._validate_note_links(note_files_map, folder_map)
        
        for note_path, post_path in note_files_map.items():
            if not post_path:  # Skip notes that shouldn't be converted
                continue
                
            try:
                self._convert_single_note(note_path, post_path, note_files_map)
                self.result.converted_notes += 1
                
            except Exception as e:
                error_msg = f"Failed to convert note {note_path}: {e}"
                logger.error(error_msg)
                self.result.errors.append(error_msg)

    def _validate_note_links(self, note_files_map: Dict[Path, Path], folder_map: Dict[Path, Path]) -> None:
        """Validate that linked notes exist in the conversion map, providing detailed warnings.
        
        Args:
            note_files_map: Mapping of note paths to post paths
            folder_map: Mapping of source to destination folders
        """
        for link in self.link_processor.inline_links.values():
            if link.link_type == LinkType.NOTE and link.source_path:
                if link.source_path not in note_files_map:
                    reason = ""
                    note_parent_dir = link.source_path.parent

                    # Check if the note was explicitly excluded
                    if self._should_exclude_note(link.source_path):
                        reason = f"its parent directory ('{note_parent_dir.name}') is in the excluded list (e.g., templates)."
                    
                    # Check if its folder wasn't included when using --folders
                    elif self.config.folder_name_map:
                        is_in_scope = note_parent_dir in folder_map
                        is_in_subfolder_of_scope = False
                        
                        if not is_in_scope:
                            for src_folder_path in folder_map.keys():
                                if note_parent_dir.is_relative_to(src_folder_path):
                                    is_in_subfolder_of_scope = True
                                    break
                        
                        rel_path = note_parent_dir.relative_to(self.config.obsidian_vault_path)
                        if is_in_subfolder_of_scope:
                            reason = f"its parent directory ('{rel_path}') is a sub-directory of a folder specified in --folders, but sub-directories are not converted recursively with this option. Please specify '{rel_path}' directly in --folders if you want to convert it."
                        else:
                            reason = f"its parent directory ('{rel_path}') was not included in the conversion scope specified by --folders."
                    
                    if not reason:
                        reason = "it was not found in the set of notes to be converted. This may be due to a file system issue or a bug."

                    warning_msg = f"Linked note '{link.original_uri}' will not be converted. Reason: {reason}"
                    logger.warning(warning_msg)
                    self.result.warnings.append(warning_msg)
                    
                    # Add placeholder to avoid errors during link replacement
                    note_files_map[link.source_path] = None

    def _convert_single_note(
        self, 
        note_path: Path, 
        post_path: Path, 
        note_files_map: Dict[Path, Path]
    ) -> None:
        """Convert a single note to a post.
        
        Args:
            note_path: Source note path
            post_path: Destination post path
            note_files_map: Mapping of all note paths to post paths
        """
        # Read and parse note
        note_content = note_path.read_text(encoding="utf-8")
        note = frontmatter.loads(note_content)
        
        # Process metadata
        metadata = self._process_metadata(note.metadata, note_path)
        
        # Replace links in content
        processed_content = self.link_processor.replace_links_in_content(
            note.content,
            note_files_map,
            self.config.hugo_project_path,
            self.config.attachment_folder_name,
            self.config,
        )
        
        # Replace links in frontmatter metadata
        processed_metadata_dict = self.link_processor.replace_links_in_frontmatter(
            metadata.to_dict(),
            note_files_map,
            self.config.hugo_project_path,
            self.config.attachment_folder_name,
            self.config,
        )
        
        # Apply internal links if enabled
        if self.internal_linker:
            processed_content = self.internal_linker.apply_internal_links(
                processed_content,
                note_path,
                metadata
            )
        
        # Create post with processed data
        post = frontmatter.Post(processed_content, **processed_metadata_dict)
        
        # Generate output based on frontmatter format
        if self.config.frontmatter_format == FrontmatterFormat.TOML:
            output = frontmatter.dumps(post, handler=CustomTOMLHandler())
        else:
            output = frontmatter.dumps(post)
        
        # Ensure destination directory exists and write file
        post_path.parent.mkdir(parents=True, exist_ok=True)
        post_path.write_text(output, encoding="utf-8")

    def _process_metadata(self, raw_metadata: dict, note_path: Path) -> NoteMetadata:
        """Process and normalize note metadata.
        
        Args:
            raw_metadata: Raw metadata from frontmatter
            note_path: Path to the note file
            
        Returns:
            Processed metadata object
        """
        metadata = NoteMetadata()
        
        # Store original metadata to preserve all fields
        metadata._original_metadata = raw_metadata.copy()
        
        # Process title
        metadata.title = raw_metadata.get("title", "").strip()
        if not metadata.title:
            metadata.title = html.escape(note_path.stem)
        
        # Process dates
        metadata.date = (
            raw_metadata.get("date") or 
            raw_metadata.get("created") or 
            get_file_creation_time(note_path)
        )
        
        metadata.lastmod = (
            raw_metadata.get("lastmod") or 
            raw_metadata.get("updated") or 
            raw_metadata.get("modified") or 
            get_file_modification_time(note_path)
        )
        
        # Process other fields
        metadata.tags = raw_metadata.get("tags", [])
        metadata.slug = raw_metadata.get("slug")
        metadata.lang = raw_metadata.get("lang")
        
        # Process link_words for internal linking
        link_words = raw_metadata.get("link_words", [])
        if isinstance(link_words, str):
            metadata.link_words = [link_words]
        elif isinstance(link_words, list):
            metadata.link_words = link_words
        else:
            metadata.link_words = []
        
        return metadata
