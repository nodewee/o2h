## O2H

🌐 [English](README.md) | [中文](README_zh.md)

Convert **O**bsidian notes **to** **H**ugo/Zola posts - A modern, type-safe Python converter with improved architecture.

## ✨ Features

### 🔗 Smart Link Processing
- Convert internal links (notes, attachments, and heading/anchor) automatically
- **HTML links support**: Process links in HTML attributes (`src`, `href`, `data-src`, etc.)
  - Works with `<iframe>`, `<img>`, `<a>`, `<video>`, `<audio>` and other HTML tags
  - Example: `<iframe src="attachments/file.html">` → `<iframe src="/attachments/file.html">`
- Using slug format with intelligent slug generation from front-matter or file names
- Alert for invalid internal links with detailed warnings
- Convert video attachment (.mp4, .webm, .ogg) links to HTML video tags
- Support for external link preservation

### 🔗 Internal Linking (NEW!)
- **Automatic cross-referencing**: Define `link_words` in frontmatter to create automatic internal links
- **Smart word matching**: Supports both English word boundaries and Chinese text matching
- **Conflict resolution**: Handle duplicate link words with priority system
- **Self-link prevention**: Avoid linking to words defined by the current article
- **Configurable limits**: Control maximum links per word per article (default: 1)
- **Preserve existing links**: Skip words that are already part of existing links

### 📁 Flexible Folder Management
- Convert all folders in the notes library by default (automatically exclude template folders)
- Specify one or more folders with custom mappings
- Option to clean target folders before conversion (preserves "_index.*" files)
- Intelligent folder structure preservation and conversion

### 📎 Flexible Attachment Management
- **Default behavior**: Save attachments to `static/attachments/` folder within the target project
- **Custom attachment path**: Use `--attachment-target-path` to specify any custom path for attachments
  - Supports both absolute paths (e.g., `/var/www/static/images`) and relative paths (e.g., `media/uploads`)
  - When specified, `--attachment-folder` parameter is ignored
  - Attachments are decoupled from the target project structure
  - **Required**: Must specify `--attachment-host` when using `--attachment-target-path`
- **Attachment host**: Use `--attachment-host` to specify the domain for complete URLs
  - Format: `example.com` or `cdn.example.com` (https:// protocol is auto-added)
  - Generates full URLs like `https://cdn.example.com/image.jpg`
  - Only used with `--attachment-target-path`

### 📅 Smart Date/Time Handling
- Prioritized metadata extraction: frontmatter → file timestamps
- Support for multiple date field formats (date, created, lastmod, updated, modified)
- Automatic file creation and modification time detection

### 🌍 Multi-language Support
- If frontmatter contains a `lang` field, language suffix will be added to generated filename
- Example: article with `lang: "zh"` and slug `abc-efg` generates `abc-efg.zh.md`
- Language-aware URL generation for internal links

### 📝 Frontmatter Formats
- **YAML format** (default) - Compatible with Hugo SSG
- **TOML format** - Compatible with Zola SSG
- Specify format with `--frontmatter-format` parameter
- Intelligent metadata processing and validation
- **Complete field preservation** - All original frontmatter fields are preserved
- Custom fields (author, category, etc.) are automatically passed through

### 🏗️ SSG Compatibility
- **Hugo SSG**: YAML frontmatter format (default)
- **Zola SSG**: TOML frontmatter format
- Optimized output structure for each platform

## 🚀 Installation

### From Source
```bash
git clone https://github.com/nodewee/o2h.git
cd o2h
pip install -e .
```

### Using pip (coming soon)
```bash
pip install o2h
```

## 📖 Usage

### Command Line Interface

```bash
# Convert notes for Hugo SSG (YAML frontmatter - default)
o2h "/path/to/obsidian/vault" "/path/to/hugo/project" --folders blogs

# Convert notes for Zola SSG (TOML frontmatter)  
o2h "/path/to/obsidian/vault" "/path/to/zola/project" --folders blogs --frontmatter-format toml

# Convert specific folders with custom mappings
o2h "/path/to/obsidian/vault" "/path/to/hugo/project" --folders "blogs>posts notes>articles"

# Use custom attachment path with CDN host (absolute path)
o2h "/path/to/obsidian/vault" "/path/to/hugo/project" --folders blogs --attachment-target-path "/var/www/static/images" --attachment-host "cdn.example.com"

# Use custom attachment path with CDN host (relative path)
o2h "/path/to/obsidian/vault" "/path/to/hugo/project" --folders blogs --attachment-target-path "media/uploads" --attachment-host "assets.mysite.com"

# Disable internal linking feature
o2h "/path/to/obsidian/vault" "/path/to/hugo/project" --folders blogs --disable-internal-linking

# Advanced usage with all options
o2h "/path/to/vault" "/path/to/project" \
    --folders "blogs>posts" \
    --attachment-folder "media/images" \
    --attachment-target-path "/var/www/cdn/attachments" \
    --attachment-host "cdn.example.com" \
    --md5-attachment \
    --clean-dest \
    --frontmatter-format toml \
    --internal-link-max 2 \
    --verbose
```

### Python API

```python
from pathlib import Path
from o2h import ObsidianToHugoConverter, ConversionConfig
from o2h.models import FrontmatterFormat

# Basic conversion
config = ConversionConfig(
    obsidian_vault_path=Path("/path/to/obsidian/vault"),
    hugo_project_path=Path("/path/to/hugo/project"),
    folder_name_map={"blogs": "posts"},
)

converter = ObsidianToHugoConverter(config)
result = converter.convert()

if result.success:
    print(f"✅ Converted {result.converted_notes} notes!")
    print(f"🔗 Added {result.internal_links_added} internal links!")
else:
    print(f"❌ Errors: {result.errors}")

# Advanced configuration with internal linking
config = ConversionConfig(
    obsidian_vault_path=Path("/path/to/obsidian/vault"),
    hugo_project_path=Path("/path/to/hugo/project"),
    enable_internal_linking=True,
    internal_link_max_per_article=2,  # Allow up to 2 links per word per article
)
```

## 🏗️ Architecture

### Modern Python Design
- **Type-safe**: Full type annotations with mypy support
- **Modular**: Clean separation of concerns across modules
- **Extensible**: Easy to extend with new features
- **Testable**: Designed for comprehensive testing

### Project Structure
```
o2h/
├── __init__.py          # Package initialization
├── cli.py               # Command-line interface
├── converter.py         # Main conversion logic
├── models.py            # Data models and configuration
├── link_processor.py    # Link processing and transformation
├── logger.py            # Logging configuration
├── utils.py             # Utility functions
└── add_spaces.py        # Chinese/English spacing
```

### Key Components
- **ConversionConfig**: Type-safe configuration management
- **ObsidianToHugoConverter**: Main converter class with error handling
- **LinkProcessor**: Specialized link processing and URL transformation
- **NoteMetadata**: Structured metadata processing
- **ConversionResult**: Comprehensive result reporting

## 📝 Internal Linking Usage

### Setting up link_words in frontmatter

```yaml
---
title: "Machine Learning Basics"
date: "2024-01-15"
tags: ["AI", "ML"]
link_words: 
  - "machine learning"
  - "artificial intelligence" 
  - "neural networks"
---

This article introduces machine learning concepts...
```

```toml
+++
title = "Machine Learning Basics"
date = "2024-01-15"
tags = ["AI", "ML"]
link_words = [
  "machine learning",
  "artificial intelligence", 
  "neural networks"
]
+++

This article introduces machine learning concepts...
```

### How it works

1. **Registry Building**: O2H scans all articles and builds a registry of `link_words` → article URLs
2. **Smart Linking**: When processing each article, it finds these keywords in other articles' content
3. **Automatic Links**: First occurrence of each keyword gets converted to a link (configurable limit)
4. **Conflict Resolution**: If multiple articles define the same `link_words`, the first one (or higher priority) wins
5. **Self-Link Prevention**: Articles don't link to their own defined keywords

## 🔧 Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `--folders` | Folder mappings (`source>target`) | All folders |
| `--attachment-folder` | Attachment destination folder | `attachments` |
| `--attachment-target-path` | Custom attachment path (absolute or relative) | None |
| `--attachment-host` | Host domain for attachments (e.g., `cdn.example.com`) | None |
| `--md5-attachment` | Use MD5 hash for attachment names | `false` |
| `--clean-dest` | Clean target directories first | `false` |
| `--frontmatter-format` | Frontmatter format (`yaml`/`toml`) | `yaml` |
| `--disable-internal-linking` | Disable automatic internal linking | `false` |
| `--internal-link-max` | Max internal links per word per article | `1` |
| `--verbose` | Enable detailed logging | `false` |

## 🐛 Error Handling

O2H provides comprehensive error handling and reporting:

- **Validation**: Input path and configuration validation
- **Warnings**: Non-fatal issues (missing links, etc.)
- **Errors**: Fatal issues that prevent conversion
- **Detailed logging**: Verbose mode for troubleshooting

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Original concept and implementation
- Community feedback and contributions
- Open source libraries used in this project