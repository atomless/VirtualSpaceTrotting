"""Shared helpers for agent-oriented deployment setup flows."""

from __future__ import annotations

import getpass
import ipaddress
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.deploy.remote_target import DEFAULT_DURABLE_STATE_DIR

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env.local"
DEFAULT_PUBLIC_IP_URL = "https://api.ipify.org?format=json"


def is_interactive_session() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def prompt_secret(prompt: str) -> str:
    return getpass.getpass(prompt)


def prompt_confirm(prompt: str, *, default_yes: bool = True) -> bool:
    suffix = " [Y/n]: " if default_yes else " [y/N]: "
    answer = input(f"{prompt}{suffix}").strip().lower()
    if not answer:
        return default_yes
    return answer in {"y", "yes"}


def prompt_text(prompt: str) -> str:
    return input(prompt)


def parse_ip_response(body: str) -> str:
    candidate = body.strip()
    if candidate.startswith("{"):
        payload = json.loads(candidate)
        candidate = str(payload.get("ip", "")).strip()
    ipaddress.ip_address(candidate)
    return candidate


def detect_public_ip(url: str = DEFAULT_PUBLIC_IP_URL, timeout_seconds: int = 10) -> str:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8")
    return parse_ip_response(body)


def resolve_operator_allowlist(
    *,
    explicit_value: str,
    persisted_value: str,
    env_value: str,
    accept_detected_default: bool,
) -> str:
    for candidate in (explicit_value, env_value, persisted_value):
        if candidate.strip():
            return candidate.strip()

    detected = f"{detect_public_ip()}/32"
    if accept_detected_default:
        return detected
    if not is_interactive_session():
        raise SystemExit(
            "VST_OPERATOR_IP_ALLOWLIST is missing. Pass --operator-ip or rerun interactively to confirm the detected public IP."
        )
    if prompt_confirm(f"Use {detected} for VST_OPERATOR_IP_ALLOWLIST?", default_yes=True):
        return detected
    entered = prompt_text("Enter VST_OPERATOR_IP_ALLOWLIST value: ").strip()
    if not entered:
        raise SystemExit("VST_OPERATOR_IP_ALLOWLIST cannot be blank.")
    return entered


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
