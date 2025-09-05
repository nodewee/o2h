"""Zola configuration reader and URL utilities."""

import toml
from pathlib import Path
from typing import Optional, Dict, Any


class ZolaConfigReader:
    """Reads and parses Zola configuration files."""
    
    CONFIG_FILENAME = "config.toml"
    
    @classmethod
    def read_config(cls, zola_project_path: Path) -> Optional[Dict[str, Any]]:
        """Read Zola configuration from the project directory.
        
        Args:
            zola_project_path: Path to the Zola project directory
            
        Returns:
            Configuration dictionary or None if no config found
        """
        config_path = zola_project_path / cls.CONFIG_FILENAME
        if not config_path.exists():
            return None
            
        try:
            return toml.loads(config_path.read_text(encoding='utf-8'))
        except (OSError, toml.TomlDecodeError) as e:
            return None
    
    @classmethod
    def get_base_url(cls, zola_project_path: Path) -> str:
        """Get the base URL from Zola configuration.
        
        Args:
            zola_project_path: Path to the Zola project directory
            
        Returns:
            Base URL string, defaults to "/" if not found
        """
        config = cls.read_config(zola_project_path)
        if not config:
            return "/"
        
        base_url = config.get("base_url", "/")
        return base_url.rstrip("/") + "/"
    
    @classmethod
    def get_taxonomies(cls, zola_project_path: Path) -> Dict[str, str]:
        """Get taxonomies configuration from Zola.
        
        Args:
            zola_project_path: Path to the Zola project directory
            
        Returns:
            Dictionary mapping taxonomy names to their plural forms
        """
        config = cls.read_config(zola_project_path)
        if not config:
            return {}
        
        taxonomies = config.get("taxonomies", [])
        if isinstance(taxonomies, list):
            taxonomy_map = {}
            for item in taxonomies:
                if isinstance(item, dict):
                    name = item.get("name", "")
                    plural = item.get("name", "") + "s"
                    if name:
                        taxonomy_map[name] = plural
                elif isinstance(item, str):
                    taxonomy_map[item] = item + "s"
            return taxonomy_map
        
        return {}
    
    @classmethod
    def generate_url_from_path(
        cls,
        zola_project_path: Path,
        post_path: Path,
        content_dir: Path,
        slug: Optional[str] = None,
        lang: Optional[str] = None
    ) -> str:
        """Generate URL for a post in Zola format.
        
        Args:
            zola_project_path: Path to the Zola project directory
            post_path: Path to the post file
            content_dir: Content directory path
            slug: Optional slug override
            lang: Optional language prefix
            
        Returns:
            Generated URL string for Zola
        """
        # Get relative path from content directory
        rel_path = post_path.relative_to(content_dir)
        
        # Remove file extension
        url_path = str(rel_path.with_suffix(""))
        
        # Handle slug override
        if slug:
            # Replace the last part with slug
            parts = url_path.split("/")
            if parts:
                parts[-1] = slug
            url_path = "/".join(parts)
        
        # Clean up the URL
        url_path = url_path.replace("//", "/")
        
        # Ensure leading slash
        if not url_path.startswith("/"):
            url_path = "/" + url_path
            
        # Add language prefix if specified
        if lang:
            if url_path.startswith("/"):
                url_path = f"/{lang}{url_path}"
            else:
                url_path = f"/{lang}/{url_path}"
        
        # Ensure trailing slash for internal links
        if not url_path.endswith("/"):
            url_path = url_path + "/"
            
        return url_path