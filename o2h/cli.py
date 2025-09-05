"""Command-line interface for O2H converter."""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import __title__, __version__
from .converter import ObsidianToHugoConverter
from .logger import setup_logger
from .models import ConversionConfig, FrontmatterFormat


class FolderMappingAction(argparse.Action):
    """Custom action for handling --folder arguments."""
    
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        # Accept 1 or 2 arguments
        if nargs is None:
            nargs = '+'
        super().__init__(option_strings, dest, nargs=nargs, **kwargs)
    
    def __call__(self, parser, namespace, values, option_string=None):
        if not hasattr(namespace, self.dest) or getattr(namespace, self.dest) is None:
            setattr(namespace, self.dest, [])
        
        # Validate number of arguments
        if len(values) == 1:
            # Single argument: source directory, target is same as source
            source_dir = values[0].strip()
            target_dir = source_dir
        elif len(values) == 2:
            # Two arguments: source and target directories
            source_dir = values[0].strip()
            target_dir = values[1].strip() if values[1].strip() else ""
            # Allow empty target_dir, will use default content path
        else:
            raise argparse.ArgumentTypeError(
                f"--folder expects 1 or 2 arguments, got {len(values)}: {values}"
            )
        
        # Validate arguments
        if not source_dir:
            raise argparse.ArgumentTypeError("Source directory name cannot be empty")
        # Allow empty target_dir, will use default content path later
        
        # Store as tuple
        getattr(namespace, self.dest).append((source_dir, target_dir))


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser.
    
    Returns:
        Configured ArgumentParser instance
    """
    description = f"""{__title__} ver {__version__}

A markdown format transpiler for Obsidian to Hugo/Zola.
Convert Obsidian vault notes to Hugo or Zola content posts.

Features:
  - Smart link processing for notes, attachments, and anchors
  - Automatic internal linking based on frontmatter link_words
  - Multi-language support and flexible folder mapping
  - Support for both Hugo (YAML) and Zola (TOML) frontmatter formats

Examples:
  # Convert for Hugo (YAML frontmatter - default)
  o2h "/path/to/obsidian/vault" "/path/to/hugo/project" --folder blogs

  # Convert for Zola (TOML frontmatter)
  o2h "/path/to/obsidian/vault" "/path/to/zola/project" --folder blogs --frontmatter-format toml

  # Convert specific folders with custom mappings (new recommended syntax)
  o2h "/path/to/obsidian/vault" "/path/to/hugo/project" \\
      --folder "blogs" "posts" \\
      --folder "notes" "articles" \\
      --folder "tutorials"

  # Legacy syntax (still supported but deprecated)
  o2h "/path/to/obsidian/vault" "/path/to/hugo/project" --folders "blogs>posts notes>articles"
  
  # Use custom attachment path (absolute path)
  o2h "/path/to/obsidian/vault" "/path/to/hugo/project" --folder blogs --attachment-target-path "/var/www/static/images" --attachment-host "cdn.example.com"
  
  # Use custom attachment path (relative to current directory)
  o2h "/path/to/obsidian/vault" "/path/to/hugo/project" --folder blogs --attachment-target-path "media/uploads" --attachment-host "assets.mysite.com"
  
  # Disable internal linking feature
  o2h "/path/to/obsidian/vault" "/path/to/hugo/project" --folder blogs --disable-internal-linking
"""

    parser = argparse.ArgumentParser(
        prog=__title__.lower(),
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="For more information, visit: https://github.com/nodewee/o2h"
    )

    # Required arguments
    parser.add_argument(
        "obsidian_vault",
        help="Path to Obsidian vault directory",
        type=Path,
    )
    
    parser.add_argument(
        "target_project",
        help="Path to Hugo/Zola project directory",
        type=Path,
    )

    # Folder mapping arguments (new and legacy)
    folder_group = parser.add_mutually_exclusive_group()
    
    folder_group.add_argument(
        "--folder",
        action=FolderMappingAction,
        dest="folder_mappings",
        help="""Specify a folder to convert with optional target mapping.
        Can be used multiple times. Usage:
          --folder "source-dir"                    (target dir same as source)
          --folder "source-dir" "target-dir"      (custom target dir)
        Examples:
          --folder "blogs" "posts"
          --folder "notes" "articles" 
          --folder "tutorials"
        """,
        metavar=("SOURCE", "TARGET"),
    )
    
    folder_group.add_argument(
        "--folders",
        type=str,
        help="""[DEPRECATED] Specify folders to convert with optional target mappings.
        Format: "source1>target1 source2>target2"
        Use --folder instead for better syntax.
        Example: --folders "blogs>posts notes>articles"
        """,
        metavar="MAPPING",
    )

    parser.add_argument(
        "--attachment-folder",
        help="Target folder name for attachments (default: attachments)",
        type=str,
        default="attachments",
        metavar="NAME",
    )

    parser.add_argument(
        "--attachment-target-path",
        help="Target path for attachments (absolute or relative path). If specified, --attachment-folder is ignored.",
        type=str,
        metavar="PATH",
    )

    parser.add_argument(
        "--attachment-host",
        help="Host domain for attachments when using --attachment-target-path. Format: 'example.com' or 'cdn.example.com' (https:// will be auto-added)",
        type=str,
        metavar="HOST",
    )

    parser.add_argument(
        "--md5-attachment",
        help="Use MD5 hash as attachment filenames",
        action="store_true",
    )

    parser.add_argument(
        "--clean-dest",
        help="Clean target directories before conversion",
        action="store_true",
    )

    parser.add_argument(
        "--frontmatter-format",
        help="Frontmatter format (auto-detect if not specified)",
        type=str,
        choices=["yaml", "toml"],
        default=None,
        metavar="FORMAT",
    )

    parser.add_argument(
        "--disable-internal-linking",
        help="Disable automatic internal linking based on link_words",
        action="store_true",
    )

    parser.add_argument(
        "--internal-link-max",
        help="Maximum internal links per word per article (default: 1)",
        type=int,
        default=1,
        metavar="N",
    )

    parser.add_argument(
        "--verbose", "-v",
        help="Enable verbose logging",
        action="store_true",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"{__title__} {__version__}"
    )

    return parser


def parse_folder_mappings(folders_str: Optional[str]) -> Dict[str, str]:
    """Parse folder mapping string into dictionary (legacy function).
    
    Args:
        folders_str: Folder mapping string (e.g., "blogs>posts notes>articles")
        
    Returns:
        Dictionary mapping source folders to target folders
    """
    if not folders_str:
        return {}

    mappings = {}
    
    for item in folders_str.split():
        item = item.strip()
        if not item:
            continue

        if ">" in item:
            parts = item.split(">", 1)
            if len(parts) == 2:
                source, target = parts
                mappings[source.strip()] = target.strip()
            else:
                mappings[item] = item
        else:
            mappings[item] = item

    return mappings


def parse_folder_mapping_list(folder_list: Optional[List[Tuple[str, str]]]) -> Dict[str, str]:
    """Parse folder mapping list into dictionary.
    
    Args:
        folder_list: List of (source, target) tuples
        
    Returns:
        Dictionary mapping source folders to target folders
    """
    if not folder_list:
        return {}
    
    mappings = {}
    for source, target in folder_list:
        if source in mappings:
            print(f"Warning: Duplicate source folder '{source}', using latest mapping: {source} -> {target}", file=sys.stderr)
        mappings[source] = target
    
    return mappings


def get_folder_mappings_from_args(args: argparse.Namespace) -> Dict[str, str]:
    """Extract folder mappings from command line arguments.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Dictionary mapping source folders to target folders
    """
    # Check if new --folder arguments were used
    if hasattr(args, 'folder_mappings') and args.folder_mappings:
        return parse_folder_mapping_list(args.folder_mappings)
    
    # Fall back to legacy --folders argument
    if args.folders:
        print("Warning: --folders is deprecated. Use --folder instead for better syntax.", file=sys.stderr)
        return parse_folder_mappings(args.folders)
    
    # No folder mappings specified
    return {}


def validate_paths(obsidian_vault: Path, target_project: Path) -> None:
    """Validate input paths.
    
    Args:
        obsidian_vault: Path to Obsidian vault
        target_project: Path to target project
        
    Raises:
        SystemExit: If paths are invalid
    """
    if not obsidian_vault.exists():
        print(f"Error: Obsidian vault not found: {obsidian_vault}", file=sys.stderr)
        sys.exit(1)
        
    if not obsidian_vault.is_dir():
        print(f"Error: Obsidian vault path is not a directory: {obsidian_vault}", file=sys.stderr)
        sys.exit(1)
        
    if not target_project.exists():
        print(f"Error: Target project not found: {target_project}", file=sys.stderr)
        sys.exit(1)
        
    if not target_project.is_dir():
        print(f"Error: Target project path is not a directory: {target_project}", file=sys.stderr)
        sys.exit(1)


def create_config_from_args(args: argparse.Namespace) -> ConversionConfig:
    """Create ConversionConfig from parsed arguments.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        ConversionConfig instance
    """
    folder_mappings = get_folder_mappings_from_args(args)
    
    # Convert frontmatter format string to enum (None for auto-detection)
    frontmatter_format = FrontmatterFormat(args.frontmatter_format) if args.frontmatter_format else None
    
    # Validate attachment parameters
    if args.attachment_target_path and not args.attachment_host:
        print("Error: --attachment-host is required when using --attachment-target-path", file=sys.stderr)
        sys.exit(1)
    
    # Validate attachment host format
    if args.attachment_host:
        if not args.attachment_target_path:
            print("Error: --attachment-host can only be used with --attachment-target-path", file=sys.stderr)
            sys.exit(1)
        
        # Basic domain validation
        host = args.attachment_host.strip()
        if not host or host.startswith("http") or "/" in host:
            print("Error: --attachment-host must be a domain name (e.g., 'example.com' or 'cdn.example.com')", file=sys.stderr)
            sys.exit(1)
    
    return ConversionConfig(
        obsidian_vault_path=args.obsidian_vault.resolve(),
        hugo_project_path=args.target_project.resolve(),
        attachment_folder_name=args.attachment_folder,
        attachment_target_path=Path(args.attachment_target_path) if args.attachment_target_path else None,
        attachment_host=args.attachment_host,
        folder_name_map=folder_mappings,
        clean_dest_dirs=args.clean_dest,
        md5_attachment=args.md5_attachment,
        frontmatter_format=frontmatter_format,
        enable_internal_linking=not args.disable_internal_linking,
        internal_link_max_per_article=args.internal_link_max,
    )


def main() -> None:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    import logging
    logger = setup_logger(level=getattr(logging, log_level))
    
    try:
        # Validate paths
        validate_paths(args.obsidian_vault, args.target_project)
        
        # Create configuration
        config = create_config_from_args(args)
        
        # Run conversion
        converter = ObsidianToHugoConverter(config)
        result = converter.convert()
        
        # Report results
        if result.success:
            print(f"\n✅ Conversion completed successfully!")
            print(f"   📝 {result.converted_notes} notes converted")
            print(f"   📎 {result.copied_attachments} attachments copied")
            if result.internal_links_added > 0:
                print(f"   🔗 {result.internal_links_added} internal links added")
            
            if result.warnings:
                print(f"\n⚠️  {len(result.warnings)} warnings:")
                for warning in result.warnings:
                    print(f"   • {warning}")
        else:
            print(f"\n❌ Conversion failed with {len(result.errors)} errors:")
            for error in result.errors:
                print(f"   • {error}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Conversion interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()