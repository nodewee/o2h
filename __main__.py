# CLI Entry

import fire

import o2h


def main(
    obsidian_vault: str,
    obsidian_note_folders: str,
    hugo_project: str,
    hugo_posts_folder,
):
    """
    O2H v0.1.0

    Convert notes from Obsidian vault to Hugo content posts.
    Example: python o2h "path/to/obsidian/vault" "publish,drafts" "path/to/hugo/project" "posts"
    """

    obsidian_note_folders_list = []
    for s in obsidian_note_folders.split(","):
        if not s:
            continue
        obsidian_note_folders_list.append(s.strip())

    o2h.convert(
        obsidian_vault,
        hugo_project,
        obsidian_note_folders_list,
        hugo_posts_folder,
    )


if __name__ == "__main__":
    fire.Fire(main)
