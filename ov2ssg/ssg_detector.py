"""SSG (Static Site Generator) type detection module.

This module provides functionality to automatically detect the type of SSG
(Hugo or Zola) based on configuration files and frontmatter format.
"""

import re
from enum import Enum
from pathlib import Path
from typing import Optional, Set

import yaml
import toml


class SSGType(Enum):
    """Supported Static Site Generator types."""
    HUGO = "hugo"
    ZOLA = "zola"
    UNKNOWN = "unknown"


class SSGDetector:
    """Detects the type of Static Site Generator based on project structure."""
    
    # Configuration file names to check
    CONFIG_FILES = ["config.yml", "config.yaml", "config.toml"]
    
    # Hugo-specific indicators in config files
    HUGO_INDICATORS = {"hugo", "hugoversion", "baseurl", "languagecode", "theme"}
    
    # Zola-specific indicators in config files
    ZOLA_INDICATORS = {"zola", "base_url", "default_language", "theme", "title"}
    
    def __init__(self, project_path: Path):
        """Initialize SSG detector with a project path.
        
        Args:
            project_path: Path to the SSG project directory
        """
        self.project_path = project_path.resolve()
        # Initialize class-level cache once
        if not hasattr(self.__class__, "_detection_cache"):
            self.__class__._detection_cache = {}
    
    def detect_ssg_type(self) -> SSGType:
        """Detect SSG type using the complete detection algorithm.
        
        This method implements the following detection order:
        1. Check configuration files for SSG indicators
        2. If no config file found, detect from frontmatter format in content files
        
        Returns:
            Detected SSG type (HUGO, ZOLA, or UNKNOWN)
        """
        # Cached result first
        key = str(self.project_path)
        cached = self.__class__._detection_cache.get(key)
        if cached is not None:
            return cached

        # Step 1: Try to detect from configuration files
        config_type = self._detect_from_config_files()
        if config_type != SSGType.UNKNOWN:
            self.__class__._detection_cache[key] = config_type
            return config_type
        
        # Step 2: Try to detect from frontmatter format
        frontmatter_type = self._detect_from_frontmatter()
        if frontmatter_type != SSGType.UNKNOWN:
            self.__class__._detection_cache[key] = frontmatter_type
            return frontmatter_type
        
        self.__class__._detection_cache[key] = SSGType.UNKNOWN
        return SSGType.UNKNOWN
    
    def _detect_from_config_files(self) -> SSGType:
        """Detect SSG type by analyzing configuration files.
        
        Returns:
            SSG type based on configuration file analysis
        """
        for config_file in self.CONFIG_FILES:
            config_path = self.project_path / config_file
            if not config_path.exists():
                continue
            
            try:
                content = config_path.read_text(encoding="utf-8")
                
                # Case-insensitive search for zola or hugo strings
                if re.search(r'zola', content, re.IGNORECASE):
                    return SSGType.ZOLA
                elif re.search(r'hugo', content, re.IGNORECASE):
                    return SSGType.HUGO
                
                # More detailed analysis based on file type
                if config_file.endswith('.toml'):
                    return self._analyze_toml_config(config_path)
                elif config_file.endswith(('.yml', '.yaml')):
                    return self._analyze_yaml_config(config_path)
                    
            except (OSError, yaml.YAMLError, toml.TomlDecodeError):
                # Skip files that can't be read or parsed
                continue
        
        return SSGType.UNKNOWN
    
    def _analyze_toml_config(self, config_path: Path) -> SSGType:
        """Analyze TOML configuration file for SSG indicators.
        
        Args:
            config_path: Path to TOML config file
            
        Returns:
            Detected SSG type
        """
        try:
            config_data = toml.loads(config_path.read_text(encoding="utf-8"))
            
            # Check for Zola-specific keys
            zola_keys = {"base_url", "default_language", "taxonomies"}
            if any(key in config_data for key in zola_keys):
                return SSGType.ZOLA
            
            # Check for Hugo-specific keys
            hugo_keys = {"baseURL", "languageCode", "paginate", "enableRobotsTXT"}
            if any(key in config_data for key in hugo_keys):
                return SSGType.HUGO
                
        except (OSError, toml.TomlDecodeError):
            pass
        
        return SSGType.UNKNOWN
    
    def _analyze_yaml_config(self, config_path: Path) -> SSGType:
        """Analyze YAML configuration file for SSG indicators.
        
        Args:
            config_path: Path to YAML config file
            
        Returns:
            Detected SSG type
        """
        try:
            config_data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if not isinstance(config_data, dict):
                return SSGType.UNKNOWN
            
            # Check for Hugo-specific keys
            hugo_keys = {"baseURL", "languageCode", "paginate", "enableRobotsTXT"}
            if any(key in config_data for key in hugo_keys):
                return SSGType.HUGO
            
            # Check for Zola-specific keys (less likely in YAML, but check anyway)
            zola_keys = {"base_url", "default_language", "taxonomies"}
            if any(key in config_data for key in zola_keys):
                return SSGType.ZOLA
                
        except (OSError, yaml.YAMLError):
            pass
        
        return SSGType.UNKNOWN
    
    def _detect_from_frontmatter(self) -> SSGType:
        """Detect SSG type by analyzing frontmatter format in content files.
        
        Returns:
            SSG type based on frontmatter format analysis
        """
        content_dirs = ["content", "posts", "blog"]
        
        for content_dir in content_dirs:
            content_path = self.project_path / content_dir
            if not content_path.exists():
                continue
            
            # Look for markdown files
            for md_file in content_path.rglob("*.md"):
                if not md_file.is_file():
                    continue
                
                frontmatter_format = self._detect_frontmatter_format(md_file)
                if frontmatter_format == "yaml":
                    return SSGType.HUGO
                elif frontmatter_format == "toml":
                    return SSGType.ZOLA
        
        return SSGType.UNKNOWN
    
    def _detect_frontmatter_format(self, md_file: Path) -> Optional[str]:
        """Detect the frontmatter format in a markdown file.
        
        Args:
            md_file: Path to markdown file
            
        Returns:
            Frontmatter format type: "yaml", "toml", or None
        """
        try:
            content = md_file.read_text(encoding="utf-8")
            content = content.strip()
            
            if content.startswith("---"):
                # YAML frontmatter (used by Hugo)
                return "yaml"
            elif content.startswith("+++"):
                # TOML frontmatter (used by Zola)
                return "toml"
                
        except OSError:
            pass
        
        return None
    
    def get_recommended_frontmatter_format(self) -> str:
        """Get the recommended frontmatter format based on detected SSG type.
        
        Returns:
            Recommended frontmatter format ("yaml" or "toml")
        """
        ssg_type = self.detect_ssg_type()
        if ssg_type == SSGType.HUGO:
            return "yaml"
        elif ssg_type == SSGType.ZOLA:
            return "toml"
        else:
            # Default to YAML for unknown cases
            return "yaml"


def detect_ssg_type(project_path: Path) -> SSGType:
    """Convenience function to detect SSG type for a project.
    
    Args:
        project_path: Path to the SSG project directory
        
    Returns:
        Detected SSG type
    """
    detector = SSGDetector(project_path)
    return detector.detect_ssg_type()


def get_ssg_recommendations(project_path: Path) -> dict:
    """Get comprehensive SSG detection results.
    
    Args:
        project_path: Path to the SSG project directory
        
    Returns:
        Dictionary with detection results and recommendations
    """
    detector = SSGDetector(project_path)
    ssg_type = detector.detect_ssg_type()
    
    return {
        "ssg_type": ssg_type.value,
        "recommended_frontmatter": detector.get_recommended_frontmatter_format(),
        "is_confident": ssg_type != SSGType.UNKNOWN
    }