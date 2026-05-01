#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx

from backend.models.maptool import MapToolMap


def push_payload_file(
    *,
    file_path: str,
    bridge_url: str,
    token: str | None = None,
) -> dict:
    payload_path = Path(file_path).expanduser().resolve()
    payload = MapToolMap.model_validate(json.loads(payload_path.read_text("utf-8")))

    headers = {"Content-Type": "application/json"}
    if token:
        normalized_token = token.strip()
        if not normalized_token.startswith("Bearer "):
            normalized_token = f"Bearer {normalized_token}"
        headers["Authorization"] = normalized_token

    with httpx.Client(base_url=bridge_url.rstrip("/"), timeout=10.0) as client:
        response = client.post(
            "/bridge/map-state",
            json=payload.model_dump(exclude_none=True),
            headers=headers,
        )
        response.raise_for_status()
    return response.json()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a MapTool bridge payload JSON file and push it to the local bridge."
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to a JSON file matching the bridge MapToolMap payload shape.",
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
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    result = push_payload_file(
        file_path=args.file,
        bridge_url=args.bridge_url,
        token=args.token,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
