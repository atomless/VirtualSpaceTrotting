#!/usr/bin/env python3
"""Install and operate host-managed mPulse profiles on a selected remote."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Optional, Sequence
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.deploy.remote_target import (  # noqa: E402
    DEFAULT_ENV_FILE,
    DEFAULT_REMOTE_RECEIPTS_DIR,
    scp_command_for_copy,
    select_remote,
    ssh_command_for_operation,
)
from scripts.mpulse_profiles import RegistryError, parse_registry_text  # noqa: E402

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
OPERATOR_GROUP = "vst-mpulse-operators"
REMOTE_ARCHIVE_PATH = "/tmp/vst-mpulse-admin-setup.tar.gz"
REMOTE_INSTALL_ROOT = "/tmp/vst-mpulse-admin-setup"


def render_caddyfile(remote_receipt: dict) -> str:
    public_base_url = remote_receipt["runtime"]["public_base_url"].rstrip("/")
    parsed = urlsplit(public_base_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path:
        raise ValueError("Remote public_base_url must be an HTTPS origin without a path")
    ssh_host = remote_receipt["ssh"]["host"]
    public_host = parsed.netloc
    return f"""http://{ssh_host} {{
\tredir {public_base_url}{{uri}} permanent
}}

{public_host} {{
\tencode zstd gzip

\thandle /mpulse-config.js {{
\t\troot * /var/opt/virtual-space-trotting/mpulse/public
\t\theader Cache-Control "no-store"
\t\theader Content-Type "application/javascript; charset=utf-8"
\t\tfile_server
\t}}

\thandle {{
\t\treverse_proxy 127.0.0.1:3000
\t}}

\t@htmlRoutes path / /maps* /categories* /blog*
\theader @htmlRoutes {{
\t\t-Cache-Control
\t\tContent-Type "text/html; charset=utf-8"
\t\tCache-Control "no-cache, max-age=0"
\t}}

\theader {{
\t\tX-Content-Type-Options "nosniff"
\t\tReferrer-Policy "strict-origin-when-cross-origin"
\t\tX-Frame-Options "DENY"
\t\tStrict-Transport-Security "max-age=300"
\t}}
}}
"""


def render_install_script(*, operator_user: str, initial_profile: str) -> str:
    user = shlex.quote(operator_user)
    profile = shlex.quote(initial_profile)
    return f"""#!/usr/bin/env bash
set -euo pipefail
umask 077

PAYLOAD_DIR="$(cd "$(dirname "$0")" && pwd)"
OPERATOR_USER={user}
INITIAL_PROFILE={profile}
OPERATOR_GROUP={OPERATOR_GROUP}
REGISTRY_PATH=/etc/opt/virtual-space-trotting/mpulse-profiles.json
CADDYFILE=/etc/caddy/Caddyfile
CADDY_BACKUP=/etc/caddy/Caddyfile.vst-mpulse-backup
SUDOERS_CANDIDATE=/etc/sudoers.d/.vst-mpulse.candidate

restore_caddy() {{
  local backup="$1"
  if [[ -f "${{backup}}" ]]; then
    install -o root -g root -m 0644 "${{backup}}" "${{CADDYFILE}}"
    caddy validate --config "${{CADDYFILE}}" --adapter caddyfile
    systemctl reload caddy
  fi
}}

getent passwd "${{OPERATOR_USER}}" >/dev/null
if ! getent group "${{OPERATOR_GROUP}}" >/dev/null; then
  groupadd --system {OPERATOR_GROUP}
fi
usermod -a -G {OPERATOR_GROUP} {user}

install -d -o root -g root -m 0755 /usr/local/lib/virtual-space-trotting
install -o root -g root -m 0755 "${{PAYLOAD_DIR}}/vst-mpulse" /usr/local/bin/vst-mpulse
install -o root -g root -m 0755 "${{PAYLOAD_DIR}}/vst-mpulse-admin" /usr/local/lib/virtual-space-trotting/vst-mpulse-admin
install -o root -g root -m 0644 "${{PAYLOAD_DIR}}/vst_mpulse_admin.py" /usr/local/lib/virtual-space-trotting/vst_mpulse_admin.py
install -o root -g root -m 0644 "${{PAYLOAD_DIR}}/mpulse_profiles.py" /usr/local/lib/virtual-space-trotting/mpulse_profiles.py

install -o root -g root -m 0644 "${{PAYLOAD_DIR}}/vst-mpulse-tmpfiles.conf" /etc/tmpfiles.d/vst-mpulse.conf
systemd-tmpfiles --create /etc/tmpfiles.d/vst-mpulse.conf

install -o root -g root -m 0440 "${{PAYLOAD_DIR}}/vst-mpulse-sudoers" "${{SUDOERS_CANDIDATE}}"
visudo -cf "${{SUDOERS_CANDIDATE}}"
install -o root -g root -m 0440 "${{SUDOERS_CANDIDATE}}" /etc/sudoers.d/vst-mpulse
rm -f "${{SUDOERS_CANDIDATE}}"

install -d -o root -g "${{OPERATOR_GROUP}}" -m 0750 /etc/opt/virtual-space-trotting
install -o root -g root -m 0644 "${{PAYLOAD_DIR}}/mpulse-admin.json" /etc/opt/virtual-space-trotting/mpulse-admin.json
if [[ -f "${{REGISTRY_PATH}}" ]]; then
  if ! cmp -s "${{PAYLOAD_DIR}}/mpulse-profiles.json" "${{REGISTRY_PATH}}"; then
    echo "Existing mPulse registry differs; use vst-mpulse registry edit instead of reinstalling." >&2
    exit 2
  fi
else
  install -o root -g "${{OPERATOR_GROUP}}" -m 0640 "${{PAYLOAD_DIR}}/mpulse-profiles.json" "${{REGISTRY_PATH}}"
fi

caddy validate --config "${{PAYLOAD_DIR}}/Caddyfile" --adapter caddyfile
install -o root -g root -m 0644 "${{CADDYFILE}}" "${{CADDY_BACKUP}}"
install -o root -g root -m 0644 "${{PAYLOAD_DIR}}/Caddyfile" "${{CADDYFILE}}"
if ! caddy validate --config "${{CADDYFILE}}" --adapter caddyfile || ! systemctl reload caddy; then
  restore_caddy "${{CADDY_BACKUP}}"
  exit 2
fi

if ! SUDO_USER="${{OPERATOR_USER}}" /usr/local/lib/virtual-space-trotting/vst-mpulse-admin switch "${{INITIAL_PROFILE}}"; then
  restore_caddy "${{CADDY_BACKUP}}"
  exit 2
fi
"""


def _write_payload(path: Path, content: str, mode: int) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)


def build_setup_archive(
    *,
    work_dir: Path,
    registry_file: Path,
    initial_profile: str,
    remote_receipt: dict,
) -> Path:
    try:
        registry = parse_registry_text(Path(registry_file).read_text(encoding="utf-8"))
        registry.profile(initial_profile)
    except (OSError, RegistryError) as exc:
        raise ValueError(f"Invalid mPulse registry: {exc}") from exc

    payload_dir = Path(work_dir) / "payload"
    payload_dir.mkdir(mode=0o700)
    _write_payload(payload_dir / "mpulse-profiles.json", registry.canonical_json(), 0o600)
    _write_payload(
        payload_dir / "mpulse-admin.json",
        json.dumps(
            {"public_base_url": remote_receipt["runtime"]["public_base_url"].rstrip("/")},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        0o600,
    )
    _write_payload(payload_dir / "Caddyfile", render_caddyfile(remote_receipt), 0o600)
    _write_payload(
        payload_dir / "install.sh",
        render_install_script(
            operator_user=remote_receipt["ssh"]["user"],
            initial_profile=initial_profile,
        ),
        0o700,
    )

    source_files = {
        "vst-mpulse": REPO_ROOT / "scripts" / "deploy" / "vst_mpulse.py",
        "vst-mpulse-admin": REPO_ROOT / "scripts" / "deploy" / "vst_mpulse_admin.py",
        "vst_mpulse_admin.py": REPO_ROOT / "scripts" / "deploy" / "vst_mpulse_admin.py",
        "mpulse_profiles.py": REPO_ROOT / "scripts" / "mpulse_profiles.py",
        "vst-mpulse-tmpfiles.conf": TEMPLATES_DIR / "vst-mpulse-tmpfiles.conf",
        "vst-mpulse-sudoers": TEMPLATES_DIR / "vst-mpulse-sudoers",
    }
    for destination_name, source_path in source_files.items():
        destination = payload_dir / destination_name
        destination.write_bytes(source_path.read_bytes())
        destination.chmod(0o700 if destination_name in {"vst-mpulse", "vst-mpulse-admin"} else 0o600)

    archive_path = Path(work_dir) / "vst-mpulse-admin-setup.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in sorted(payload_dir.iterdir()):
            archive.add(path, arcname=path.name, recursive=False)
    archive_path.chmod(0o600)
    return archive_path


def run_remote_install(remote_receipt: dict, archive_path: Path) -> int:
    upload = subprocess.run(
        scp_command_for_copy(remote_receipt, Path(archive_path), REMOTE_ARCHIVE_PATH),
        check=False,
    )
    if upload.returncode != 0:
        return int(upload.returncode)
    remote_script = f"""set -euo pipefail
chmod 600 {shlex.quote(REMOTE_ARCHIVE_PATH)}
rm -rf {shlex.quote(REMOTE_INSTALL_ROOT)}
mkdir -m 700 {shlex.quote(REMOTE_INSTALL_ROOT)}
tar -xzf {shlex.quote(REMOTE_ARCHIVE_PATH)} -C {shlex.quote(REMOTE_INSTALL_ROOT)}
sudo bash {shlex.quote(REMOTE_INSTALL_ROOT + '/install.sh')}
rm -rf {shlex.quote(REMOTE_INSTALL_ROOT)} {shlex.quote(REMOTE_ARCHIVE_PATH)}
"""
    install = subprocess.run(
        ssh_command_for_operation(remote_receipt, f"bash -c {shlex.quote(remote_script)}"),
        check=False,
    )
    return int(install.returncode)


def run_operator_command(remote_receipt: dict, command: Sequence[str]) -> int:
    remote_command = " ".join(shlex.quote(part) for part in ["vst-mpulse", *command])
    return int(subprocess.run(ssh_command_for_operation(remote_receipt, remote_command), check=False).returncode)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--receipts-dir", default=str(DEFAULT_REMOTE_RECEIPTS_DIR))
    parser.add_argument("--name")
    subparsers = parser.add_subparsers(dest="command", required=True)
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--registry-file", type=Path, required=True)
    install_parser.add_argument("--initial-profile", required=True)
    for command in ("list", "current", "verify"):
        subparsers.add_parser(command)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    receipt = select_remote(args.name, Path(args.env_file), Path(args.receipts_dir))
    if args.command != "install":
        return run_operator_command(receipt, [args.command])
    try:
        with tempfile.TemporaryDirectory(prefix="vst-mpulse-host-setup-") as temp_dir:
            archive = build_setup_archive(
                work_dir=Path(temp_dir),
                registry_file=args.registry_file,
                initial_profile=args.initial_profile,
                remote_receipt=receipt,
            )
            result = run_remote_install(receipt, archive)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if result == 0:
        print(f"mPulse administration installed on {receipt['identity']['name']}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
