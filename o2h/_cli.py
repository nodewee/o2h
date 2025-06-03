import argparse
import logging
from logging import Formatter, StreamHandler

_title_ = "O2H"
_version_ = "0.3.7"


# Initialize logging config
streamHandler = StreamHandler()
streamHandler.setFormatter(Formatter("[ %(levelname)-8s ] %(message)s"))
logging.getLogger().addHandler(streamHandler)
logging.getLogger().setLevel(logging.INFO)


def parse_arguments():
    desc = f"{_title_} ver {_version_}"
    desc += """
A markdown format transpiler for Obsidian to Hugo/Zola. (Convert Obsidian vault notes to Hugo or Zola content posts.)

Usage:
    - python . "path/to/obsidian/vault" "path/to/hugo/project" --folders blogs
        Convert all notes in "blogs" folder to Hugo /content/blogs folder (YAML frontmatter).
    - python . "path/to/obsidian/vault" "path/to/zola/project" --folders blogs --frontmatter-format toml
        Convert all notes in "blogs" folder to Zola /content/blogs folder (TOML frontmatter).
    - python . "path/to/obsidian/vault" "path/to/hugo/project" --folders "blogs/abc>posts subject2/efg>subject"
        Convert all notes in "blogs/abc" folder to Hugo /content/posts folder, and all notes in "subject2/efg" folder to Hugo "/content/subject" folder.
        * Use ` ` space to separate multiple folders, and `>` to separate source and target folder names.
    """

    parser = argparse.ArgumentParser(
        prog=f"{_title_}",
        description=desc,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "obsidian_vault",
        help="(required) Obsidian vault path",
        type=str,
    )
    parser.add_argument(
        "hugo_project",
        help="(required) Hugo/Zola project path",
        type=str,
    )

    parser.add_argument(
        "--folders",
        type=str,
        help='Specify Obsidian note folders to convert, and target folder names in Hugo/Zola project. If target folder name is not specified, is the same as the source folder name. The target folder name can be specified after the source folder name, separated by a greater than sign (>). For example: "--folders blogs>posts subject2>subject"',
    )

    parser.add_argument(
        "--attachment-folder",
        help="(optional) Specify the folder name in Hugo/Zola project, that copy attachments to. Default is 'attachments', the path is '/static/attachments'",
        type=str,
        default="attachments",
    )

    parser.add_argument(
        "--md5-attachment",
        help="(optional) Use MD5 hash as attachment file name. Default is false",
        action=argparse.BooleanOptionalAction,
    )

    parser.add_argument(
        "-c",
        "--clean-dest",
        help="(optional) Clean target folders before convert. Default is false",
        action=argparse.BooleanOptionalAction,
    )

    parser.add_argument(
        "--frontmatter-format",
        help="(optional) Specify frontmatter format: yaml (Hugo) or toml (Zola). Default is yaml",
        type=str,
        choices=["yaml", "toml"],
        default="yaml",
    )

    args = parser.parse_args()

    return args


def _parse_post_folder_name_map(folders: str):
    if not folders:
        return {}

    folders = folders.split(" ")
    folder_name_map = {}  # {src_folder:dest_folder}
    for item in folders:
        item = item.strip()
        if not item:
            continue

        if ">" not in item:
            folder_name_map[item] = item
        else:
            arr = item.split(">")
            folder_name_map[arr[0]] = arr[1]
    return folder_name_map



def handle():
    args = parse_arguments()
    post_folder_name_map = _parse_post_folder_name_map(args.folders)

    from o2h import converter

    converter.handle(
        args.obsidian_vault,
        args.hugo_project,
        args.attachment_folder,
        post_folder_name_map,
        args.clean_dest,
        args.md5_attachment,
        args.frontmatter_format,
    )
