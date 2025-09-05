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
from functools import lru_cache

import frontmatter
from ov2ssg.add_spaces import add_spaces_to_content
from slugify import slugify
from ov2ssg.utils import (
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
        self.note_metadata_map: Dict[Path, NoteMetadata] = {}  # New metadata storage
        
        # Log configuration details in verbose mode
        logger.info("🔧 Initializing OV2SSG converter...")
        logger.debug(f"Configuration: {config}")
        logger.debug(f"Vault path: {config.obsidian_vault_path}")
        logger.debug(f"Project path: {config.hugo_project_path}")
        logger.debug(f"Folder mappings: {config.folder_name_map}")
        logger.debug(f"Attachment folder: {config.attachment_folder_name}")
        logger.debug(f"Internal linking: {config.enable_internal_linking}")
        
        # Log SSG type detection
        try:
            from .ssg_detector import SSGDetector
            detector = SSGDetector(config.hugo_project_path)
            ssg_type = detector.detect_ssg_type()
            
            format_name = "YAML" if config.frontmatter_format == FrontmatterFormat.YAML else "TOML"
            if ssg_type.value != "unknown":
                logger.info(f"Detected {ssg_type.value.title()} SSG - using {format_name} frontmatter")
            else:
                logger.info(f"SSG type unknown - defaulting to {format_name} frontmatter")
        except ImportError:
            format_name = "YAML" if config.frontmatter_format == FrontmatterFormat.YAML else "TOML"
            logger.info(f"Using {format_name} frontmatter")

    def convert(self) -> ConversionResult:
        """Perform the complete conversion process with progress display.
        
        Returns:
            Conversion result with statistics and any errors
        """
        from datetime import datetime
        
        try:
            print("🚀 Starting Obsidian to Hugo/Zola conversion...")
            start_time = datetime.now()
            
            # Prepare folder mappings
            folder_map = self._prepare_folder_map()
            print(f"📁 Mapped {len(folder_map)} source folders")
            
            # Clean destination directories if requested
            if self.config.clean_dest_dirs:
                print("🧹 Cleaning destination directories...")
                self._clean_destination_directories(folder_map)
                print("   ✅ Destination directories cleaned")
            
            # Parse notes and extract links with progress
            note_files_map = self._parse_notes_with_progress(folder_map)
            
            # Copy attachments with progress
            self._copy_attachments_with_progress()
            
            # Build internal link registry if enabled
            if self.internal_linker:
                content_dir = self.config.hugo_project_path / "content"
                self.internal_linker.build_link_registry(
                    note_files_map, 
                    content_dir, 
                    self.config.hugo_project_path
                )
                print(f"   🔗 Building internal link registry...")

            # Generate Hugo/Zola posts with progress
            self._generate_posts_with_progress(note_files_map, folder_map)
            
            # Collect final internal link statistics after posts are generated
            if self.internal_linker:
                stats = self.internal_linker.get_statistics()
                self.result.internal_links_added = stats["total_links_added"]
                print(f"   🔗 Added {self.result.internal_links_added} internal links")
            
            # Add warnings for unresolved links
            if self.link_processor.unresolved_links:
                self.result.warnings.extend(self.link_processor.unresolved_links)
            
            # Show final summary
            elapsed_time = datetime.now() - start_time
            print(f"\n🎉 Conversion completed in {elapsed_time.total_seconds():.1f}s")
            print(f"   📊 Notes processed: {len(note_files_map)}")
            print(f"   ✅ Notes converted: {self.result.converted_notes}")
            print(f"   📎 Attachments copied: {self.result.copied_attachments}")
            if self.internal_linker:
                print(f"   🔗 Internal links added: {self.result.internal_links_added}")
            if self.result.errors:
                print(f"   ⚠️  Errors encountered: {len(self.result.errors)}")
            if self.result.warnings:
                print(f"   ⚠️  Warnings: {len(self.result.warnings)}")
            
            logger.info(f"Conversion completed! {self.result.converted_notes} notes converted.")
            if self.internal_linker:
                logger.info(f"Added {self.result.internal_links_added} internal links.")
            
        except Exception as e:
            error_msg = f"Conversion failed: {e}"
            logger.error(error_msg)
            self.result.errors.append(error_msg)
            print(f"❌ Conversion failed: {e}")
            
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
            logger.info(f"📁 Using custom folder mappings: {len(self.config.folder_name_map)} mappings")
            # Use specified folder mappings
            for src_folder, dest_folder in self.config.folder_name_map.items():
                src_path = self.config.obsidian_vault_path / src_folder
                dest_folder = dest_folder.strip()
                if dest_folder:
                    dest_path = self.config.hugo_project_path / "content" / dest_folder
                else:
                    # Empty target_dir, put in content folder directly
                    dest_path = self.config.hugo_project_path / "content"
                
                # Ensure target directory exists
                try:
                    dest_path.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    raise RuntimeError(f"Failed to create target directory '{dest_path}': {e}")
                
                folder_map[src_path] = dest_path
                logger.debug(f"   Mapping: {src_path} -> {dest_path}")
        else:
            logger.info("📁 Using default mapping (entire vault)")
            # Use all folders in vault
            for folder_path in yield_subfolders(
                self.config.obsidian_vault_path,
                recursive=True,
                excludes=self.config.excluded_dirs,
            ):
                rel_path = folder_path.relative_to(self.config.obsidian_vault_path)
                # Use original format without slugify
                dest_path = self.config.hugo_project_path / "content" / rel_path
                
                # Ensure target directory exists
                try:
                    dest_path.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    raise RuntimeError(f"Failed to create target directory '{dest_path}': {e}")
                
                folder_map[folder_path] = dest_path
                logger.debug(f"   Mapping: {folder_path} -> {dest_path}")
                
            # Add vault root folder
            folder_map[self.config.obsidian_vault_path] = (
                self.config.hugo_project_path / "content" / "posts"
            )
            logger.debug(f"   Mapping: {self.config.obsidian_vault_path} -> {self.config.hugo_project_path / 'content' / 'posts'}")
            
        logger.debug(f"Final folder map: {folder_map}")
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

    @lru_cache(maxsize=1024)
    def _get_note_metadata_cached(self, note_path: Path) -> Optional[NoteMetadata]:
        """Cached version of note metadata retrieval.
        
        Args:
            note_path: Path to the note file
            
        Returns:
            Note metadata if successfully parsed, None otherwise
        """
        try:
            return self.note_parser.parse_note(note_path)
        except Exception as e:
            error_msg = f"Failed to parse note {note_path}: {e}"
            logger.error(error_msg)
            self.result.errors.append(error_msg)
            return None

    def _parse_notes(self, folder_map: Dict[Path, Path]) -> Dict[Path, Path]:
        """Parse Obsidian notes and extract metadata and links.

        Args:
            folder_map: Mapping of source to destination folders
            
        Returns:
            Dictionary mapping note paths to post paths
        """
        note_files_map = {}
        total_notes = 0
        
        # Count total notes first
        for note_folder, post_folder in folder_map.items():
            notes_in_folder = list(yield_files(note_folder, extensions=[".md"], recursive=False))
            total_notes += len(notes_in_folder)
            logger.debug(f"Folder {note_folder}: {len(notes_in_folder)} notes")
        
        logger.info(f"📋 Found {total_notes} total notes to process")
        processed = 0
        
        for note_folder, post_folder in folder_map.items():
            logger.debug(f"Processing folder: {note_folder}")
            for note_path in yield_files(
                note_folder, 
                extensions=[".md"], 
                recursive=False
            ):
                # Skip excluded directories
                if self._should_exclude_note(note_path):
                    logger.debug(f"Skipping excluded note: {note_path}")
                    continue
                    
                try:
                    logger.debug(f"Parsing note: {note_path}")
                    
                    # Parse note
                    note_content = note_path.read_text(encoding="utf-8")
                    note = frontmatter.loads(note_content)
                    logger.debug(f"Loaded note with {len(note.metadata)} metadata fields")
                    
                    # Extract metadata and store it (using cached version)
                    metadata = self._get_note_metadata_cached(note_path)
                    if metadata is None:
                        logger.warning(f"Could not parse metadata for: {note_path}")
                        continue
                    self.note_metadata_map[note_path] = metadata
                    
                    # Extract links from content
                    logger.debug(f"Extracting links from content ({len(note.content)} chars)")
                    self.link_processor.extract_links_from_content(
                        note.content, note_folder, str(note_path)
                    )
                    
                    # Extract links from frontmatter
                    logger.debug("Extracting links from frontmatter")
                    self.link_processor.extract_links_from_frontmatter(
                        note.metadata, note_folder, str(note_path)
                    )
                    
                    # Generate post path
                    post_path = self._generate_post_path(note, note_path, post_folder)
                    note_files_map[note_path] = post_path
                    logger.debug(f"Generated post path: {post_path}")
                    
                    processed += 1
                    if processed % 10 == 0:
                        logger.debug(f"Processed {processed}/{total_notes} notes")
                    
                except Exception as e:
                    error_msg = f"Failed to parse note {note_path}: {e}"
                    logger.error(error_msg)
                    logger.debug(f"Error details: {type(e).__name__}: {e}")
                    self.result.errors.append(error_msg)
                    
        logger.info(f"✅ Successfully parsed {len(note_files_map)} notes")
        return note_files_map

    def _parse_notes_with_progress(self, folder_map: Dict[Path, Path]) -> Dict[Path, Path]:
        """Parse Obsidian notes with progress display.

        Args:
            folder_map: Mapping of source to destination folders
            
        Returns:
            Dictionary mapping note paths to post paths
        """
        note_files_map = {}
        
        # Count total notes for progress
        total_notes = 0
        for note_folder, post_folder in folder_map.items():
            total_notes += len(list(yield_files(note_folder, extensions=[".md"], recursive=False)))
        
        if total_notes == 0:
            print("📋 No notes found to parse")
            return note_files_map
            
        print(f"📋 Parsing {total_notes} notes...")
        processed = 0
        
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
                    
                    # Extract metadata and store it
                    metadata = self._process_metadata(note.metadata, note_path)
                    self.note_metadata_map[note_path] = metadata
                    
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
                    
                    processed += 1
                    if processed % 10 == 0 or processed == total_notes:
                        progress = (processed / total_notes) * 100
                        print(f"   📊 Progress: {processed}/{total_notes} ({progress:.1f}%)", end="\r")
                        if processed == total_notes:
                            print()  # New line after completion
                    
                except Exception as e:
                    error_msg = f"Failed to parse note {note_path}: {e}"
                    logger.error(error_msg)
                    self.result.errors.append(error_msg)
                    
        print(f"   ✅ Parsed {len(note_files_map)} notes successfully")
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
        if slug:
            # Clean slug from metadata by removing markdown link syntax
            slug = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', str(slug))
            slug = re.sub(r'[\[\]\(\)#]', '', slug)
            slug = slugify_path(add_spaces_to_content(slug))
        else:
            filename = note_path.stem
            # Clean filename by removing markdown link syntax before slugifying
            clean_filename = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', filename)
            clean_filename = re.sub(r'[\[\]\(\)#]', '', clean_filename)
            slug = slugify_path(add_spaces_to_content(clean_filename))
        
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
        
        # Batch process attachments to reduce I/O
        file_operations = []
        processed_paths = set()
        
        for link in self.link_processor.inline_links.values():
            if link.link_type != LinkType.FILE or not link.source_path:
                continue
                
            # Skip duplicates
            cache_key = str(link.source_path)
            if cache_key in processed_paths:
                continue
            processed_paths.add(cache_key)
                
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
                file_operations.append((link.source_path, dest_path, dest_filename))
                
            except Exception as e:
                error_msg = f"Failed to prepare attachment {link.source_path}: {e}"
                logger.error(error_msg)
                self.result.errors.append(error_msg)
        
        # Execute batch file operations
        for source_path, dest_path, dest_filename in file_operations:
            try:
                shutil.copyfile(source_path, dest_path)
                # Update link with destination filename
                for link in self.link_processor.inline_links.values():
                    if link.source_path == source_path:
                        link.dest_filename = dest_filename
                self.result.copied_attachments += 1
                
            except Exception as e:
                error_msg = f"Failed to copy attachment {source_path}: {e}"
                logger.error(error_msg)
                self.result.errors.append(error_msg)

    def _copy_attachments_with_progress(self) -> None:
        """Copy attachment files to destination with progress display.
        
        This includes images, videos, PDFs, and other files referenced by links.
        """
        if not self.link_processor.inline_links:
            print("📎 No attachments to copy")
            return
            
        # Collect unique attachments to avoid duplicates
        unique_attachments = {}
        for link in self.link_processor.inline_links.values():
            if link.link_type == LinkType.FILE and link.source_path:
                unique_attachments[str(link.source_path)] = link
        
        total_attachments = len(unique_attachments)
        if total_attachments == 0:
            print("📎 No attachments to copy")
            return
            
        print(f"📎 Copying {total_attachments} attachments...")
        
        # Determine destination directory
        if self.config.attachment_target_path:
            dest_dir = self.config.attachment_target_path
            if not dest_dir.is_absolute():
                dest_dir = dest_dir.resolve()
        else:
            dest_dir = self.config.hugo_project_path / "static"
            for part in self.config.attachment_folder_name.split("/"):
                dest_dir = dest_dir / part
                
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Pre-calculate all filenames
        file_operations = []
        for link in unique_attachments.values():
            try:
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
                file_operations.append((link.source_path, dest_path, dest_filename))
                
            except Exception as e:
                error_msg = f"Failed to prepare attachment {link.source_path}: {e}"
                logger.error(error_msg)
                self.result.errors.append(error_msg)
        
        # Execute batch operations with progress
        for i, (source_path, dest_path, dest_filename) in enumerate(file_operations, 1):
            try:
                shutil.copyfile(source_path, dest_path)
                
                # Update all links pointing to this source
                for link in self.link_processor.inline_links.values():
                    if link.source_path == source_path:
                        link.dest_filename = dest_filename
                
                self.result.copied_attachments += 1
                
                if i % 5 == 0 or i == total_attachments:
                    progress = (i / total_attachments) * 100
                    print(f"   📊 Progress: {i}/{total_attachments} ({progress:.1f}%)", end="\r")
                    if i == total_attachments:
                        print()  # New line after completion
                
            except Exception as e:
                error_msg = f"Failed to copy attachment {source_path}: {e}"
                logger.error(error_msg)
                self.result.errors.append(error_msg)
                
        print(f"   ✅ Copied {self.result.copied_attachments} attachments successfully")

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

    def _generate_posts_with_progress(self, note_files_map: Dict[Path, Path], folder_map: Dict[Path, Path]) -> None:
        """Generate Hugo/Zola posts from Obsidian notes with progress display.
        
        Args:
            note_files_map: Mapping of note paths to post paths
            folder_map: Mapping of source to destination folders
        """
        # Check for linked notes that aren't being converted
        self._validate_note_links(note_files_map, folder_map)
        
        # Count total notes to convert
        total_notes = len([path for path in note_files_map.values() if path])
        
        if total_notes == 0:
            print("📝 No notes to convert")
            return
            
        print(f"📝 Converting {total_notes} notes...")
        
        processed = 0
        for note_path, post_path in note_files_map.items():
            if not post_path:  # Skip notes that shouldn't be converted
                continue
                
            try:
                self._convert_single_note(note_path, post_path, note_files_map)
                self.result.converted_notes += 1
                
                processed += 1
                if processed % 5 == 0 or processed == total_notes:
                    progress = (processed / total_notes) * 100
                    print(f"   📊 Progress: {processed}/{total_notes} ({progress:.1f}%)", end="\r")
                    if processed == total_notes:
                        print()  # New line after completion
                
            except Exception as e:
                error_msg = f"Failed to convert note {note_path}: {e}"
                logger.error(error_msg)
                self.result.errors.append(error_msg)
        
        print(f"   ✅ Converted {self.result.converted_notes} notes successfully")

    def _build_internal_link_registry(self, notes_metadata: Dict[Path, NoteMetadata]) -> None:
        """Build registry of internal links for cross-referencing.
        
        Args:
            notes_metadata: Dictionary of note paths to their metadata
        """
        # Build registry from note metadata
        self.internal_linker.build_link_registry(notes_metadata)
        
        # Apply internal links to content
        for note_path, metadata in notes_metadata.items():
            if metadata.link_words:
                # Update content with internal links
                metadata.content = self.internal_linker.apply_internal_links(
                    metadata.content, note_path, metadata
                )

    def _build_internal_link_registry_with_progress(self, notes_metadata: Dict[Path, NoteMetadata]) -> None:
        """Build registry of internal links for cross-referencing with progress display.
        
        Args:
            notes_metadata: Dictionary of note paths to their metadata
        """
        total_notes = len(notes_metadata)
        if total_notes == 0:
            print("🔗 No internal links to process")
            return
            
        print(f"🔗 Building internal link registry for {total_notes} notes...")
        
        # Build registry from note metadata
        self.internal_linker.build_link_registry(notes_metadata)
        
        # Apply internal links to content
        processed = 0
        for note_path, metadata in notes_metadata.items():
            if metadata.link_words:
                # Update content with internal links
                metadata.content = self.internal_linker.apply_internal_links(
                    metadata.content, note_path, metadata
                )
            
            processed += 1
            if processed % 10 == 0 or processed == total_notes:
                progress = (processed / total_notes) * 100
                print(f"   📊 Progress: {processed}/{total_notes} ({progress:.1f}%)", end="\r")
                if processed == total_notes:
                    print()  # New line after completion
        
        # Show statistics
        stats = self.internal_linker.get_statistics()
        print(f"   ✅ Registered {stats['total_link_words']} link words, added {stats['total_links_added']} internal links")

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
        logger.debug(f"📝 Converting note: {note_path.name}")
        
        # Get pre-parsed metadata
        metadata = self.note_metadata_map.get(note_path)
        if not metadata:
            logger.error(f"No metadata found for {note_path}")
            return
            
        logger.debug(f"   Title: {metadata.title}")
        logger.debug(f"   Tags: {metadata.tags}")
        logger.debug(f"   Slug: {metadata.slug}")
        
        try:
            # Read and parse note content only
            logger.debug(f"   Reading note content ({note_path.stat().st_size} bytes)")
            note_content = note_path.read_text(encoding="utf-8")
            logger.debug(f"   Raw content sample: {repr(note_content[:500])}")
            note = frontmatter.loads(note_content)
            logger.debug(f"   Parsed frontmatter with {len(note.metadata)} fields")
            logger.debug(f"   Content after frontmatter: {repr(note.content[:200])}...")
            
            # Replace links in content
            logger.debug(f"   Processing links in content ({len(note.content)} chars)")
            processed_content = self.link_processor.replace_links_in_content(
                note.content,
                note_files_map,
                self.config.hugo_project_path,
                self.config.attachment_folder_name,
                self.config,
            )
            logger.debug(f"   Content processing complete")
            
            # Replace links in frontmatter metadata
            logger.debug("   Processing links in frontmatter")
            processed_metadata_dict = self.link_processor.replace_links_in_frontmatter(
                metadata.to_dict(),
                note_files_map,
                self.config.hugo_project_path,
                self.config.attachment_folder_name,
                self.config,
            )
            logger.debug(f"   Frontmatter processing complete")
            
            # Handle language field based on frontmatter format
            if metadata.lang:
                logger.debug(f"   Processing language: {metadata.lang}")
                if self.config.frontmatter_format == FrontmatterFormat.YAML:
                    # For Hugo (YAML): use languageCode, not lang
                    processed_metadata_dict["languageCode"] = metadata.lang
                    # Remove lang if it exists from original metadata
                    processed_metadata_dict.pop("lang", None)
                else:
                    # For Zola (TOML): use lang, not languageCode
                    processed_metadata_dict["lang"] = metadata.lang
                    # Remove languageCode if it exists from original metadata
                    processed_metadata_dict.pop("languageCode", None)
            
            # Apply internal links if enabled
            if self.internal_linker:
                logger.debug("   Applying internal links")
                processed_content = self.internal_linker.apply_internal_links(
                    processed_content,
                    note_path,
                    metadata
                )
                logger.debug("   Internal links applied")
            
            # Create post with processed data
            post = frontmatter.Post(processed_content, **processed_metadata_dict)
            
            # Generate output based on frontmatter format
            logger.debug(f"   Generating output with {self.config.frontmatter_format} format")
            if self.config.frontmatter_format == FrontmatterFormat.TOML:
                output = frontmatter.dumps(post, handler=CustomTOMLHandler())
            else:
                output = frontmatter.dumps(post)
            
            # Ensure destination directory exists and write file
            logger.debug(f"   Writing to: {post_path}")
            post_path.parent.mkdir(parents=True, exist_ok=True)
            post_path.write_text(output, encoding="utf-8")
            logger.debug(f"   ✅ Successfully converted: {note_path.name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to convert note {note_path}: {e}")
            logger.debug(f"Error details: {type(e).__name__}: {e}")
            logger.debug(f"Stack trace:", exc_info=True)
            raise

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
        # Try to get language from 'lang' or 'languageCode' fields
        metadata.lang = (
            raw_metadata.get("lang") or 
            raw_metadata.get("languageCode")
        )
        
        # Process link_words for internal linking
        link_words = NoteMetadata.extract_link_words(raw_metadata)
        if isinstance(link_words, str):
            metadata.link_words = [link_words]
        elif isinstance(link_words, list):
            metadata.link_words = link_words
        else:
            metadata.link_words = []
        
        return metadata
