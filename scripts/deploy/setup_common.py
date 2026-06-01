"""Shared helpers for deployment setup flows."""

from __future__ import annotations

import getpass
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env.local"


def prompt_secret(prompt: str) -> str:
    return getpass.getpass(prompt)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
