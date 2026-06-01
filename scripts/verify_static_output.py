#!/usr/bin/env python3
"""Verify the static SvelteKit build shape Spin will serve."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_SITE = REPO_ROOT / "dist" / "site"


def main() -> int:
    expected_pages = [
        DIST_SITE / "index.html",
        DIST_SITE / "maps" / "index.html",
        DIST_SITE / "maps" / "page" / "2" / "index.html",
        DIST_SITE / "maps" / "page" / "5" / "index.html",
        DIST_SITE / "blog" / "index.html",
        DIST_SITE / "maps" / "asterfall-ring-terminal" / "index.html",
        DIST_SITE / "categories" / "transport" / "index.html",
        DIST_SITE / "categories" / "transport" / "page" / "2" / "index.html",
    ]
    missing = [path for path in expected_pages if not path.exists()]
    if missing:
        for path in missing:
            print(f"Missing static output: {path}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
