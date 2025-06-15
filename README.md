## O2H

🌐 [English](README.md) | [中文](README_zh.md)

Convert **O**bsidian notes **to** **H**ugo/Zola posts - A modern, type-safe Python converter with improved architecture.

## ✨ Features

### 🔗 Smart Link Processing
- Convert internal links (notes, attachments, and heading/anchor) automatically
- Using slug format with intelligent slug generation from front-matter or file names
- Alert for invalid internal links with detailed warnings
- Convert video attachment (.mp4, .webm, .ogg) links to HTML video tags
- Support for external link preservation

### 📁 Flexible Folder Management
- Convert all folders in the notes library by default (automatically exclude template folders)
- Specify one or more folders with custom mappings
- Option to clean target folders before conversion (preserves "_index.*" files)
- Intelligent folder structure preservation and conversion

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

# Advanced usage with all options
o2h "/path/to/vault" "/path/to/project" \
    --folders "blogs>posts" \
    --attachment-folder "media/images" \
    --md5-attachment \
    --clean-dest \
    --frontmatter-format toml \
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
else:
    print(f"❌ Errors: {result.errors}")
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

## 🔧 Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `--folders` | Folder mappings (`source>target`) | All folders |
| `--attachment-folder` | Attachment destination folder | `attachments` |
| `--md5-attachment` | Use MD5 hash for attachment names | `false` |
| `--clean-dest` | Clean target directories first | `false` |
| `--frontmatter-format` | Frontmatter format (`yaml`/`toml`) | `yaml` |
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
