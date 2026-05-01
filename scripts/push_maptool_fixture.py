#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os

import httpx


DEFAULT_FIXTURE = {
    "id": "harbor-docks",
    "name": "Greyhaven Docks",
    "tokens": [
        {
            "id": "captain-mira",
            "name": "Captain Mira",
            "x": 14,
            "y": 7,
            "notes": "Holding the line",
            "gm_notes": "Knows the smugglers are backed by House Vane",
            "layer": "objects",
            "hp_current": 22,
            "hp_max": 35,
            "initiative": 18,
            "conditions": ["frightened 1"],
        },
        {
            "id": "talia-stormborn",
            "name": "Talia Stormborn",
            "x": 12,
            "y": 8,
            "notes": "Investigating the crates",
            "layer": "objects",
            "hp_current": 31,
            "hp_max": 38,
            "initiative": 21,
            "conditions": [],
        },
        {
            "id": "smuggler-lookout",
            "name": "Smuggler Lookout",
            "x": 18,
            "y": 4,
            "notes": "Backing toward the skiff",
            "layer": "objects",
            "hp_current": 8,
            "hp_max": 20,
            "initiative": 12,
            "conditions": ["off-guard"],
        },
    ],
    "fog_state": "partial",
    "light_state": "dim",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Push a sample map-state fixture into the local MapTool bridge."
    )
    parser.add_argument(
        "--bridge-url",
        default=os.getenv("MAPTOOL_BRIDGE_URL", "http://127.0.0.1:5005"),
        help="Base URL for the local bridge.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("MAPTOOL_BRIDGE_TOKEN"),
        help="Optional bearer token for protected bridge routes.",
    )
    parser.add_argument(
        "--map-id",
        default=DEFAULT_FIXTURE["id"],
        help="Override the fixture map id.",
    )
    parser.add_argument(
        "--map-name",
        default=DEFAULT_FIXTURE["name"],
        help="Override the fixture map name.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    payload = dict(DEFAULT_FIXTURE)
    payload["id"] = args.map_id
    payload["name"] = args.map_name

    headers = {"Content-Type": "application/json"}
    if args.token:
        token = args.token.strip()
        if not token.startswith("Bearer "):
            token = f"Bearer {token}"
        headers["Authorization"] = token

    with httpx.Client(base_url=args.bridge_url.rstrip("/"), timeout=10.0) as client:
        response = client.post("/bridge/map-state", json=payload, headers=headers)
        response.raise_for_status()

    print(json.dumps(response.json(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
