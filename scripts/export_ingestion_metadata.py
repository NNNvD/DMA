#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.services.ingestion_governance import (  # noqa: E402
    ingestion_governance_service,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate ingestion governance artifacts for assets/imports, including "
            "source registry, sidecars, review queue, and corpus manifests."
        )
    )
    parser.add_argument(
        "--root",
        dest="root_path",
        default=None,
        help="Optional import root to scan instead of assets/imports.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    result = ingestion_governance_service.export_artifacts(root_path=args.root_path)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
