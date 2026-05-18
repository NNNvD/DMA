#!/usr/bin/env python3
"""Backfill private room-key JSON files with literal room text.

This script reads ignored/private room-key JSON files and enriches them from the
local Obsidian reference markdown. The resulting literal text is copyrighted
campaign material, so only run with --apply against private-local files that are
ignored by Git.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.routes.live import _enrich_room_key_literal_text


DEFAULT_ROOM_KEY_ROOT = Path("assets/imports/misc/private-local/room-keys")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _literal_count(payload: dict[str, Any]) -> tuple[int, int]:
    rooms = payload.get("rooms") or []
    if not isinstance(rooms, list):
        return 0, 0
    return sum(1 for room in rooms if isinstance(room, dict) and room.get("literal_text")), len(rooms)


def _iter_room_keys(root: Path, map_id: str | None) -> list[Path]:
    paths = sorted(root.rglob("*.json"))
    if not map_id:
        return paths
    normalized = map_id.strip().casefold()
    matched: list[Path] = []
    for path in paths:
        try:
            payload = _load_json(path)
        except json.JSONDecodeError:
            continue
        if str(payload.get("map_id", "")).strip().casefold() == normalized:
            matched.append(path)
    return matched


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill ignored/private dungeon room-key JSON with literal room text.",
    )
    parser.add_argument(
        "--room-key-root",
        type=Path,
        default=DEFAULT_ROOM_KEY_ROOT,
        help=f"Room-key root folder. Default: {DEFAULT_ROOM_KEY_ROOT}",
    )
    parser.add_argument(
        "--map-id",
        help="Only backfill the room-key file whose map_id matches this value.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write enriched literal_text fields back to disk. Without this, dry-run only.",
    )
    args = parser.parse_args()

    root = args.room_key_root
    if not root.exists():
        print(f"Room-key root not found: {root}")
        return 1

    paths = _iter_room_keys(root, args.map_id)
    if not paths:
        suffix = f" for map_id={args.map_id!r}" if args.map_id else ""
        print(f"No room-key JSON files found under {root}{suffix}.")
        return 1

    changed = 0
    for path in paths:
        payload = _load_json(path)
        before_count, total = _literal_count(payload)
        enriched = _enrich_room_key_literal_text(payload)
        after_count, _total = _literal_count(enriched)
        needs_write = after_count > before_count
        status = "would update" if needs_write and not args.apply else "updated" if needs_write else "unchanged"
        print(f"{status}: {path} ({before_count}/{total} -> {after_count}/{total} rooms)")
        if needs_write and args.apply:
            _write_json(path, enriched)
            changed += 1

    if args.apply:
        print(f"Applied updates to {changed} file(s).")
    else:
        print("Dry run only. Re-run with --apply to write private literal_text to disk.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
