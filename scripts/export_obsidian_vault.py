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
import backend.models.campaign  # noqa: F401,E402
import backend.models.document  # noqa: F401,E402
import backend.models.chunk  # noqa: F401,E402
from backend.services.obsidian_vault_service import (  # noqa: E402
    obsidian_vault_service,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export DMA campaign state and generated notes into an Obsidian vault."
    )
    parser.add_argument(
        "--vault",
        dest="vault_path",
        required=True,
        help="Target Obsidian vault root folder.",
    )
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Export only active campaign entities.",
    )
    parser.add_argument(
        "--no-campaign-notes",
        action="store_true",
        help="Skip exporting stored campaign note documents.",
    )
    parser.add_argument(
        "--no-pc-sheets",
        action="store_true",
        help="Skip exporting stored PC sheet documents.",
    )
    parser.add_argument(
        "--no-session-logs",
        action="store_true",
        help="Skip exporting session log documents.",
    )
    parser.add_argument(
        "--no-session-prep",
        action="store_true",
        help="Skip exporting generated session prep documents.",
    )
    parser.add_argument(
        "--no-indexes",
        action="store_true",
        help="Skip writing Obsidian index notes.",
    )
    parser.add_argument(
        "--no-command-center",
        action="store_true",
        help="Skip writing generated command-center dashboard notes.",
    )
    parser.add_argument(
        "--campaign-note-limit",
        type=int,
        default=100,
        help="Maximum number of campaign note documents to export.",
    )
    parser.add_argument(
        "--pc-sheet-limit",
        type=int,
        default=50,
        help="Maximum number of PC sheet documents to export.",
    )
    parser.add_argument(
        "--session-limit",
        type=int,
        default=50,
        help="Maximum number of session log documents to export.",
    )
    parser.add_argument(
        "--prep-limit",
        type=int,
        default=50,
        help="Maximum number of session prep documents to export.",
    )
    return parser


async def _run(args: argparse.Namespace) -> dict:
    async with async_session_maker() as session:
        return await obsidian_vault_service.export_vault(
            session,
            vault_path=args.vault_path,
            include_inactive=not args.active_only,
            include_campaign_notes=not args.no_campaign_notes,
            include_pc_sheets=not args.no_pc_sheets,
            include_session_logs=not args.no_session_logs,
            include_session_prep=not args.no_session_prep,
            include_indexes=not args.no_indexes,
            include_command_center=not args.no_command_center,
            campaign_note_limit=args.campaign_note_limit,
            pc_sheet_limit=args.pc_sheet_limit,
            session_limit=args.session_limit,
            prep_limit=args.prep_limit,
        )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    result = asyncio.run(_run(args))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
