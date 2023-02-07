import datetime
import html
import json
import os
import pathlib
import re
import shutil
import urllib.parse

import frontmatter
from add_spaces import add_spaces_to_content
from slugify import slugify
from utils import (
    get_file_creation_time,
    get_file_modification_time,
    time_to_readable,
    yield_files,
    yield_subfolders,
)


def handle(
    obsidian_vault_path: str,
    hugo_project_path: str,
    folder_name_map: dict = None,
    onoff_clean_dest_dirs: bool = False,
):
    """
    Args:
    - obsidian_note_folder_names, if not specified, all notes (exclude "drafts" and "template" folder) in the vault will be converted
    - hugo_post_folder_name, destination folder in hugo project content directory. default is "posts"
    - folder_name_map, data struct: {src_folder:dest_folder}. if it's empty, means all folders
    """

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
        clean_up_dest_dirs(hugo_project_path, folders_map)

    # 4th copy attachments
    inline_links = copy_attachments(inline_links, hugo_project_path)

    # 5th generate hugo posts
    generate_hugo_posts(
        note_files_map, inline_links, obsidian_vault_path, hugo_project_path
    )

    print("Done!")


def _check_folders(
    obsidian_vault_path: str, hugo_project_path: str, folder_name_map: dict
):
    if not os.path.exists(obsidian_vault_path):
        raise ValueError("Obsidian vault path does not exist!")
    if not os.path.exists(hugo_project_path):
        raise ValueError("Hugo project path does not exist!")

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
    - inline_links = {inline_uri: {"abs": abs_path, "type": "file|note"}}
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
                print(f"Failed to parse note: {filepath}\n\t{e}")
                exit(1)
            # note.metadata, note.content
            inline_links = extract_inline_links_of_post(
                inline_links, obsidian_vault_path, note_folder, note.content
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
    inline_links: dict, obsidian_vault_path, note_folder, note_content
):

    # convert wiki links to md links: [[file_path]] -> md [](file_path)
    note_content = re.sub(r"\[\[(.*?)\]\]", r"\[\1\](\1)", note_content)

    # find links
    link_pattern = r"\[.*?\]\((.*?)\)"
    for link_uri in re.findall(link_pattern, note_content):
        uri = link_uri.split("#")[0].strip()
        if not uri:
            continue

        # ignore external links
        if ":" in uri:
            continue

        if uri in inline_links:
            continue

        unquoted_uri = urllib.parse.unquote(uri)
        abs_path = os.path.join(obsidian_vault_path, unquoted_uri)
        if not os.path.exists(abs_path):
            abs_path = os.path.join(note_folder, unquoted_uri)
        if not os.path.exists(abs_path):
            print(f"Maybe not a uri or broken link: {uri}")
            continue
            # raise ValueError(f"Can not solve the inline uri: {uri}")

        if os.path.splitext(abs_path)[1] in [".md", ".markdown"]:
            type_ = "note"
        else:
            type_ = "file"

        inline_links.update({uri: {"abs": abs_path, "type": type_}})

    return inline_links


def generate_hugo_posts(
    note_files_map, inline_links, obsidian_vault_path, hugo_project_path
):

    # check be linked notes
    for uri in inline_links:
        type_ = inline_links[uri]["type"]
        note_abs_path = inline_links[uri]["abs"]
        if type_ == "note":
            if not note_abs_path in note_files_map:
                print(f"Invalid link. Linked note not be converted: {uri}")
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

        metadata["date"] = datetime.datetime.fromisoformat(
            time_to_readable(post_date, format_template="%Y-%m-%d")
        )

        last_mod = metadata.get("lastmod")
        if not last_mod:
            last_mod = metadata.get("updated")
        if not last_mod:
            last_mod = metadata.get("modified")
        if not last_mod:
            last_mod = get_file_modification_time(note_abs_path)

        metadata["lastmod"] = datetime.datetime.fromisoformat(
            time_to_readable(last_mod, format_template="%Y-%m-%d")
        )

        metadata["tags"] = metadata.get("tags", [])

        content = note.content
        content = replace_links(
            content,
            inline_links,
            note_files_map,
            obsidian_vault_path,
            hugo_project_path,
        )

        post = frontmatter.Post(content, **metadata)
        output = frontmatter.dumps(post)

        dest_dir = os.path.dirname(post_abs_path)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        open(post_abs_path, "w", encoding="utf-8").write(output)

    print(f"Total {count} notes converted.")


def replace_links(
    content, inline_links, note_files_map, obsidian_vault_path, hugo_project_path
):
    # - note_files_map = {note_abs_path:post_abs_path}
    # - inline_links = {uri: {"type": "file|note", "abs": "/src/file", "dest": "/dest/file"}}

    # convert wiki links to md links: [[file_path]] -> md [](file_path)
    content = re.sub(r"\[\[(.*?)\]\]", r"\[\1\](\1)", content)

    static_dir = os.path.join(hugo_project_path, "static")
    content_dir = os.path.join(hugo_project_path, "content")

    video_tag_template = """
<video controls style="width:100%; max-height:480px;border:1px solid #ccc;border-radius:5px;">
    <source src="{uri}" type="video/mp4">
</video>
"""

    for uri in inline_links:
        type_ = inline_links[uri]["type"]
        if type_ == "file":
            dest_filename = inline_links[uri]["dest_filename"]
            dest_uri = "/attachments/" + dest_filename
            ext_name = os.path.splitext(dest_filename)[1]

            if ext_name in [".mp4", ".webm", ".ogg"]:
                # video, replace md link with html tag
                pos = _find_md_link_pos(content, uri)
                if not pos:
                    continue
                pos_start, pos_end = pos
                tag_html = video_tag_template.format(uri=dest_uri)
                content = content[:pos_start] + tag_html + content[pos_end + 1 :]
            else:
                content = content.replace(f"]({uri})", f"]({dest_uri})")
                content = content.replace(f"]({uri}#", f"]({dest_uri}#")
                continue

        else:
            note_abs_path = inline_links[uri]["abs"]
            post_abs_path = note_files_map[note_abs_path]
            if not post_abs_path:  # be linked note that not be converted
                dest_uri = "#"
            else:
                dest_rel_path = os.path.relpath(post_abs_path, content_dir)
                dest_uri = os.path.splitext(dest_rel_path)[0]
                dest_uri = urllib.parse.quote(dest_uri)
            content = content.replace(f"]({uri})", f"](/{dest_uri})")
            content = content.replace(f"]({uri}#", f"](/{dest_uri}#")
            continue

    return content


def _find_md_link_pos(content, uri):
    pos = content.find(f"]({uri}")
    if pos == -1:
        return None
    pos_end = content.find(")", pos)
    pos_start = content.rfind("![", 0, pos)
    return (pos_start, pos_end)


def copy_attachments(inline_links, hugo_project_path):
    """
    - inline_links: {uri: {"type": "file|note", "abs": "/src/file", "dest_filename":""}}
    """
    dest_dir = os.path.join(hugo_project_path, "static", "attachments")
    os.makedirs(dest_dir, exist_ok=True)

    for uri in inline_links:
        item = inline_links[uri]
        if item["type"] != "file":
            continue
        src_path = item["abs"]
        filename, ext_name = os.path.splitext(os.path.basename(uri))
        dest_filename = slugify(add_spaces_to_content(filename)) + ext_name
        dest_path = os.path.join(dest_dir, dest_filename)

        shutil.copyfile(src_path, dest_path)

        inline_links[uri]["dest_filename"] = dest_filename

    return inline_links


def clean_up_dest_dirs(hugo_project_path, folders_map):
    # folders_map = {src_note_folder:dest_post_folder}
    waiting_clean_dirs = []
    for dest_folder in folders_map.values():
        waiting_clean_dirs.append(dest_folder)
    # add attachments dir
    waiting_clean_dirs.append(os.path.join(hugo_project_path, "static", "attachments"))

    # clean up dest dirs
    for dirpath in waiting_clean_dirs:
        # avoid cleaning hugo project dir
        if dirpath.rstrip("/") == hugo_project_path.rstrip("/"):
            continue

        shutil.rmtree(dirpath, ignore_errors=True)
        os.makedirs(dirpath, exist_ok=True)
