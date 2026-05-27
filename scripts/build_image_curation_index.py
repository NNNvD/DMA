#!/usr/bin/env python3
"""Build a human-reviewable Obsidian image curation note for NPC portraits."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
PAGE_PATTERN = re.compile(r"page-(\d+)-image-(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class PortraitAsset:
    path: Path
    book: str
    page: int | None
    image_number: int | None


# These are working hypotheses from visual inspection only. They are deliberately
# not written back to NPC notes until the GM confirms the match.
VISUAL_REVIEW_HINTS = {
    ("Abomination Vaults 1 Ruins Of Gauntlight", 1, 2): (
        "likely portrait",
        "Wrin Sivinxi",
        "white-haired horned tiefling astrologer; strong visual match",
    ),
    ("Abomination Vaults 1 Ruins Of Gauntlight", 41, 1): (
        "likely portrait",
        "Korlok",
        "barbazu devil; likely campaign NPC/foe portrait",
    ),
    ("Abomination Vaults 1 Ruins Of Gauntlight", 44, 1): (
        "likely portrait",
        "",
        "undead figure; likely dungeon NPC/foe, needs source-text confirmation",
    ),
    ("Abomination Vaults 1 Ruins Of Gauntlight", 50, 1): (
        "likely portrait",
        "",
        "undead spellcaster; needs source-text confirmation",
    ),
    ("Abomination Vaults 1 Ruins Of Gauntlight", 52, 1): (
        "likely portrait",
        "Belcorra Haruvex",
        "ghostly white-haired woman; strong visual match",
    ),
    ("Abomination Vaults 1 Ruins Of Gauntlight", 62, 1): (
        "likely portrait",
        "",
        "living human with knives; likely named NPC, needs confirmation",
    ),
    ("Abomination Vaults 1 Ruins Of Gauntlight", 91, 1): (
        "likely portrait",
        "Otari Ilvashti",
        "ghostly rogue figure; likely founder ghost",
    ),
    ("Abomination Vaults 2 Hands Of The Devil", 1, 3): (
        "likely portrait",
        "",
        "devil with contracts; likely named foe, needs confirmation",
    ),
    ("Abomination Vaults 2 Hands Of The Devil", 4, 3): (
        "non-portrait",
        "",
        "scene illustration, not a reusable NPC portrait",
    ),
    ("Abomination Vaults 2 Hands Of The Devil", 6, 3): (
        "non-portrait",
        "",
        "scene illustration, not a reusable NPC portrait",
    ),
    ("Abomination Vaults 2 Hands Of The Devil", 8, 3): (
        "likely portrait",
        "Lardus Longsaddle",
        "uniformed older guard captain; plausible match",
    ),
    ("Abomination Vaults 3 Eyes Of Empty Death", 6, 3): (
        "non-portrait",
        "",
        "scene illustration, not a reusable NPC portrait",
    ),
    ("Abomination Vaults 3 Eyes Of Empty Death", 10, 3): (
        "likely portrait",
        "",
        "masked figure; needs campaign-text confirmation",
    ),
    ("Abomination Vaults 3 Eyes Of Empty Death", 11, 3): (
        "likely portrait",
        "",
        "red-cloaked figure; needs campaign-text confirmation",
    ),
    ("Abomination Vaults Players Guide", 8, 3): (
        "likely portrait",
        "",
        "townsperson portrait; candidate needs source-text confirmation",
    ),
    ("Abomination Vaults Players Guide", 9, 3): (
        "likely portrait",
        "",
        "townsperson portrait; candidate needs source-text confirmation",
    ),
}


def portrait_assets(vault_root: Path) -> list[PortraitAsset]:
    asset_root = vault_root / "Library" / "Assets" / "Portraits" / "NPCs"
    if not asset_root.exists():
        return []
    assets: list[PortraitAsset] = []
    for path in sorted(asset_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        relative = path.relative_to(vault_root)
        match = PAGE_PATTERN.search(path.stem)
        page = int(match.group(1)) if match else None
        image_number = int(match.group(2)) if match else None
        assets.append(
            PortraitAsset(
                path=relative,
                book=path.parent.name,
                page=page,
                image_number=image_number,
            )
        )
    return assets


def build_markdown(vault_root: Path) -> str:
    assets = portrait_assets(vault_root)
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
        "This page is the working review queue for extracted **NPC portrait candidates**.",
        "The folder names give us the book, and the filenames give us the extracted page/image number.",
        "That is enough to build a strong review queue, but not enough to auto-confirm every identity.",
        "",
        "## Workflow",
        "",
        "1. Review the focused portrait gallery below.",
        "2. Use `Likely Candidate` only as a hypothesis until a GM confirms the visual match.",
        "3. When confirmed, write the chosen image to the canonical NPC note as `imageLink:`.",
        "4. Also set `image_status`, `image_source`, `image_source_page`, `image_match_basis`, and `image_confidence`.",
        "5. Mark scene art or wrong extractions as `non-portrait` so they do not reappear as portrait candidates.",
        "",
        "## Priority Review Queue",
        "",
        "| NPC | Best Current Candidate | Confidence | Next Step |",
        "| --- | --- | --- | --- |",
        "| Wrin Sivinxi | `page-001-image-02.png` from Book 1 | high | confirm and assign |",
        "| Belcorra Haruvex | `page-052-image-01.png` from Book 1 | high | confirm and assign |",
        "| Otari Ilvashti | `page-091-image-01.png` from Book 1 | medium-high | confirm against source text |",
        "| Lardus Longsaddle | `page-008-image-03.png` from Book 2 | medium | confirm against source text |",
        "| Korlok | `page-041-image-01.png` from Book 1 | medium-high | create/confirm canonical NPC note if needed |",
        "| Others | no safe assignment yet | low | review remaining portraits manually |",
        "",
        "## Focused Portrait Gallery",
        "",
    ]

    current_book = None
    for asset in assets:
        if asset.book != current_book:
            lines.extend([f"### {asset.book}", ""])
            current_book = asset.book
        status, candidate, notes = VISUAL_REVIEW_HINTS.get(
            (asset.book, asset.page, asset.image_number),
            ("needs review", "", "no visual review hint recorded yet"),
        )
        source_label = (
            f"page {asset.page}, image {asset.image_number}"
            if asset.page is not None and asset.image_number is not None
            else "page/image unknown"
        )
        lines.extend(
            [
                f"#### {asset.path.name}",
                "",
                f"![[{asset.path.as_posix()}]]",
                "",
                f"- Path: `[[{asset.path.as_posix()}]]`",
                f"- Source position: `{asset.book}`, {source_label}",
                f"- Review status: `{status}`",
                f"- Likely candidate: {candidate or 'none yet'}",
                f"- Notes: {notes}",
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
