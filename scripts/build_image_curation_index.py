#!/usr/bin/env python3
"""Build a human-reviewable Obsidian image curation note for campaign art."""

from __future__ import annotations

import argparse
from pathlib import Path


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def image_paths(vault_root: Path) -> list[Path]:
    asset_root = vault_root / "Library" / "Assets"
    if not asset_root.exists():
        return []
    return sorted(
        path.relative_to(vault_root)
        for path in asset_root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def build_markdown(vault_root: Path) -> str:
    images = image_paths(vault_root)
    lines = [
        "---",
        "type: image_curation",
        "campaign: Abomination Vaults",
        "visibility: GM only",
        "status: working",
        "---",
        "",
        "# NPC Image Curation",
        "",
        "Use this page to match extracted campaign art to canonical NPC notes.",
        "",
        "## Workflow",
        "",
        "1. Review the image gallery below.",
        "2. When an image is a confirmed NPC portrait, add it to that NPC note as `imageLink:`.",
        "3. Also set `image_status: confirmed`, `image_source: <book/page>`, and `image_notes:` if useful.",
        "4. Leave decorative art, maps, and uncertain matches unassigned until reviewed.",
        "",
        "## NPC Assignment Queue",
        "",
        "| NPC | Confirmed Image | Status | Notes |",
        "| --- | --- | --- | --- |",
        "| Wrin Sivinxi |  | needs review |  |",
        "| Oseph Menhemes |  | needs review |  |",
        "| Lardus Longsaddle |  | needs review |  |",
        "| Vandy Banderdash |  | needs review |  |",
        "| Carman Rajani |  | needs review |  |",
        "| Morlibint |  | needs review |  |",
        "| Yinyasmera |  | needs review |  |",
        "| Belcorra Haruvex |  | needs review |  |",
        "",
        "## Extracted Image Gallery",
        "",
    ]
    current_parent = None
    for image in images:
        parent = image.parent.as_posix()
        if parent != current_parent:
            lines.extend([f"### {parent}", ""])
            current_parent = parent
        lines.extend(
            [
                f"#### {image.name}",
                "",
                f"![[{image.as_posix()}]]",
                "",
                f"- Path: `[[{image.as_posix()}]]`",
                "- Review status: `unreviewed`",
                "- Candidate NPC:",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vault",
        default="obsidian-abomination-vaults-vault",
        help="Path to the Obsidian vault.",
    )
    parser.add_argument(
        "--output",
        default="Command Center/Assets/NPC Image Curation.md",
        help="Vault-relative output note path.",
    )
    args = parser.parse_args()

    vault_root = Path(args.vault).resolve()
    output_path = vault_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_markdown(vault_root), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
