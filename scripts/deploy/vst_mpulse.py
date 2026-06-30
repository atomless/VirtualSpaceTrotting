#!/usr/bin/env python3
"""Operator interface for host-managed mPulse profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional, Sequence, TextIO
from urllib.parse import urlsplit

try:
    from scripts.deploy.vst_mpulse_admin import (
        DEFAULT_ADMIN_CONFIG_PATH,
        DEFAULT_REGISTRY_PATH,
        DEFAULT_STATE_DIR,
        default_probe,
        make_public_verifier,
    )
    from scripts.mpulse_profiles import Profile, Registry, RegistryError, parse_registry_text
except ModuleNotFoundError:
    installed_lib_dir = Path("/usr/local/lib/virtual-space-trotting")
    sys.path.insert(0, str(installed_lib_dir if installed_lib_dir.exists() else Path(__file__).resolve().parent))
    from mpulse_profiles import Profile, Registry, RegistryError, parse_registry_text
    from vst_mpulse_admin import (
        DEFAULT_ADMIN_CONFIG_PATH,
        DEFAULT_REGISTRY_PATH,
        DEFAULT_STATE_DIR,
        default_probe,
        make_public_verifier,
    )


DEFAULT_HELPER_PATH = Path("/usr/local/lib/virtual-space-trotting/vst-mpulse-admin")


class CLIError(RuntimeError):
    """Raised when an operator command cannot be completed."""


def default_editor(path: Path) -> int:
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    command = [*shlex.split(editor), str(path)]
    return int(subprocess.run(command, check=False).returncode)


class MPulseCLI:
    def __init__(
        self,
        *,
        registry_path: Path = DEFAULT_REGISTRY_PATH,
        state_dir: Path = DEFAULT_STATE_DIR,
        helper_path: Path = DEFAULT_HELPER_PATH,
        admin_config_path: Path = DEFAULT_ADMIN_CONFIG_PATH,
        run_privileged: Optional[Callable[..., int]] = None,
        run_editor: Callable[[Path], int] = default_editor,
        probe: Callable[[Profile], None] = default_probe,
        verify_public: Optional[Callable[[Profile], None]] = None,
        output: TextIO = sys.stdout,
    ) -> None:
        self.registry_path = Path(registry_path)
        self.state_dir = Path(state_dir)
        self.helper_path = Path(helper_path)
        self.admin_config_path = Path(admin_config_path)
        self.run_privileged = run_privileged or self._run_privileged
        self.run_editor = run_editor
        self.probe = probe
        self.verify_public = verify_public or self._verify_public
        self.output = output

    @property
    def active_path(self) -> Path:
        return self.state_dir / "active-profile"

    @property
    def history_path(self) -> Path:
        return self.state_dir / "history.jsonl"

    def _registry(self) -> Registry:
        try:
            return parse_registry_text(self.registry_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CLIError(f"mPulse registry does not exist: {self.registry_path}") from exc
        except RegistryError as exc:
            raise CLIError(str(exc)) from exc

    def _active_name(self) -> str:
        try:
            name = self.active_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise CLIError("No mPulse profile is active") from exc
        if not name:
            raise CLIError("No mPulse profile is active")
        return name

    def _current_profile(self) -> Profile:
        registry = self._registry()
        try:
            return registry.profile(self._active_name())
        except RegistryError as exc:
            raise CLIError(str(exc)) from exc

    def _run_privileged(self, args: Sequence[str], input_text: Optional[str] = None) -> int:
        result = subprocess.run(
            ["sudo", str(self.helper_path), *args],
            input=input_text,
            text=True,
            check=False,
        )
        return int(result.returncode)

    def _verify_public(self, profile: Profile) -> None:
        try:
            payload = json.loads(self.admin_config_path.read_text(encoding="utf-8"))
            public_base_url = payload["public_base_url"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise CLIError(f"Invalid administrator configuration: {self.admin_config_path}") from exc
        make_public_verifier(public_base_url)(profile)

    def _privileged(self, args: Sequence[str], input_text: Optional[str] = None) -> None:
        if self.run_privileged(args, input_text) != 0:
            raise CLIError(f"Privileged mPulse operation failed: {' '.join(args)}")

    def list_profiles(self) -> None:
        registry = self._registry()
        try:
            active = self._active_name()
        except CLIError:
            active = ""
        for name, profile in sorted(registry.profiles.items()):
            marker = "*" if name == active else " "
            host = urlsplit(profile.script_base_url).hostname or ""
            print(f"{marker} {name:<24} {host:<40} {profile.description}", file=self.output)

    def show_current(self) -> None:
        profile = self._current_profile()
        fingerprint = hashlib.sha256(profile.api_key.encode("ascii")).hexdigest()[:12]
        host = urlsplit(profile.script_base_url).hostname or ""
        print(f"profile: {profile.name}", file=self.output)
        print(f"endpoint: {host}", file=self.output)
        print(f"key fingerprint: sha256:{fingerprint}", file=self.output)

    def verify(self) -> None:
        profile = self._current_profile()
        self.probe(profile)
        self.verify_public(profile)
        print(f"mPulse profile verified: {profile.name}", file=self.output)

    def show_history(self) -> None:
        try:
            lines = self.history_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            print("No mPulse profile history.", file=self.output)
            return
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            old_name = event.get("old_profile") or "none"
            new_name = event.get("new_profile") or "none"
            print(
                f"{event.get('timestamp', '?')} {event.get('actor', '?')} "
                f"{event.get('action', '?')} {old_name} -> {new_name} {event.get('outcome', '?')}",
                file=self.output,
            )

    def validate_registry_file(self, path: Path) -> Registry:
        try:
            registry = parse_registry_text(Path(path).read_text(encoding="utf-8"))
        except (OSError, RegistryError) as exc:
            raise CLIError(str(exc)) from exc
        print(f"mPulse registry is valid: {len(registry.profiles)} profile(s)", file=self.output)
        return registry

    def edit_registry(self) -> None:
        original = self._registry()
        original_json = original.canonical_json()
        descriptor, temporary_name = tempfile.mkstemp(prefix="vst-mpulse-profiles-", suffix=".json")
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
                temporary_file.write(original_json)
            os.chmod(temporary_path, 0o600)
            if self.run_editor(temporary_path) != 0:
                raise CLIError("Registry edit was cancelled")
            try:
                updated = parse_registry_text(temporary_path.read_text(encoding="utf-8"))
            except RegistryError as exc:
                raise CLIError(str(exc)) from exc
            updated_json = updated.canonical_json()
            if updated_json == original_json:
                print("mPulse registry unchanged.", file=self.output)
                return
            for name, profile in updated.profiles.items():
                if name not in original.profiles or profile != original.profiles[name]:
                    self.probe(profile)
            self._privileged(["install-registry"], updated_json)
            print("mPulse registry installed.", file=self.output)
        finally:
            temporary_path.unlink(missing_ok=True)

    def switch(self, name: str) -> None:
        try:
            self._registry().profile(name)
        except RegistryError as exc:
            raise CLIError(str(exc)) from exc
        self._privileged(["switch", name])

    def rollback(self) -> None:
        self._privileged(["rollback"])


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    subparsers.add_parser("current")
    subparsers.add_parser("verify")
    subparsers.add_parser("history")
    switch_parser = subparsers.add_parser("switch")
    switch_parser.add_argument("profile")
    subparsers.add_parser("rollback")
    registry_parser = subparsers.add_parser("registry")
    registry_subparsers = registry_parser.add_subparsers(dest="registry_command", required=True)
    validate_parser = registry_subparsers.add_parser("validate")
    validate_parser.add_argument("path", type=Path)
    registry_subparsers.add_parser("edit")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    cli = MPulseCLI()
    try:
        if args.command == "list":
            cli.list_profiles()
        elif args.command == "current":
            cli.show_current()
        elif args.command == "verify":
            cli.verify()
        elif args.command == "history":
            cli.show_history()
        elif args.command == "switch":
            cli.switch(args.profile)
        elif args.command == "rollback":
            cli.rollback()
        elif args.registry_command == "validate":
            cli.validate_registry_file(args.path)
        else:
            cli.edit_registry()
    except (CLIError, RegistryError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
