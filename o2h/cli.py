"""Command-line interface for O2H converter."""

import argparse
import sys
from pathlib import Path
from typing import Dict, Optional

from . import __title__, __version__
from .converter import ObsidianToHugoConverter
from .logger import setup_logger
from .models import ConversionConfig, FrontmatterFormat


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser.
    
    Returns:
        Configured ArgumentParser instance
    """
    description = f"""{__title__} ver {__version__}

A markdown format transpiler for Obsidian to Hugo/Zola.
Convert Obsidian vault notes to Hugo or Zola content posts.

Examples:
  # Convert for Hugo (YAML frontmatter - default)
  o2h "/path/to/obsidian/vault" "/path/to/hugo/project" --folders blogs

  # Convert for Zola (TOML frontmatter)
  o2h "/path/to/obsidian/vault" "/path/to/zola/project" --folders blogs --frontmatter-format toml

  # Convert specific folders with custom mappings
  o2h "/path/to/obsidian/vault" "/path/to/hugo/project" --folders "blogs>posts notes>articles"
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

    # Optional arguments
    parser.add_argument(
        "--folders",
        type=str,
        help="""Specify folders to convert with optional target mappings.
        Format: "source1>target1 source2>target2"
        If no target specified, uses source name.
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
        help="Frontmatter format (default: yaml for Hugo, toml for Zola)",
        type=str,
        choices=["yaml", "toml"],
        default="yaml",
        metavar="FORMAT",
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
    """Parse folder mapping string into dictionary.
    
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
            source, target = item.split(">", 1)
            mappings[source.strip()] = target.strip()
        else:
            mappings[item] = item

    return mappings


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
    folder_mappings = parse_folder_mappings(args.folders)
    
    # Convert frontmatter format string to enum
    frontmatter_format = FrontmatterFormat(args.frontmatter_format)
    
    return ConversionConfig(
        obsidian_vault_path=args.obsidian_vault.resolve(),
        hugo_project_path=args.target_project.resolve(),
        attachment_folder_name=args.attachment_folder,
        folder_name_map=folder_mappings,
        clean_dest_dirs=args.clean_dest,
        md5_attachment=args.md5_attachment,
        frontmatter_format=frontmatter_format,
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