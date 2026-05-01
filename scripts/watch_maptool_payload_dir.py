#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from scripts.push_maptool_payload_file import push_payload_file


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Watch a directory of exported MapTool JSON payloads and push changed files into the local bridge."
    )
    parser.add_argument(
        "--dir",
        dest="directory",
        required=True,
        help="Directory to watch for *.json payload files.",
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
        "--interval-seconds",
        type=float,
        default=2.0,
        help="Polling interval in seconds.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process the current directory contents once and exit.",
    )
    return parser


def _iter_payload_files(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.glob("*.json")
        if path.is_file() and not path.name.startswith(".")
    )


def _process_directory(
    *,
    directory: Path,
    bridge_url: str,
    token: str | None,
    seen_mtimes: dict[Path, float],
) -> int:
    pushed = 0
    for path in _iter_payload_files(directory):
        mtime = path.stat().st_mtime
        if seen_mtimes.get(path) == mtime:
            continue
        push_payload_file(
            file_path=str(path),
            bridge_url=bridge_url,
            token=token,
        )
        seen_mtimes[path] = mtime
        print(f"Pushed {path}")
        pushed += 1
    return pushed


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    directory = Path(args.directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    seen_mtimes: dict[Path, float] = {}

    if args.once:
        _process_directory(
            directory=directory,
            bridge_url=args.bridge_url,
            token=args.token,
            seen_mtimes=seen_mtimes,
        )
        return 0

    print(f"Watching {directory}")
    while True:
        _process_directory(
            directory=directory,
            bridge_url=args.bridge_url,
            token=args.token,
            seen_mtimes=seen_mtimes,
        )
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
