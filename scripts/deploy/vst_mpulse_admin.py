#!/usr/bin/env python3
"""Privileged state transitions for host-managed mPulse profiles."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Optional, Sequence
from urllib.parse import urlsplit

try:
    from scripts.mpulse_profiles import Profile, Registry, RegistryError, parse_registry_text, render_browser_config
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from mpulse_profiles import Profile, Registry, RegistryError, parse_registry_text, render_browser_config


DEFAULT_REGISTRY_PATH = Path("/etc/opt/virtual-space-trotting/mpulse-profiles.json")
DEFAULT_ADMIN_CONFIG_PATH = Path("/etc/opt/virtual-space-trotting/mpulse-admin.json")
DEFAULT_STATE_DIR = Path("/var/opt/virtual-space-trotting/mpulse/state")
DEFAULT_PUBLIC_DIR = Path("/var/opt/virtual-space-trotting/mpulse/public")
DEFAULT_LOCK_PATH = Path("/run/lock/vst-mpulse.lock")


class AdminError(RuntimeError):
    """Raised when a privileged profile operation cannot complete safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def default_probe(profile: Profile) -> None:
    request = urllib.request.Request(
        profile.script_url,
        headers={"Accept": "application/javascript", "User-Agent": "VirtualSpaceTrotting-mPulse-Admin/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            content_type = response.headers.get_content_type()
            body = response.read(4096)
    except Exception as exc:
        raise AdminError(f"Boomerang endpoint probe failed for profile {profile.name!r}: {exc}") from exc
    if content_type not in {"application/javascript", "text/javascript"} and b"BOOMR" not in body:
        raise AdminError(f"Boomerang endpoint for profile {profile.name!r} did not return JavaScript")


def make_public_verifier(public_base_url: str) -> Callable[[Profile], None]:
    base_url = public_base_url.rstrip("/")

    def verify(profile: Profile) -> None:
        expected = render_browser_config(profile).encode("utf-8")
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=8) as response:
                if response.status != 200:
                    raise AdminError(f"Public health returned HTTP {response.status}")
            request = urllib.request.Request(
                f"{base_url}/mpulse-config.js",
                headers={"Cache-Control": "no-cache", "User-Agent": "VirtualSpaceTrotting-mPulse-Admin/1"},
            )
            with urllib.request.urlopen(request, timeout=8) as response:
                body = response.read()
                cache_control = response.headers.get("Cache-Control", "")
        except AdminError:
            raise
        except Exception as exc:
            raise AdminError(f"Public mPulse verification failed: {exc}") from exc
        if body != expected:
            raise AdminError("Public mPulse configuration does not match the selected profile")
        if "no-store" not in cache_control.lower():
            raise AdminError("Public mPulse configuration is missing Cache-Control: no-store")

    return verify


def default_audit(event: dict[str, Any]) -> None:
    subprocess.run(
        ["systemd-cat", "--identifier=vst-mpulse", "--priority=notice"],
        input=json.dumps(event, sort_keys=True) + "\n",
        text=True,
        check=False,
    )


def default_ownership(path: Path, kind: str) -> None:
    group = "caddy" if kind == "public" else "vst-mpulse-operators"
    shutil.chown(path, user="root", group=group)


class MPulseAdmin:
    def __init__(
        self,
        *,
        registry_path: Path = DEFAULT_REGISTRY_PATH,
        state_dir: Path = DEFAULT_STATE_DIR,
        public_dir: Path = DEFAULT_PUBLIC_DIR,
        lock_path: Path = DEFAULT_LOCK_PATH,
        probe: Callable[[Profile], None] = default_probe,
        verify: Optional[Callable[[Profile], None]] = None,
        audit: Callable[[dict[str, Any]], None] = default_audit,
        clock: Callable[[], str] = utc_now,
        apply_ownership: Callable[[Path, str], None] = default_ownership,
        backup_limit: int = 10,
    ) -> None:
        self.registry_path = Path(registry_path)
        self.state_dir = Path(state_dir)
        self.public_dir = Path(public_dir)
        self.lock_path = Path(lock_path)
        self.probe = probe
        self.verify = verify or (lambda _profile: None)
        self.audit = audit
        self.clock = clock
        self.apply_ownership = apply_ownership
        self.backup_limit = backup_limit

    @property
    def active_path(self) -> Path:
        return self.state_dir / "active-profile"

    @property
    def previous_path(self) -> Path:
        return self.state_dir / "previous-profile"

    @property
    def history_path(self) -> Path:
        return self.state_dir / "history.jsonl"

    @property
    def browser_config_path(self) -> Path:
        return self.public_dir / "mpulse-config.js"

    @property
    def backups_dir(self) -> Path:
        return self.state_dir / "registry-backups"

    @contextmanager
    def _mutation_lock(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise AdminError("Another mPulse profile operation is in progress") from exc
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _atomic_write(self, path: Path, content: bytes, *, mode: int, kind: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.chmod(temporary_path, mode)
            self.apply_ownership(temporary_path, kind)
            os.replace(temporary_path, path)
            directory_fd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _read_optional(self, path: Path) -> Optional[bytes]:
        try:
            return path.read_bytes()
        except FileNotFoundError:
            return None

    def _restore_optional(self, path: Path, content: Optional[bytes], *, mode: int, kind: str) -> None:
        if content is None:
            path.unlink(missing_ok=True)
        else:
            self._atomic_write(path, content, mode=mode, kind=kind)

    def _load_registry(self) -> Registry:
        try:
            return parse_registry_text(self.registry_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise AdminError(f"mPulse registry does not exist: {self.registry_path}") from exc
        except RegistryError as exc:
            raise AdminError(str(exc)) from exc

    def _active_name(self) -> Optional[str]:
        try:
            return self.active_path.read_text(encoding="utf-8").strip() or None
        except FileNotFoundError:
            return None

    def _registry_checksum(self, registry: Registry) -> str:
        return hashlib.sha256(registry.canonical_json().encode("utf-8")).hexdigest()

    def _record(self, event: dict[str, Any]) -> None:
        safe_event = {**event, "timestamp": self.clock()}
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("a", encoding="utf-8") as history_file:
            history_file.write(json.dumps(safe_event, sort_keys=True) + "\n")
            history_file.flush()
            os.fsync(history_file.fileno())
        os.chmod(self.history_path, 0o640)
        self.apply_ownership(self.history_path, "state")
        self.audit(safe_event)

    def _backup_registry(self) -> None:
        if not self.registry_path.exists():
            return
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        backup_path = self.backups_dir / f"mpulse-profiles-{self.clock()}.json"
        self._atomic_write(backup_path, self.registry_path.read_bytes(), mode=0o640, kind="state")
        backups = sorted(self.backups_dir.glob("mpulse-profiles-*.json"))
        for stale in backups[: max(0, len(backups) - self.backup_limit)]:
            stale.unlink()

    def install_registry(self, text: str, *, actor: str) -> None:
        try:
            registry = parse_registry_text(text)
        except RegistryError as exc:
            raise AdminError(str(exc)) from exc
        with self._mutation_lock():
            active_name = self._active_name()
            if active_name and active_name not in registry.profiles:
                raise AdminError(f"Registry cannot remove active profile {active_name!r}")
            self._backup_registry()
            self._atomic_write(
                self.registry_path,
                registry.canonical_json().encode("utf-8"),
                mode=0o640,
                kind="registry",
            )
            self._record(
                {
                    "action": "install-registry",
                    "actor": actor,
                    "outcome": "success",
                    "registry_checksum": self._registry_checksum(registry),
                }
            )

    def _switch_locked(self, name: str, *, actor: str, action: str) -> None:
        registry = self._load_registry()
        try:
            profile = registry.profile(name)
        except RegistryError as exc:
            raise AdminError(str(exc)) from exc
        old_name = self._active_name()
        if old_name == name:
            self.verify(profile)
            return

        self.probe(profile)
        old_active = self._read_optional(self.active_path)
        old_previous = self._read_optional(self.previous_path)
        old_config = self._read_optional(self.browser_config_path)
        if old_name:
            self._atomic_write(self.previous_path, f"{old_name}\n".encode(), mode=0o640, kind="state")
        self._atomic_write(self.active_path, f"{name}\n".encode(), mode=0o640, kind="state")
        self._atomic_write(
            self.browser_config_path,
            render_browser_config(profile).encode("utf-8"),
            mode=0o640,
            kind="public",
        )

        event = {
            "action": action,
            "actor": actor,
            "endpoint_host": urlsplit(profile.script_base_url).hostname,
            "new_profile": name,
            "old_profile": old_name,
            "registry_checksum": self._registry_checksum(registry),
        }
        try:
            self.verify(profile)
        except Exception as exc:
            self._restore_optional(self.active_path, old_active, mode=0o640, kind="state")
            self._restore_optional(self.previous_path, old_previous, mode=0o640, kind="state")
            self._restore_optional(self.browser_config_path, old_config, mode=0o640, kind="public")
            self._record({**event, "outcome": "rolled-back"})
            if isinstance(exc, AdminError):
                raise
            raise AdminError(f"Profile verification failed: {exc}") from exc
        self._record({**event, "outcome": "success"})

    def switch(self, name: str, *, actor: str) -> None:
        with self._mutation_lock():
            self._switch_locked(name, actor=actor, action="switch")

    def rollback(self, *, actor: str) -> None:
        with self._mutation_lock():
            try:
                previous = self.previous_path.read_text(encoding="utf-8").strip()
            except FileNotFoundError as exc:
                raise AdminError("No previous profile is available for rollback") from exc
            if not previous:
                raise AdminError("No previous profile is available for rollback")
            self._switch_locked(previous, actor=actor, action="rollback")


def _load_public_base_url(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = payload["public_base_url"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise AdminError(f"Invalid mPulse administrator configuration: {path}") from exc
    if not isinstance(value, str) or not value.startswith("https://"):
        raise AdminError("Administrator public_base_url must use HTTPS")
    return value


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("install-registry")
    switch_parser = subparsers.add_parser("switch")
    switch_parser.add_argument("profile")
    subparsers.add_parser("rollback")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        public_base_url = _load_public_base_url(DEFAULT_ADMIN_CONFIG_PATH)
        admin = MPulseAdmin(verify=make_public_verifier(public_base_url))
        actor = os.environ.get("SUDO_USER") or os.environ.get("USER") or "unknown"
        if args.command == "install-registry":
            admin.install_registry(sys.stdin.read(), actor=actor)
        elif args.command == "switch":
            admin.switch(args.profile, actor=actor)
        else:
            admin.rollback(actor=actor)
    except (AdminError, RegistryError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
