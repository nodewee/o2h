import html
import json
import logging
import os
import pathlib
import re
import shutil
import urllib.parse
import io
import toml

import frontmatter
from o2h.add_spaces import add_spaces_to_content
from slugify import slugify
from o2h.utils import (
    calc_file_md5,
    format_time,
    get_file_creation_time,
    get_file_modification_time,
    yield_files,
    yield_subfolders,
)


# Custom TOML handler for frontmatter
class CustomTOMLHandler:
    """Handler for TOML frontmatter."""

    def load(self, fm, text):
        """Parse TOML front matter. Returns the metadata and content."""
        try:
            metadata, content = self.split(text)
            if metadata:
                fm.metadata = toml.loads(metadata)
            else:
                fm.metadata = {}
            fm.content = content
        except Exception as e:
            logging.error(f"Error parsing frontmatter: {e}")
            fm.metadata = {}
            fm.content = text

    def split(self, text):
        """Split text into metadata and content parts."""
        if not text.startswith('+++'):
            return None, text

        # Find the end of the frontmatter section (marked by +++)
        end_index = text.find('+++', 3)
        if end_index == -1:
            return None, text

        metadata = text[3:end_index].strip()
        content = text[end_index+3:].lstrip()
        return metadata, content

    def export(self, metadata, content):
        """Format metadata and content for TOML frontmatter."""
        if not metadata:
            return content

        try:
            toml_metadata = toml.dumps(metadata)
            if not toml_metadata.strip():
                return content
            return f"+++\n{toml_metadata}+++\n\n{content}"
        except Exception as e:
            logging.error(f"Error exporting TOML frontmatter: {e}")
            return content

    def format(self, post, **kwargs):
        """Format a post for dumping."""
        return self.export(post.metadata, post.content)


def handle(
    obsidian_vault_path: str,
    hugo_project_path: str,
    hugo_attachment_folder_name: str,
    folder_name_map: dict = None,
    onoff_clean_dest_dirs: bool = False,
    onoff_md5_attachment: bool = False,
    frontmatter_format: str = "yaml",
):
    """
    Args:
    - obsidian_note_folder_names, if not specified, all notes (exclude "drafts" and "template" folder) in the vault will be converted
    - hugo_post_folder_name, destination folder in hugo project content directory. default is "posts"
    - folder_name_map, data struct: {src_folder:dest_folder}. if it's empty, means all folders
    - attachment_folder_names, tuple of (folder_name_in_obsidian, folder_name_in_hugo)
    - frontmatter_format, format of frontmatter in generated Hugo posts: "yaml" or "toml"
    """

    logging.info("Start converting...")

    # 1st check folders
    _check_folders(obsidian_vault_path, hugo_project_path, folder_name_map)

    # prepare exclude dirs
    excluded_dirname_patterns = [r"^\."]
    # excludes template folder
    tmp_cfg_file = str(
        pathlib.Path(obsidian_vault_path, ".obsidian/templates.json").absolute()
    )
    t = open(tmp_cfg_file).read()
    template_dirname = json.loads(t).get("folder")
    excluded_dirname_patterns.append(f"^(?:{template_dirname})$")

    # 2nd parse folders
    folders_map = _prepare_folder_map(
        obsidian_vault_path,
        hugo_project_path,
        folder_name_map,
        excluded_dirname_patterns,
    )

    # 3rd parse notes
    note_files_map, inline_links = _parse_obsidian_notes(
        obsidian_vault_path, folders_map, excluded_dirname_patterns
    )

    if onoff_clean_dest_dirs:
        clean_up_dest_dirs(hugo_project_path, folders_map, hugo_attachment_folder_name)

    # 4th copy attachments
    inline_links = copy_attachments(
        inline_links,
        obsidian_vault_path,
        hugo_project_path,
        hugo_attachment_folder_name,
        onoff_md5_attachment,
    )

    # 5th generate hugo posts
    generate_hugo_posts(
        note_files_map,
        inline_links,
        obsidian_vault_path,
        hugo_project_path,
        hugo_attachment_folder_name,
        frontmatter_format,
    )

    logging.info("Done!")


def _check_folders(
    obsidian_vault_path: str, hugo_project_path: str, folder_name_map: dict
):
    if not os.path.exists(obsidian_vault_path):
        raise FileNotFoundError(f"Path not found: {obsidian_vault_path}")
    if not os.path.exists(hugo_project_path):
        raise FileNotFoundError(f"Path not found: {hugo_project_path}")

    if not folder_name_map:
        return
    for src_folder, dest_folder in folder_name_map.items():
        if not os.path.exists(os.path.join(obsidian_vault_path, src_folder)):
            raise ValueError(f"Obsidian vault folder {src_folder} does not exist!")


def _prepare_folder_map(
    obsidian_vault_path: str,
    hugo_project_path: str,
    folder_name_map: dict,
    excluded_dirname_patterns: list,
):
    """folders_map = {src_note_folder:dest_post_folder}, absolute path"""
    folders = {}
    if folder_name_map:
        for src_folder, dest_folder in folder_name_map.items():
            src_path = os.path.join(obsidian_vault_path, src_folder)
            dest_rel_dirpath = _slugify_rel_dirpath(dest_folder)
            dest_path = os.path.join(hugo_project_path, "content", dest_rel_dirpath)
            folders[src_path] = dest_path
        return folders

    # else: all folders
    # add all sub folders
    for dirpath in yield_subfolders(
        obsidian_vault_path, recursive=True, excludes=excluded_dirname_patterns
    ):
        src_abs_dirpath = os.path.abspath(dirpath)
        src_rel_dirpath = os.path.relpath(src_abs_dirpath, obsidian_vault_path)

        dest_rel_dirpath = _slugify_rel_dirpath(src_rel_dirpath)
        dest_abs_path = os.path.join(hugo_project_path, "content", dest_rel_dirpath)
        folders[src_abs_dirpath] = dest_abs_path
    # add vault root folder
    folders[obsidian_vault_path] = os.path.join(hugo_project_path, "content", "posts")

    return folders


def _slugify_rel_dirpath(rel_dirpath):
    """slugify relative dirpath"""
    path_parts = rel_dirpath.split(os.sep)
    path_parts = [slugify(add_spaces_to_content(p)) for p in path_parts]
    return os.sep.join(path_parts)


def _parse_obsidian_notes(obsidian_vault_path, folders_map, excluded_dirname_patterns):
    """
    Returns:
    - note_files_map = {note_abs_path:post_abs_path}
    - inline_links = {inline_uri: {"note_abs_path": abs_path, "type": "file|note"}}
    """
    notes = {}
    inline_links = {}

    for note_folder, post_folder in folders_map.items():
        for filepath in yield_files(note_folder, ext=[".md"], recursive=False):
            note_abs_path = os.path.join(note_folder, filepath)

            # exclude dir patterns
            dn = os.path.basename(os.path.dirname(note_abs_path))
            if any([re.search(pat, dn) for pat in excluded_dirname_patterns]):
                continue

            # load post
            note_raw = open(note_abs_path, "rt", encoding="utf-8").read()
            try:
                note = frontmatter.loads(note_raw)
            except Exception as e:
                logging.error(f"Failed to parse note: {filepath}\n\t{e}")
                exit(1)
            # note.metadata, note.content
            inline_links = extract_inline_links_of_post(
                inline_links, obsidian_vault_path, note_folder, note.content, filepath
            )

            # dest post path
            post_slug = note.metadata.get("slug")
            if not post_slug:
                post_filename = os.path.splitext(os.path.basename(filepath))[0]
                post_slug = slugify(add_spaces_to_content(post_filename))
            post_filename = post_slug + ".md"
            notes[note_abs_path] = os.path.join(post_folder, post_filename)

    return notes, inline_links


def extract_inline_links_of_post(
    inline_links: dict, obsidian_vault_path, note_folder, note_content, note_filepath
):
    # convert wiki links to md links: [[file_path]] -> md [](file_path)
    note_content = re.sub(r"\[\[(.*?)\]\]", r"\[\1\](\1)", note_content)

    # find links
    link_pattern = r"\[.*?\]\((.*?)\)"
    for origin_uri in re.findall(link_pattern, note_content):
        if origin_uri in inline_links:
            continue

        if not origin_uri:
            logging.warn(f"Found empty link in {note_filepath}")
            continue

        if ":" in origin_uri:  # ignore external links
            continue

        # convert anchor
        link = {}
        parts = list(urllib.parse.urlsplit(origin_uri))
        link["anchor"] = trans_url_anchor(parts[4])

        if origin_uri.startswith("#"):  # only has anchor
            link["type"] = "anchor"
            link["dest"] = ""
            inline_links.update({origin_uri: link})
            continue

        unquoted_uri_path = urllib.parse.unquote(origin_uri.split("#")[0])
        note_abs_path = os.path.join(obsidian_vault_path, unquoted_uri_path)
        if not os.path.exists(note_abs_path):
            note_abs_path = os.path.join(note_folder, unquoted_uri_path)
        if not os.path.exists(note_abs_path):
            logging.warn(f"Maybe not a uri or broken link: {origin_uri}")
            continue
            # raise ValueError(f"Can not solve the inline uri: {uri}")
        link["note_abs_path"] = note_abs_path

        if os.path.splitext(note_abs_path)[1] in [".md", ".markdown"]:
            link["type"] = "note"
        else:
            link["type"] = "file"
        inline_links.update({origin_uri: link})

    return inline_links


def generate_hugo_posts(
    note_files_map,
    inline_links,
    obsidian_vault_path,
    hugo_project_path,
    hugo_attachment_folder_name,
    frontmatter_format: str = "yaml",
):
    # check be linked notes
    for uri in inline_links:
        type_ = inline_links[uri]["type"]
        if type_ == "note":
            note_abs_path = inline_links[uri].get("note_abs_path")
            if not note_abs_path in note_files_map:
                logging.warn(f"Invalid link. Linked note not be converted: {uri}")
                # use empty value to instead
                note_files_map[note_abs_path] = None

    count = 0
    for note_abs_path, post_abs_path in note_files_map.items():
        if not post_abs_path:  # be linked note that not be converted
            continue

        count += 1
        # read note
        note_raw = open(note_abs_path, "r", encoding="utf-8").read()
        note = frontmatter.loads(note_raw)

        # prepare frontmatter. https://gohugo.io/content-management/front-matter/
        metadata = note.metadata

        title = metadata.get("title", "").strip()
        if not title:
            title = os.path.splitext(os.path.basename(note_abs_path))[0]
            title = html.escape(title)
        metadata["title"] = title

        post_date = metadata.get("date")
        if not post_date:
            post_date = metadata.get("created")
        if not post_date:
            post_date = get_file_creation_time(note_abs_path)
        if post_date:
            metadata["date"] = post_date

        last_mod = metadata.get("lastmod")
        if not last_mod:
            last_mod = metadata.get("updated")
        if not last_mod:
            last_mod = metadata.get("modified")
        if not last_mod:
            last_mod = get_file_modification_time(note_abs_path)
        if last_mod:
            metadata["lastmod"] = last_mod

        metadata["tags"] = metadata.get("tags", [])

        metadata, content = replace_inline_links(
            metadata,
            note.content,
            inline_links,
            note_files_map,
            obsidian_vault_path,
            hugo_project_path,
            hugo_attachment_folder_name,
        )

        post = frontmatter.Post(content, **metadata)
        
        # Output with specified format
        if frontmatter_format == "toml":
            output = frontmatter.dumps(post, handler=CustomTOMLHandler())
        else:
            output = frontmatter.dumps(post)

        dest_dir = os.path.dirname(post_abs_path)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        open(post_abs_path, "w", encoding="utf-8").write(output)

    logging.info(f"Total {count} notes converted.")


def replace_inline_links(
    metadata,
    content,
    inline_links,
    note_files_map,
    obsidian_vault_path,
    hugo_project_path,
    hugo_attachment_folder_name,
):
    # - note_files_map = {note_abs_path:post_abs_path}
    # - inline_links = {uri: {"type": "anchor|file|note", "note_abs_path": "src/file/"}}

    # convert wiki links to md links: [[file_path]] -> md [](file_path)
    content = re.sub(r"\[\[(.*?)\]\]", r"\[\1\](\1)", content)

    content_dir = os.path.join(hugo_project_path, "content")

    video_tag_template = """
<video controls style="width:100%; max-height:480px;border:1px solid #ccc;border-radius:5px;">
    <source src="{uri}" type="video/mp4">
</video>
"""
    attachment_rel_path = "/" + hugo_attachment_folder_name.strip("/") + "/"

    for origin_uri in inline_links:
        type_ = inline_links[origin_uri]["type"]
        if type_ == "file":
            dest_filename = inline_links[origin_uri]["dest_filename"]
            dest_uri = attachment_rel_path + dest_filename
            ext_name = os.path.splitext(dest_filename)[1]

            # replace links in metadata
            metadata = _replace_inline_links_in_var(metadata, origin_uri, dest_uri)

            # replace links in content
            if ext_name in [".mp4", ".webm", ".ogg"]:
                # video, replace md link with html tag
                pos = _find_md_link_pos(content, origin_uri)
                if not pos:
                    continue
                pos_start, pos_end = pos
                tag_html = video_tag_template.format(uri=dest_uri)
                content = content[:pos_start] + tag_html + content[pos_end + 1 :]
            else:
                anchor = inline_links[origin_uri]["anchor"]
                if anchor:
                    dest_uri += f"#{anchor}"
                content = content.replace(f"]({origin_uri})", f"]({dest_uri})")
                continue

        elif type_ == "anchor":
            dest_uri = "#" + inline_links[origin_uri]["anchor"]
            content = content.replace(f"]({origin_uri})", f"]({dest_uri})")
            continue
        elif type_ == "note":
            note_abs_path = inline_links[origin_uri]["note_abs_path"]
            post_abs_path = note_files_map[note_abs_path]
            if not post_abs_path:  # be linked note that not be converted
                dest_uri = "#"
            else:
                dest_rel_path = os.path.relpath(post_abs_path, content_dir)
                dest_uri = os.path.splitext(dest_rel_path)[0]
                dest_uri = urllib.parse.quote(dest_uri)

            anchor = inline_links[origin_uri]["anchor"]
            if anchor:
                dest_uri += f"#{anchor}"
            content = content.replace(f"]({origin_uri})", f"](/{dest_uri})")
            continue
        else:
            raise ValueError(f"Unknown type: {type_}")

    return metadata, content


def _find_md_link_pos(content, uri):
    pos = content.find(f"]({uri}")
    if pos == -1:
        return None
    pos_end = content.find(")", pos)
    pos_start = content.rfind("![", 0, pos)
    return (pos_start, pos_end)


def copy_attachments(
    inline_links,
    obsidian_vault_path,
    hugo_project_path,
    hugo_attachment_folder_name,
    onoff_md5_attachment,
):
    """
    - inline_links: {uri: {"type": "file|note", "note_abs_path": "/src/file", "dest_filename":""}}
    """

    dest_dir = os.path.join(hugo_project_path, "static")
    for name in hugo_attachment_folder_name.split("/"):
        dest_dir = os.path.join(dest_dir, name)
    os.makedirs(dest_dir, exist_ok=True)

    logging.info("Coping attachments ...")

    for uri in inline_links:
        item = inline_links[uri]
        if item["type"] != "file":
            continue
        src_path = item["note_abs_path"]
        file_name, ext_name = os.path.splitext(os.path.basename(src_path))
        if onoff_md5_attachment:
            dest_filename = calc_file_md5(src_path) + ext_name
        else:
            file_rel_path_in_vault = os.path.relpath(src_path, obsidian_vault_path)
            rel_path = os.path.dirname(file_rel_path_in_vault)
            slug_filename = slugify(add_spaces_to_content(rel_path + "-" + file_name))
            dest_filename = slug_filename + ext_name
        dest_path = os.path.join(dest_dir, dest_filename)

        shutil.copyfile(src_path, dest_path)

        inline_links[uri]["dest_filename"] = dest_filename

    return inline_links


def clean_up_dest_dirs(hugo_project_path, folders_map, hugo_attachment_folder_name):
    logging.info("Cleaning up destination directories ...")
    # folders_map = {src_note_folder:dest_post_folder}
    waiting_clean_dirs = []
    for dest_folder in folders_map.values():
        waiting_clean_dirs.append(dest_folder)
    # add attachments dir
    attachment_dir = os.path.join(hugo_project_path, "static")
    for name in hugo_attachment_folder_name.split("/"):
        attachment_dir = os.path.join(attachment_dir, name)
    waiting_clean_dirs.append(attachment_dir)

    # clean up dest dirs
    for dirpath in waiting_clean_dirs:
        # avoid cleaning hugo project dir
        if dirpath.rstrip("/") == hugo_project_path.rstrip("/"):
            continue

        logging.info(f"Cleaning directory: {dirpath} ...")
        for file in pathlib.Path(dirpath).rglob("*"):
            if file.is_dir():
                continue
            if file.name.startswith("_index."):
                continue  # avoid custom index page
            # delete the file
            file.unlink(True)


def trans_url_anchor(url_anchor: str):
    url_anchor = url_anchor.strip().lower()
    if not url_anchor:
        return ""

    s = urllib.parse.unquote(url_anchor).replace(" ", "-")
    return urllib.parse.quote(s)


def _replace_inline_links_in_var(var: any, origin_uri: str, dest_uri: str):
    if isinstance(var, str):
        return var.replace(origin_uri, dest_uri)
    elif isinstance(var, list):
        return [
            _replace_inline_links_in_var(item, origin_uri, dest_uri) for item in var
        ]
    elif isinstance(var, dict):
        return {
            _replace_inline_links_in_var(
                k, origin_uri, dest_uri
            ): _replace_inline_links_in_var(v, origin_uri, dest_uri)
            for k, v in var.items()
        }
    else:
        return var
