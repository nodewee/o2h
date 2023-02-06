## O2H

Convert notes from **O**bsidian vault **to** **H**ugo content posts

## Features

- Links
  - automatically convert internal links to website relative links (notes, attachments)
  - use slug format, get slug from front-matter or generated from title
  - alert on invalid internal links
  - automatically convert video attachments (.mp4, .webm, .ogg) links to HTML video tags

- Folders
  - Default is converting all folders (exclude template folder) in vault
  - Or specify one or more folders

- Date/time of post
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
