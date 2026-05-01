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
from backend.services.campaign_asset_import_service import (  # noqa: E402
    campaign_asset_import_service,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview or import campaign assets from assets/imports drop zones."
    )
    parser.add_argument(
        "--root",
        dest="root_path",
        default=None,
        help=(
            "Optional root folder containing pathbuilder/, session-logs/, "
            "campaign-notes/, misc/pf2e-reference/raw/ guide files, "
            "misc/aon-rules/raw/ rule payloads, and misc/private-local/reference/raw/ "
            "local reference files."
        ),
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="Optional category filter. Repeat for multiple values.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files and report what would be imported without writing to the database.",
    )
    parser.add_argument(
        "--no-store-documents",
        action="store_true",
        help="Skip storing raw source documents while still importing structured state.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop processing after the first failed file.",
    )
    return parser


async def _run(args: argparse.Namespace) -> dict:
    async with async_session_maker() as session:
        return await campaign_asset_import_service.import_batch(
            session,
            root_path=args.root_path,
            categories=args.category,
            dry_run=args.dry_run,
            store_documents=not args.no_store_documents,
            stop_on_error=args.stop_on_error,
        )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    result = asyncio.run(_run(args))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
