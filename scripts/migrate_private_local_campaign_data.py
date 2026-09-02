from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path
from time import time
from typing import Any
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.routes.live import _npc_dossier_view, _pc_sheet_view, _vault_pc_sheets
from backend.config.settings import settings
from backend.models.base import async_session_maker
from backend.services.campaign_service import campaign_service
from backend.services.obsidian_markdown import split_frontmatter
from backend.services.private_campaign_data_service import private_campaign_data_service


VAULT_ROOT = (PROJECT_ROOT / settings.obsidian_vault_path).resolve()
PRIVATE_ROOT = private_campaign_data_service.private_root()
CAMPAIGN_ID = private_campaign_data_service.campaign_id()
CAMPAIGN_ROOT = PRIVATE_ROOT / "campaigns" / CAMPAIGN_ID
PORTRAIT_SOURCE_ROOT = VAULT_ROOT / "Library" / "Assets" / "Portraits"
PORTRAIT_DEST_ROOT = PRIVATE_ROOT / "media" / CAMPAIGN_ID / "portraits"


NOTE_TABS = [
    {
        "id": "overview",
        "label": "Overview",
        "title": "Campaign Overview",
        "path": "Command Center/Campaign Overview.md",
    },
    {
        "id": "gm-summary",
        "label": "GM Summary",
        "title": "GM Summary Through Level 3 C7",
        "path": "Command Center/Campaign Recaps/GM Summary Through Level 3 C7.md",
    },
    {
        "id": "pc-summary",
        "label": "PC Summary",
        "title": "Player Summary Through Level 3 C7",
        "path": "Command Center/Campaign Recaps/Player Summary Through Level 3 C7.md",
    },
    {
        "id": "items",
        "label": "Items",
        "title": "Treasure Tracker",
        "path": "Command Center/Treasure Tracker.md",
    },
]


def read_markdown_note(relative_path: str) -> tuple[dict[str, Any], str, float | None]:
    path = VAULT_ROOT / relative_path
    if not path.exists():
        return {}, "", None
    frontmatter, body = split_frontmatter(path.read_text(encoding="utf-8"))
    return frontmatter, body.strip() + "\n", path.stat().st_mtime


def write_json(filename: str, payload: dict[str, Any], *, apply: bool) -> None:
    path = CAMPAIGN_ROOT / filename
    print(f"{'write' if apply else 'would write'} {path.relative_to(PROJECT_ROOT)}")
    if not apply:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def copy_portraits(*, apply: bool) -> list[dict[str, Any]]:
    copied = []
    if not PORTRAIT_SOURCE_ROOT.exists():
        return copied
    for source in sorted(PORTRAIT_SOURCE_ROOT.rglob("*")):
        if not source.is_file() or source.name == ".DS_Store":
            continue
        relative = source.relative_to(PORTRAIT_SOURCE_ROOT)
        target = PORTRAIT_DEST_ROOT / relative
        copied.append(
            {
                "source": source.relative_to(VAULT_ROOT).as_posix(),
                "private_path": target.relative_to(PRIVATE_ROOT).as_posix(),
                "name": source.stem,
            }
        )
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    print(f"{'copied' if apply else 'would copy'} {len(copied)} portrait/media files")
    return copied


def vault_target_from_ref(ref: str | None) -> str | None:
    if not ref:
        return None
    value = ref.strip()
    if value.startswith("/api/live/private-file"):
        return None
    if value.startswith("/api/live/vault/file"):
        parsed = urlparse(value)
        path_values = parse_qs(parsed.query).get("path")
        return path_values[0] if path_values else None
    if value.startswith(("http://", "https://")):
        return None
    if value.startswith("private-local:"):
        return None
    if value.startswith("/"):
        return None
    if value.startswith("![[") or value.startswith("[["):
        return value.strip("![]").split("|", 1)[0].split("#", 1)[0].strip()
    return value


def private_portrait_path_from_ref(ref: str | None) -> str | None:
    target = vault_target_from_ref(ref)
    if not target:
        return ref
    prefix = "Library/Assets/Portraits/"
    if not target.startswith(prefix):
        return ref
    return f"media/{CAMPAIGN_ID}/portraits/{target[len(prefix):]}"


def normalize_image_payload(item: dict[str, Any]) -> dict[str, Any]:
    item = json.loads(json.dumps(item))
    details = item.get("details") if isinstance(item.get("details"), dict) else {}
    image = item.get("image") if isinstance(item.get("image"), dict) else {}
    portrait = private_portrait_path_from_ref(item.get("portrait"))
    image_ref = private_portrait_path_from_ref(image.get("ref"))
    image_url = private_portrait_path_from_ref(image.get("url"))
    details_ref = private_portrait_path_from_ref(details.get("portrait") or details.get("image"))

    final_ref = portrait or image_ref or image_url or details_ref
    if final_ref:
        item["portrait"] = final_ref
        image["ref"] = final_ref
        image["url"] = private_campaign_data_service.private_file_url(final_ref)
        image["status"] = image.get("status") or "local"
        details["portrait"] = final_ref
    item["image"] = image
    if details:
        item["details"] = details
    return item


def npc_portrait_by_name(name: str | None, media_items: list[dict[str, Any]]) -> str | None:
    if not name:
        return None
    normalized = name.casefold().replace("'", "").strip()
    for item in media_items:
        if not item["private_path"].startswith(f"media/{CAMPAIGN_ID}/portraits/NPCs/"):
            continue
        stem = Path(item["private_path"]).stem.casefold().replace("'", "").strip()
        if stem == normalized:
            return item["private_path"]
    return None


def campaign_overview_payload() -> dict[str, Any]:
    tabs = []
    for tab in NOTE_TABS:
        frontmatter, body, updated_at = read_markdown_note(tab["path"])
        tabs.append(
            {
                **tab,
                "visibility": frontmatter.get("visibility"),
                "player_safe": frontmatter.get("player_safe"),
                "body_markdown": body,
                "updated_at": updated_at,
            }
        )
    return {
        "campaign_id": CAMPAIGN_ID,
        "source": "obsidian-migration",
        "tabs": tabs,
        "updated_at": time(),
    }


def campaign_recaps_payload() -> dict[str, Any]:
    recap_ids = {"gm-summary", "pc-summary"}
    return {
        "campaign_id": CAMPAIGN_ID,
        "source": "obsidian-migration",
        "items": [
            tab
            for tab in campaign_overview_payload()["tabs"]
            if tab.get("id") in recap_ids
        ],
        "updated_at": time(),
    }


def sessions_payload() -> dict[str, Any]:
    session_dir = VAULT_ROOT / "Command Center" / "Sessions"
    items = []
    if session_dir.exists():
        for path in sorted(session_dir.glob("*.md")):
            relative = path.relative_to(VAULT_ROOT).as_posix()
            frontmatter, body = split_frontmatter(path.read_text(encoding="utf-8"))
            items.append(
                {
                    "id": path.stem.lower().replace(" ", "-"),
                    "path": relative,
                    "title": path.stem,
                    "visibility": frontmatter.get("visibility"),
                    "body_markdown": body.strip() + "\n",
                    "updated_at": path.stat().st_mtime,
                }
            )
    return {
        "campaign_id": CAMPAIGN_ID,
        "source": "obsidian-migration",
        "items": items,
        "updated_at": time(),
    }


def treasure_payload() -> dict[str, Any]:
    frontmatter, body, updated_at = read_markdown_note("Command Center/Treasure Tracker.md")
    return {
        "campaign_id": CAMPAIGN_ID,
        "source": "obsidian-migration",
        "title": "Treasure Tracker",
        "visibility": frontmatter.get("visibility"),
        "body_markdown": body,
        "updated_at": updated_at or time(),
    }


def pcs_payload() -> dict[str, Any]:
    items = [normalize_image_payload(sheet) for sheet in _vault_pc_sheets()]
    return {
        "campaign_id": CAMPAIGN_ID,
        "source": "obsidian-migration",
        "items": items,
        "updated_at": time(),
    }


async def npcs_payload(media_items: list[dict[str, Any]]) -> dict[str, Any]:
    async with async_session_maker() as db:
        overview = await campaign_service.get_overview(db)
    items = []
    for entity in overview.get("npcs") or []:
        dossier = normalize_image_payload(_npc_dossier_view(entity))
        if not dossier.get("portrait"):
            portrait = npc_portrait_by_name(dossier.get("name"), media_items)
            if portrait:
                dossier["portrait"] = portrait
                dossier["image"] = {
                    "ref": portrait,
                    "url": private_campaign_data_service.private_file_url(portrait),
                    "status": "local",
                }
                details = dict(dossier.get("details") or {})
                details["portrait"] = portrait
                dossier["details"] = details
        items.append(dossier)
    return {
        "campaign_id": CAMPAIGN_ID,
        "source": "database-and-obsidian-migration",
        "items": items,
        "updated_at": time(),
    }


async def migrate(*, apply: bool) -> None:
    media_items = copy_portraits(apply=apply)
    write_json("images.json", {"campaign_id": CAMPAIGN_ID, "items": media_items}, apply=apply)
    write_json("campaign-overview.json", campaign_overview_payload(), apply=apply)
    write_json("campaign-recaps.json", campaign_recaps_payload(), apply=apply)
    write_json("sessions.json", sessions_payload(), apply=apply)
    write_json("treasure-tracker.json", treasure_payload(), apply=apply)
    write_json("pcs.json", pcs_payload(), apply=apply)
    write_json("npcs.json", await npcs_payload(media_items), apply=apply)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate current DMA Obsidian/DB campaign material to private-local JSON."
    )
    parser.add_argument("--apply", action="store_true", help="Actually write files.")
    args = parser.parse_args()
    asyncio.run(migrate(apply=args.apply))


if __name__ == "__main__":
    main()
