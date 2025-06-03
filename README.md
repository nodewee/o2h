## O2H

🌐 [English](README.md) | [中文](README_zh.md)

Convert **O**bsidian notes **to** **H**ugo/Zola posts

## Features

- Links
  - Convert internal links (notes,attachments and heading/anchor) automatically
  - Using slug format, get slug from front-matter or convert from file name
  - Alert for invalid internal links
  - Convert video attachment (.mp4, .webm, .ogg) links to HTML video tags

- Folders
  - Convert all folders in the notes library by default (automatically exclude template folders)
  - One or more folders can be specified
  - Option to empty target folder (keep "_index.*" files)

- Date/time of publication
  - First look for the specified value from the front-matter, if not found
  - Use the creation time and last modified time of the notes file (.md)

- Language support
  - If frontmatter contains a `lang` field, the language suffix will be added to the generated filename
  - Example: article with `lang: "zh"` and slug `abc-efg` will generate `abc-efg.zh.md`

- Frontmatter
  - Support both YAML and TOML formats
  - YAML format (default) - compatible with Hugo SSG
  - TOML format - compatible with Zola SSG
  - Specify format with `--frontmatter-format` parameter

- SSG Compatibility
  - **Hugo SSG**: Use YAML frontmatter format (default)
  - **Zola SSG**: Use TOML frontmatter format

## Usage

```sh
git clone https://github.com/nodewee/o2h.git
cd o2h
pdm install
# or pip install -r requirements.txt
python . --help
```

### Examples

```sh
# Convert notes for Hugo SSG (YAML frontmatter - default)
python . "path/to/obsidian/vault" "path/to/hugo/project" --folders blogs

# Convert notes for Zola SSG (TOML frontmatter)
python . "path/to/obsidian/vault" "path/to/zola/project" --folders blogs --frontmatter-format toml

# Convert specific folders with custom mappings
python . "path/to/obsidian/vault" "path/to/hugo/project" --folders "blogs>posts notes>articles"
```
