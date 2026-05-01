#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.services.aon_rules_fetch_service import (  # noqa: E402
    aon_rules_fetch_service,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Pathfinder 2e rules pages from Archives of Nethys into "
            "assets/imports/misc/aon-rules/raw/ as retrieval-only rule payloads."
        )
    )
    parser.add_argument(
        "--root",
        dest="root_path",
        default=None,
        help="Optional output root instead of assets/imports/misc/aon-rules.",
    )
    parser.add_argument(
        "--id",
        dest="ids",
        action="append",
        type=int,
        default=[],
        help="Optional rule page ID filter. Repeat for multiple values.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for the number of fetched rule pages.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=0.0,
        help="Optional pause between requests.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="Network timeout per request.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Do not overwrite JSON files that already exist.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    result = aon_rules_fetch_service.fetch_rules(
        root_path=args.root_path,
        ids=set(args.ids) or None,
        limit=args.limit,
        overwrite=not args.skip_existing,
        pause_seconds=args.pause_seconds,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
