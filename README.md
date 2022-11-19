## O2H

Convert notes from **O**bsidian vault **to** **H**ugo content posts

## Features

- Links
  - Slug, use specified slug in file or generated from title
  - URL, replaced local notes and assets addresses with slug.
    (Not supported block link yet)
  - Alert on invalid internal links

- Folders
  - Default is converting all folders (exclude "template" and "drafts" folder in vault
  - Or specify one or more folders.

- Post date/time
  - Use the specified date/time in front-matter first,
  - Or use note(.md) file's created time and last modified time.

## Usage

```sh
git clone https://github.com/nodewee/o2h.git
cd o2h
pdm install
# or pip install -r requirements.txt
python . --help
```
