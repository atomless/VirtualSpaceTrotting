"""Validation and rendering for host-managed mPulse profiles."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence, Tuple
from urllib.parse import urlsplit


REGISTRY_SCHEMA = "virtual-space-trotting.mpulse-profiles.v1"
PROFILE_NAME_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?")
API_KEY_RE = re.compile(r"[A-Za-z0-9]{5}(?:-[A-Za-z0-9]{5}){4}")
TOP_LEVEL_FIELDS = {"schema", "profiles"}
PROFILE_FIELDS = {"description", "script_base_url", "api_key"}


class RegistryError(ValueError):
    """Raised when an mPulse registry is invalid."""


@dataclass(frozen=True)
class Profile:
    name: str
    description: str
    script_base_url: str
    api_key: str

    @property
    def script_url(self) -> str:
        return f"{self.script_base_url}{self.api_key}"

    def as_dict(self) -> dict[str, str]:
        return {
            "description": self.description,
            "script_base_url": self.script_base_url,
            "api_key": self.api_key,
        }


@dataclass(frozen=True)
class Registry:
    profiles: Mapping[str, Profile]

    def profile(self, name: str) -> Profile:
        try:
            return self.profiles[name]
        except KeyError as exc:
            raise RegistryError(f"Unknown mPulse profile: {name}") from exc

    def canonical_json(self) -> str:
        payload = {
            "schema": REGISTRY_SCHEMA,
            "profiles": {name: profile.as_dict() for name, profile in sorted(self.profiles.items())},
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _reject_duplicate_keys(pairs: Sequence[Tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RegistryError(f"Registry contains duplicate JSON key: {key}")
        result[key] = value
    return result


def _require_exact_fields(payload: Mapping[str, Any], allowed: set[str], context: str) -> None:
    unknown = set(payload) - allowed
    missing = allowed - set(payload)
    if unknown:
        raise RegistryError(f"{context} contains unknown fields: {', '.join(sorted(unknown))}")
    if missing:
        raise RegistryError(f"{context} is missing fields: {', '.join(sorted(missing))}")


def _parse_profile(name: str, payload: Any) -> Profile:
    if not PROFILE_NAME_RE.fullmatch(name):
        raise RegistryError(f"Invalid profile name: {name!r}")
    if not isinstance(payload, dict):
        raise RegistryError(f"Profile {name!r} must be an object")
    _require_exact_fields(payload, PROFILE_FIELDS, f"Profile {name!r}")

    description = payload["description"]
    if not isinstance(description, str) or not 1 <= len(description) <= 200:
        raise RegistryError(f"Profile {name!r} description must contain 1-200 characters")

    api_key = payload["api_key"]
    if not isinstance(api_key, str) or not API_KEY_RE.fullmatch(api_key):
        raise RegistryError(f"Profile {name!r} api_key has an invalid format")

    script_base_url = payload["script_base_url"]
    if not isinstance(script_base_url, str):
        raise RegistryError(f"Profile {name!r} script_base_url must be a string")
    parsed_url = urlsplit(script_base_url)
    if (
        parsed_url.scheme != "https"
        or not parsed_url.hostname
        or parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.query
        or parsed_url.fragment
        or not parsed_url.path.endswith("/boomerang/")
    ):
        raise RegistryError(f"Profile {name!r} script_base_url is not a safe Boomerang HTTPS endpoint")

    return Profile(
        name=name,
        description=description,
        script_base_url=script_base_url,
        api_key=api_key,
    )


def parse_registry_text(text: str) -> Registry:
    try:
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except RegistryError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise RegistryError("Registry must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise RegistryError("Registry must be a JSON object")
    _require_exact_fields(payload, TOP_LEVEL_FIELDS, "Registry")
    if payload["schema"] != REGISTRY_SCHEMA:
        raise RegistryError(f"Unsupported registry schema: {payload['schema']!r}")
    profiles_payload = payload["profiles"]
    if not isinstance(profiles_payload, dict) or not profiles_payload:
        raise RegistryError("Registry must define at least one profile")

    profiles = {name: _parse_profile(name, value) for name, value in profiles_payload.items()}
    return Registry(profiles=MappingProxyType(profiles))


def render_browser_config(profile: Profile) -> str:
    payload = {
        "apiKey": profile.api_key,
        "name": profile.name,
        "scriptBaseUrl": profile.script_base_url,
    }
    return f"window.VST_MPULSE_PROFILE = Object.freeze({json.dumps(payload, sort_keys=True, separators=(',', ':'))});\n"
