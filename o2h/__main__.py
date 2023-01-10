# CLI Entry

import fire

from o2h import converter


def cli(
    obsidian_vault: str,
    hugo_project: str,
    folders: str = None,
):
    """
    O2H v0.2.0

    Convert notes from Obsidian vault to Hugo content posts.

    Args:
    - folders:
        - Default is None that means convert all folders in Obsidian vault, and same folder name to Hugo content
        - Or specified Obsidian note folders
        - Or specified Obsidian note folders and destination folder names in Hugo content

    Example:
        - `python3 o2h "path/to/obsidian/vault" "path/to/hugo/project"`
        - `python3 o2h "path/to/obsidian/vault" "path/to/hugo/project" --folders=posts,drafts`
        - `python3 o2h "path/to/obsidian/vault" "path/to/hugo/project" --folders=a>posts,b>articles`

    """

    folder_name_map = {}  # {src_folder:dest_folder}
    if folders:
        for item in folders.split(","):
            item = item.strip()
            if not item:
                continue

            if ">" not in item:
                folder_name_map[item] = item
            else:
                arr = item.split(">")
                folder_name_map[arr[0]] = arr[1]

    try:
        converter.convert(obsidian_vault, hugo_project, folder_name_map)
    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    fire.Fire(cli)
