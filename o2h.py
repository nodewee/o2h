import datetime
import html
import json
import os
import pathlib
import re
import shutil
import urllib.parse

import frontmatter
from slugify import slugify

from add_spaces import add_spaces_to_content
from utils import get_file_creation_time, list_files, list_subfolders, time_to_readable


def prepare_attachments(obsidian_vault_path, hugo_static_path, hugo_post_folder_name):
    """
    Return: attachment file path mapping
        = {src_file_path: [slug_path], ...}
    """
    tmpfile = str(pathlib.Path(obsidian_vault_path, ".obsidian/app.json").absolute())
    tmp = open(tmpfile).read()
    attachment_dirname = json.loads(tmp).get("attachmentFolderPath")

    attachment_indexes = {}
    for ob_attach_dir_abs_path in list_subfolders(obsidian_vault_path):
        if f"/{attachment_dirname}" not in ob_attach_dir_abs_path:
            # filter out attachments folders
            continue
        ob_attach_dir_rel_path = os.path.relpath(
            ob_attach_dir_abs_path, obsidian_vault_path
        )
        for src_file_path in list_files(ob_attach_dir_abs_path):
            src_file_name = os.path.basename(src_file_path)

            dest_file_name = slugify(add_spaces_to_content(src_file_name))

            # copy file to hugo static dir
            dest_file_path = os.path.join(
                hugo_static_path, hugo_post_folder_name, dest_file_name
            )
            shutil.copyfile(src_file_path, dest_file_path)

            # store link mapping
            src_file_rel_path = os.path.join(ob_attach_dir_rel_path, src_file_name)
            slug_uri = hugo_post_folder_name + "/" + dest_file_name
            attachment_indexes[src_file_rel_path.lower()] = [slug_uri]

    return attachment_indexes


def prepare_notes_all(
    hugo_post_folder_name: str,
    obsidian_vault_path: str,
    exclude_dirs=[],
):
    """
    Args:
        - exclude_dirs, relative path in the vault

    Returns: note file path mapping
        = {src_file_path:[slug_path, quoted_path], ...}
    """

    # excludes templates folder
    tmpfile = str(
        pathlib.Path(obsidian_vault_path, ".obsidian/templates.json").absolute()
    )
    tmp = open(tmpfile).read()
    exclude_dirs.append(json.loads(tmp).get("folder"))

    note_indexes = {}
    for file_abs_path in list_files(obsidian_vault_path, ext=[".md"]):
        file_rel_path = os.path.relpath(file_abs_path, obsidian_vault_path)
        if any(file_rel_path.startswith(exclude_dir) for exclude_dir in exclude_dirs):
            continue
        slug_rel_path = os.path.relpath(file_abs_path, obsidian_vault_path)
        slug_path_parts = slug_rel_path.split("/")
        slug_path_parts[-1] = slug_path_parts[-1][:-3]
        for i in range(len(slug_path_parts)):
            slug_path_parts[i] = slugify(
                add_spaces_to_content(slug_path_parts[i]), word_boundary=True
            )

        # if post slug specified in frontmatter, use it
        post = frontmatter.load(file_abs_path)
        slug = post.metadata.get("slug", "").strip()
        if slug:
            slug_path_parts[-1] = slug

        slug_uri = f"{hugo_post_folder_name}/" + "/".join(slug_path_parts)
        title = os.path.splitext(os.path.basename(file_abs_path))[0]
        note_indexes[file_rel_path.lower()] = [slug_uri, title]

    return note_indexes


def prepare_notes_specified(
    hugo_post_folder_name: str,
    obsidian_vault_path: str,
    obsidian_note_folder_names: list,
):
    """
    Args:
        - obsidian_note_folder_names, relative path in the vault

    Returns: note file path mapping
        = {src_file_path:[slug_path, quoted_path], ...}
    """

    note_indexes = {}
    for specify_folder in obsidian_note_folder_names:
        note_folder_dir = os.path.join(obsidian_vault_path, specify_folder)
        for file_abs_path in list_files(note_folder_dir, ext=[".md"]):
            file_rel_path = os.path.relpath(file_abs_path, obsidian_vault_path)
            slug_rel_path = os.path.relpath(file_abs_path, note_folder_dir)
            slug_path_parts = slug_rel_path.split("/")
            slug_path_parts[-1] = slug_path_parts[-1][:-3]
            for i in range(len(slug_path_parts)):
                slug_path_parts[i] = slugify(
                    add_spaces_to_content(slug_path_parts[i]), word_boundary=True
                )

            # if post slug specified in frontmatter, use it
            post = frontmatter.load(file_abs_path)
            slug = post.metadata.get("slug", "").strip()
            if slug:
                slug_path_parts[-1] = slug

            slug_uri = f"{hugo_post_folder_name}/" + "/".join(slug_path_parts)
            title = os.path.splitext(os.path.basename(file_abs_path))[0]
            note_indexes[file_rel_path.lower()] = [slug_uri, title]
    return note_indexes


def slice_frontmatter(note_content):
    post = frontmatter.loads(note_content)
    return post.metadata, post.content


def replace_links(note_content, note_indexes, attachment_indexes):

    # convert wiki links to md links: [[file_path]] -> md [](file_path)
    note_content = re.sub(r"\[\[(.*?)\]\]", r"\[\1\](\1)", note_content)

    # get links
    found_uris = []
    link_pattern = r"\[.*?\]\((.*?)\)"
    for link_uri in re.findall(link_pattern, note_content):
        uri = link_uri.split("#")[0].strip()
        if not uri:
            continue

        # ignore external links
        if ":" in uri:
            continue

        if uri in found_uris:
            continue

        found_uris.append(uri)

    # replace links
    for uri in found_uris:
        unquoted_uri = urllib.parse.unquote(uri).lower()

        if unquoted_uri in note_indexes:
            slug_uri = note_indexes[unquoted_uri][0]
        elif unquoted_uri in attachment_indexes:
            slug_uri = attachment_indexes[unquoted_uri][0]
        else:
            # dead note link, or not a link (e.g. text in code block)
            print(f"WARNING: A dead or not note link: {unquoted_uri}")
            continue

        note_content = note_content.replace(f"]({uri})", f"](/{slug_uri})")
        note_content = note_content.replace(f"]({uri}#", f"](/{slug_uri}#")

    return note_content


def convert_notes_to_posts(
    note_indexes,
    attachment_indexes,
    obsidian_vault_path,
    hugo_content_path,
    hugo_static_path,
):

    for file_path in note_indexes:
        slug_path = note_indexes[file_path][0]
        title = note_indexes[file_path][1]
        note_file = os.path.join(obsidian_vault_path, file_path)

        try:
            post = frontmatter.load(note_file)
        except Exception as e:
            print(f"Error: {e}")
            print(note_file)
            exit(1)

        # prepare frontmatter. https://gohugo.io/content-management/front-matter/
        metadata = post.metadata
        metadata["slug"] = metadata.get("slug", slug_path.split("/")[-1])
        _title = metadata.get("title", "").strip()
        if _title:
            title = _title
        metadata["title"] = html.escape(title)
        metadata["date"] = metadata.get(
            "date",
            time_to_readable(
                get_file_creation_time(note_file), format_template="%Y-%m-%d"
            ),
        )
        metadata["tags"] = metadata.get("tags", [])
        metadata["lastmod"] = metadata.get(
            "lastmod",
            time_to_readable(
                pathlib.Path(note_file).stat().st_mtime, format_template="%Y-%m-%d"
            ),
        )
        metadata["date"] = datetime.datetime.fromisoformat(str(metadata["date"]))
        metadata["lastmod"] = datetime.datetime.fromisoformat(str(metadata["lastmod"]))

        post.metadata = metadata

        post.content = replace_links(post.content, note_indexes, attachment_indexes)

        output = frontmatter.dumps(post)

        dest_path = os.path.join(hugo_content_path, slug_path + ".md")
        # print(f"dest_path: {dest_path}")
        dest_dir = os.path.dirname(dest_path)

        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        with open(dest_path, "w") as f:
            f.write(output)


def convert(
    obsidian_vault_path,
    hugo_project_path,
    obsidian_note_folder_names: list = None,
    hugo_post_folder_name: str = "posts",
):
    """
    Args:
    - obsidian_note_folder_names, if not specified, all notes (exclude "drafts" and "template" folder) in the vault will be converted
    - hugo_post_folder_name, destination folder in hugo project content directory. default is "posts"
    """
    hugo_content_path = os.path.join(hugo_project_path, "content")
    hugo_static_path = os.path.join(hugo_project_path, "static")

    dest_posts_dir = os.path.join(hugo_content_path, hugo_post_folder_name)
    dest_static_dir = os.path.join(hugo_static_path, hugo_post_folder_name)

    print("NOTICE: Will clean up these directories:")
    print(dest_posts_dir)
    print(dest_static_dir)
    inputstr = input("Confirm to continue (y/N)")
    if inputstr.lower() not in ["y", "yes"]:
        print("Canceled")
        exit(0)

    shutil.rmtree(dest_posts_dir, ignore_errors=True)
    shutil.rmtree(dest_static_dir, ignore_errors=True)
    os.makedirs(dest_posts_dir, exist_ok=True)
    os.makedirs(dest_static_dir, exist_ok=True)

    print("prepare slug and uri ...", flush=True)
    if obsidian_note_folder_names is None:
        note_indexes = prepare_notes_all(
            hugo_post_folder_name, obsidian_vault_path, exclude_dirs=["drafts"]
        )
    else:
        note_indexes = prepare_notes_specified(
            hugo_post_folder_name, obsidian_vault_path, obsidian_note_folder_names
        )

    attachment_indexes = prepare_attachments(
        obsidian_vault_path, hugo_static_path, hugo_post_folder_name
    )

    print("converting ...", flush=True)
    convert_notes_to_posts(
        note_indexes,
        attachment_indexes,
        obsidian_vault_path,
        hugo_content_path,
        hugo_static_path,
    )

    print(f"{len(note_indexes)} notes converted.")
    print(f"{len(attachment_indexes)} attachments copied.")

    print("Done!")
