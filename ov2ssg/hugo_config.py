"""Hugo configuration reader and permalink utilities.

Adds lightweight in-memory caching to avoid repeatedly parsing project
configuration files and recomputing permalink patterns.
"""

import yaml
import toml
from pathlib import Path
from typing import Optional, Dict, Any, Tuple


class HugoConfigReader:
    """Reads and parses Hugo configuration files."""
    
    CONFIG_FILENAMES = ["config.yml", "config.yaml", "config.toml"]
    # In-memory caches keyed by resolved project path
    _config_cache: Dict[str, Optional[Dict[str, Any]]] = {}
    _permalink_cache: Dict[Tuple[str, str], str] = {}
    
    @classmethod
    def read_config(cls, hugo_project_path: Path) -> Optional[Dict[str, Any]]:
        """Read Hugo configuration from the project directory.
        
        Args:
            hugo_project_path: Path to the Hugo project directory
            
        Returns:
            Configuration dictionary or None if no config found
        """
        key = str(hugo_project_path.resolve())
        if key in cls._config_cache:
            return cls._config_cache[key]

        for config_filename in cls.CONFIG_FILENAMES:
            config_path = hugo_project_path / config_filename
            if config_path.exists():
                try:
                    if config_filename.endswith('.toml'):
                        config = toml.loads(config_path.read_text(encoding='utf-8'))
                        cls._config_cache[key] = config
                        return config
                    else:  # .yml or .yaml
                        config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
                        cls._config_cache[key] = config
                        return config
                except (OSError, yaml.YAMLError, toml.TomlDecodeError) as e:
                    # Continue to try other formats if parsing fails
                    continue
        cls._config_cache[key] = None
        return None
    
    @classmethod
    def get_permalink_pattern(cls, hugo_project_path: Path, content_type: str = "posts") -> str:
        """Get the permalink pattern for the specified content type.
        
        Args:
            hugo_project_path: Path to the Hugo project directory
            content_type: Type of content (e.g., "posts", "articles")
            
        Returns:
            Permalink pattern string, defaults to "/posts/:slug" if not found
        """
        cache_key = (str(hugo_project_path.resolve()), content_type)
        if cache_key in cls._permalink_cache:
            return cls._permalink_cache[cache_key]

        config = cls.read_config(hugo_project_path)
        if not config:
            cls._permalink_cache[cache_key] = "/posts/:slug"
            return cls._permalink_cache[cache_key]
        
        # Get permalinks configuration
        permalinks = config.get("permalinks", {})
        if not isinstance(permalinks, dict):
            cls._permalink_cache[cache_key] = "/posts/:slug"
            return cls._permalink_cache[cache_key]
        
        # Get the specific content type pattern
        pattern = permalinks.get(content_type)
        if not pattern or not isinstance(pattern, str):
            cls._permalink_cache[cache_key] = "/posts/:slug"
            return cls._permalink_cache[cache_key]
        
        cls._permalink_cache[cache_key] = pattern.strip()
        return cls._permalink_cache[cache_key]
    
    @classmethod
    def generate_url_from_pattern(
        cls, 
        pattern: str, 
        slug: str, 
        date: Optional[str] = None,
        title: Optional[str] = None,
        section: Optional[str] = None
    ) -> str:
        """Generate URL from a Hugo permalink pattern.
        
        Args:
            pattern: The permalink pattern (e.g., "/:section/:slug/")
            slug: The slug to use in the URL
            date: Optional date string or date object for date-based patterns
            title: Optional title for title-based patterns  
            section: Optional section name
            
        Returns:
            Generated URL string
        """
        url = pattern
        
        # Replace common Hugo placeholders
        replacements = {
            ":slug": slug,
            ":title": title or slug,
            ":section": section or "posts",
        }
        
        # Handle date-based placeholders
        if date:
            try:
                from datetime import datetime, date as dt_date
                
                # Handle different date formats
                dt = None
                if hasattr(date, 'strftime'):  # datetime or date object
                    dt = date
                elif isinstance(date, str):
                    # Handle string dates, including those with time
                    date_str = date.split('T')[0] if 'T' in date else date
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                
                if dt:
                    replacements.update({
                        ":year": str(dt.year),
                        ":month": f"{dt.month:02d}",
                        ":day": f"{dt.day:02d}",
                        ":yearday": str(dt.timetuple().tm_yday),
                    })
            except (ValueError, AttributeError):
                pass
        
        # Apply replacements
        for placeholder, value in replacements.items():
            url = url.replace(placeholder, str(value))
        
        # Clean up the URL
        url = url.replace("//", "/")
        
        # Remove trailing slash if it exists and ensure leading slash
        url = url.rstrip("/")
        if not url.startswith("/"):
            url = "/" + url
            
        return url