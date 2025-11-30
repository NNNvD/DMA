#!/usr/bin/env python3
"""
Export OpenAPI schema from the FastAPI app to docs/openapi.json.
Run: python scripts/export_openapi.py
"""

import os
import sys
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.api.main import app  # noqa: E402


def main():
    schema = app.openapi()
    out_dir = os.path.join(PROJECT_ROOT, "docs")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "openapi.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"Wrote {out_file}")


if __name__ == "__main__":
    main()

