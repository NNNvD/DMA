#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.models.base import async_session_maker  # noqa: E402
from backend.services.obsidian_vault_sync_service import (  # noqa: E402
    obsidian_vault_sync_service,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import edited Obsidian vault notes back into DMA structured state."
    )
    parser.add_argument(
        "--vault",
        dest="vault_path",
        required=True,
        help="Source Obsidian vault root folder.",
    )
    parser.add_argument(
        "--no-campaign-entities",
        action="store_true",
        help="Skip syncing Campaign/* entity notes.",
    )
    parser.add_argument(
        "--no-campaign-notes",
        action="store_true",
        help="Skip syncing Notes/* campaign-note documents.",
    )
    parser.add_argument(
        "--no-pc-sheets",
        action="store_true",
        help="Skip syncing Sheets/* PC sheet documents.",
    )
    parser.add_argument(
        "--no-session-logs",
        action="store_true",
        help="Skip syncing Sessions/* session-log documents.",
    )
    return parser


async def _run(args: argparse.Namespace) -> dict:
    async with async_session_maker() as session:
        return await obsidian_vault_sync_service.import_vault(
            session,
            vault_path=args.vault_path,
            include_campaign_entities=not args.no_campaign_entities,
            include_campaign_notes=not args.no_campaign_notes,
            include_pc_sheets=not args.no_pc_sheets,
            include_session_logs=not args.no_session_logs,
        )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    result = asyncio.run(_run(args))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
