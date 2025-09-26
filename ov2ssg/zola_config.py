"""Zola configuration reader and URL utilities with simple caching."""

import toml
from pathlib import Path
from typing import Optional, Dict, Any


class ZolaConfigReader:
    """Reads and parses Zola configuration files."""
    
    CONFIG_FILENAME = "config.toml"
    _config_cache: Dict[str, Optional[Dict[str, Any]]] = {}
    _base_url_cache: Dict[str, str] = {}
    _taxonomies_cache: Dict[str, Dict[str, str]] = {}
    
    @classmethod
    def read_config(cls, zola_project_path: Path) -> Optional[Dict[str, Any]]:
        """Read Zola configuration from the project directory.
        
        Args:
            zola_project_path: Path to the Zola project directory
            
        Returns:
            Configuration dictionary or None if no config found
        """
        key = str(zola_project_path.resolve())
        if key in cls._config_cache:
            return cls._config_cache[key]

        config_path = zola_project_path / cls.CONFIG_FILENAME
        if not config_path.exists():
            cls._config_cache[key] = None
            return None
            
        try:
            config = toml.loads(config_path.read_text(encoding='utf-8'))
            cls._config_cache[key] = config
            return config
        except (OSError, toml.TomlDecodeError) as e:
            cls._config_cache[key] = None
            return None
    
    @classmethod
    def get_base_url(cls, zola_project_path: Path) -> str:
        """Get the base URL from Zola configuration.
        
        Args:
            zola_project_path: Path to the Zola project directory
            
        Returns:
            Base URL string, defaults to "/" if not found
        """
        key = str(zola_project_path.resolve())
        if key in cls._base_url_cache:
            return cls._base_url_cache[key]

        config = cls.read_config(zola_project_path)
        if not config:
            cls._base_url_cache[key] = "/"
            return cls._base_url_cache[key]
        
        base_url = config.get("base_url", "/")
        result = base_url.rstrip("/") + "/"
        cls._base_url_cache[key] = result
        return result
    
    @classmethod
    def get_taxonomies(cls, zola_project_path: Path) -> Dict[str, str]:
        """Get taxonomies configuration from Zola.
        
        Args:
            zola_project_path: Path to the Zola project directory
            
        Returns:
            Dictionary mapping taxonomy names to their plural forms
        """
        key = str(zola_project_path.resolve())
        if key in cls._taxonomies_cache:
            return cls._taxonomies_cache[key]

        config = cls.read_config(zola_project_path)
        if not config:
            cls._taxonomies_cache[key] = {}
            return cls._taxonomies_cache[key]
        
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
            cls._taxonomies_cache[key] = taxonomy_map
            return cls._taxonomies_cache[key]
        
        cls._taxonomies_cache[key] = {}
        return cls._taxonomies_cache[key]
    
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