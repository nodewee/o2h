import argparse
import logging
from logging import Formatter, StreamHandler

_title_ = "O2H"
_version_ = "0.3.4"


# Initialize logging config
streamHandler = StreamHandler()
streamHandler.setFormatter(Formatter("%(levelname)-6s %(message)s"))
logging.getLogger().addHandler(streamHandler)
logging.getLogger().setLevel(logging.INFO)


def parse_arguments():
    desc = f"{_title_} ver {_version_}"
    desc += """
Convert Obsidian vault notes to Hugo content posts.

Examples:
    - python o2h "path/to/obsidian/vault" "path/to/hugo/project" --folders blogs
    - python o2h "path/to/obsidian/vault" "path/to/hugo/project" --folders "blogs>posts subject2>subject"
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
        help="(required) Hugo project path",
        type=str,
    )

    parser.add_argument(
        "--folders",
        type=str,
        help='Specify Obsidian note folders to convert, and target folder names in Hugo project. If target folder name is not specified, is the same as the source folder name. The target folder name can be specified after the source folder name, separated by a greater than sign (>). For example: "--folders blogs>posts subject2>subject"',
    )

    parser.add_argument(
        "--md5-filename",
        help="(optional) Use MD5 hash as attachment file name",
        action=argparse.BooleanOptionalAction,
    )

    parser.add_argument(
        "-c",
        "--clean-dest",
        help="(optional) Clean target folders before convert. Default is false",
        action=argparse.BooleanOptionalAction,
    )

    args = parser.parse_args()

    return args


def _parse_folder_name_map(folders: str):
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
    folder_name_map = _parse_folder_name_map(args.folders)

    from o2h import converter

    converter.handle(
        args.obsidian_vault,
        args.hugo_project,
        folder_name_map,
        args.clean_dest,
        args.md5_filename,
    )
