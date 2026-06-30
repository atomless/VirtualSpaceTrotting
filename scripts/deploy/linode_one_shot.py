"""Provision or attach a Linode host and install the VirtualSpaceTrotting Spin service."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.deploy.linode_host_setup import (  # noqa: E402
    DEFAULT_IMAGE,
    DEFAULT_LINODE_API_URL,
    DEFAULT_PROFILE_TYPES,
    LinodeApiClient,
    ensure_ssh_keypair,
    resolve_linode_token,
    summarize_instance,
)
from scripts.deploy.local_env import ensure_env_file, upsert_env_value  # noqa: E402
from scripts.deploy.mpulse_host_setup import build_setup_archive, run_remote_install  # noqa: E402
from scripts.deploy.remote_target import (  # noqa: E402
    ACTIVE_REMOTE_ENV_KEY,
    DEFAULT_APP_DIR,
    DEFAULT_DURABLE_STATE_DIR,
    DEFAULT_REMOTE_RECEIPTS_DIR,
    DEFAULT_REMOTE_USER,
    DEFAULT_SERVICE_NAME,
    build_remote_receipt,
    copy_file_to_remote,
    shell_env_assignments,
    ssh_command_for_operation,
    write_json,
    write_remote_receipt,
)
from scripts.deploy.remote_target import build_release_bundle  # noqa: E402
from scripts.deploy.setup_common import DEFAULT_ENV_FILE, utc_now_iso  # noqa: E402

DEFAULT_RECEIPT_PATH = DEFAULT_DURABLE_STATE_DIR / "linode-deploy.json"
DEFAULT_REMOTE_RELEASE_ARCHIVE_PATH = "/tmp/vst-linode-release.tar.gz"
DEFAULT_REMOTE_RELEASE_METADATA_PATH = "/tmp/vst-linode-release.json"
DEFAULT_REMOTE_BOOTSTRAP_PATH = "/tmp/vst-linode-bootstrap.sh"
DEFAULT_PUBLIC_PORT = 3000
SSH_READY_ATTEMPTS = 60
SSH_READY_RETRY_DELAY_SECONDS = 2


def default_public_base_url(host: str, public_port: int) -> str:
    return f"http://{host}:{public_port}"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt-output", default=str(DEFAULT_RECEIPT_PATH))
    parser.add_argument("--remote-name", default="prod")
    parser.add_argument("--remote-receipts-dir", default=str(DEFAULT_REMOTE_RECEIPTS_DIR))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--linode-token", help="Linode Personal Access Token override")
    parser.add_argument("--no-store-token", action="store_true")
    parser.add_argument(
        "--ssh-private-key-file",
        default=str(Path("~/.ssh/virtual-space-trotting-linode").expanduser()),
    )
    parser.add_argument("--existing-instance-id", type=int)
    parser.add_argument("--label", default="virtual-space-trotting")
    parser.add_argument("--profile", choices=sorted(DEFAULT_PROFILE_TYPES), default="small")
    parser.add_argument("--region", default="us-east")
    parser.add_argument("--type", dest="linode_type", help="Linode type/plan override")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--public-base-url", help="Canonical public base URL")
    parser.add_argument("--public-port", type=int, default=DEFAULT_PUBLIC_PORT)
    parser.add_argument("--mpulse-registry-file", type=Path)
    parser.add_argument("--mpulse-profile")
    return parser.parse_args(argv)


def wait_for_ssh_ready(receipt: dict[str, Any], *, attempts: int = SSH_READY_ATTEMPTS) -> None:
    for attempt in range(1, attempts + 1):
        result = subprocess.run(
            ssh_command_for_operation(receipt, "true"),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return
        if attempt == attempts:
            detail = result.stderr.strip() or result.stdout.strip() or "SSH did not become ready in time."
            raise SystemExit(detail)
        time.sleep(SSH_READY_RETRY_DELAY_SECONDS)


def write_remote_bootstrap_script(work_dir: Path) -> Path:
    script_path = work_dir / "linode-bootstrap.sh"
    script_path.write_text(
        """#!/usr/bin/env bash
set -euo pipefail

: "${REMOTE_APP_DIR:?missing REMOTE_APP_DIR}"
: "${REMOTE_SERVICE_NAME:?missing REMOTE_SERVICE_NAME}"
: "${RELEASE_ARCHIVE_PATH:?missing RELEASE_ARCHIVE_PATH}"
: "${RELEASE_METADATA_PATH:?missing RELEASE_METADATA_PATH}"
: "${REMOTE_PUBLIC_PORT:?missing REMOTE_PUBLIC_PORT}"

NEXT_APP_DIR="${REMOTE_APP_DIR}.next"
PREV_APP_DIR="${REMOTE_APP_DIR}.prev"
FAILED_APP_DIR="${REMOTE_APP_DIR}.failed"

sudo apt-get update
sudo apt-get install -y ca-certificates curl

if ! command -v spin >/dev/null 2>&1; then
  spin_tmp="$(mktemp -d)"
  (
    cd "${spin_tmp}"
    curl -fsSL https://developer.fermyon.com/downloads/install.sh | bash
    sudo install -m 0755 spin /usr/local/bin/spin
  )
  rm -rf "${spin_tmp}"
fi

sudo rm -rf "${NEXT_APP_DIR}"
sudo mkdir -p "${NEXT_APP_DIR}"
sudo chown "$(id -u):$(id -g)" "${NEXT_APP_DIR}"
tar -xzf "${RELEASE_ARCHIVE_PATH}" -C "${NEXT_APP_DIR}"
cp "${RELEASE_METADATA_PATH}" "${NEXT_APP_DIR}/.vst-release.json"

if [[ -f "${REMOTE_APP_DIR}/.env.local" ]]; then
  sudo cp "${REMOTE_APP_DIR}/.env.local" "${NEXT_APP_DIR}/.env.local"
  sudo chown "$(id -u):$(id -g)" "${NEXT_APP_DIR}/.env.local"
  chmod 600 "${NEXT_APP_DIR}/.env.local"
fi

sudo rm -rf "${PREV_APP_DIR}"
if [[ -d "${REMOTE_APP_DIR}" ]]; then
  sudo mv "${REMOTE_APP_DIR}" "${PREV_APP_DIR}"
fi
sudo mv "${NEXT_APP_DIR}" "${REMOTE_APP_DIR}"
sudo chown -R "$(id -u):$(id -g)" "${REMOTE_APP_DIR}"

cat <<UNIT_FILE | sudo tee "/etc/systemd/system/${REMOTE_SERVICE_NAME}.service" >/dev/null
[Unit]
Description=VirtualSpaceTrotting Spin site
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(id -un)
Group=$(id -gn)
WorkingDirectory=${REMOTE_APP_DIR}
ExecStart=/usr/local/bin/spin up --listen 0.0.0.0:${REMOTE_PUBLIC_PORT} --file ${REMOTE_APP_DIR}/spin.toml
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT_FILE

sudo systemctl daemon-reload
sudo systemctl enable "${REMOTE_SERVICE_NAME}"
if ! sudo systemctl restart "${REMOTE_SERVICE_NAME}"; then
  echo "Remote service restart failed; attempting rollback." >&2
  if [[ -d "${PREV_APP_DIR}" ]]; then
    sudo rm -rf "${FAILED_APP_DIR}"
    sudo mv "${REMOTE_APP_DIR}" "${FAILED_APP_DIR}" || true
    sudo mv "${PREV_APP_DIR}" "${REMOTE_APP_DIR}"
    sudo chown -R "$(id -u):$(id -g)" "${REMOTE_APP_DIR}"
    sudo systemctl restart "${REMOTE_SERVICE_NAME}" || true
  fi
  exit 1
fi

for attempt in $(seq 1 20); do
  if curl -fsS --max-time 8 "http://127.0.0.1:${REMOTE_PUBLIC_PORT}/health" >/dev/null; then
    exit 0
  fi
  sleep 2
done

sudo journalctl -u "${REMOTE_SERVICE_NAME}" -n 120 --no-pager >&2 || true
exit 1
""",
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    return script_path


def run_remote_bootstrap(receipt: dict[str, Any], *, public_port: int) -> int:
    runtime = receipt["runtime"]
    env_values = {
        "REMOTE_APP_DIR": runtime["app_dir"],
        "REMOTE_SERVICE_NAME": runtime["service_name"],
        "RELEASE_ARCHIVE_PATH": DEFAULT_REMOTE_RELEASE_ARCHIVE_PATH,
        "RELEASE_METADATA_PATH": DEFAULT_REMOTE_RELEASE_METADATA_PATH,
        "REMOTE_PUBLIC_PORT": str(public_port),
    }
    remote_command = f"{shell_env_assignments(env_values)} bash {shlex.quote(DEFAULT_REMOTE_BOOTSTRAP_PATH)}"
    result = subprocess.run(ssh_command_for_operation(receipt, remote_command), check=False)
    return int(result.returncode)


def provision_or_inspect_instance(
    *,
    client: LinodeApiClient,
    args: argparse.Namespace,
    ssh_public_key: str,
) -> tuple[str, dict[str, Any]]:
    if args.existing_instance_id:
        return "existing-instance", client.get_instance(args.existing_instance_id)

    created = client.create_instance(
        label=args.label,
        region=args.region,
        linode_type=args.linode_type or DEFAULT_PROFILE_TYPES[args.profile],
        image=args.image,
        ssh_public_key=ssh_public_key,
    )
    return "fresh-instance", client.wait_for_instance_running(int(created["id"]))


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if bool(args.mpulse_registry_file) != bool(args.mpulse_profile):
        raise SystemExit("--mpulse-registry-file and --mpulse-profile must be supplied together.")
    if args.mpulse_registry_file and not (args.public_base_url or "").startswith("https://"):
        raise SystemExit("mPulse host initialization requires an explicit HTTPS --public-base-url.")
    env_file = Path(args.env_file).expanduser().resolve()
    receipt_output = Path(args.receipt_output).expanduser().resolve()
    remote_receipts_dir = Path(args.remote_receipts_dir).expanduser().resolve()
    ensure_env_file(env_file)

    token = resolve_linode_token(args, env_file)
    private_key_path, public_key_path, public_key = ensure_ssh_keypair(Path(args.ssh_private_key_file))

    client = LinodeApiClient(token)
    client.validate_token()
    mode, details = provision_or_inspect_instance(client=client, args=args, ssh_public_key=public_key)

    instance = summarize_instance(details)
    public_ipv4 = str(instance["public_ipv4"])
    if not public_ipv4:
        raise SystemExit("Linode instance did not expose a public IPv4 address.")

    public_base_url = (args.public_base_url or default_public_base_url(public_ipv4, args.public_port)).rstrip("/")
    if not args.no_store_token:
        upsert_env_value(env_file, "LINODE_TOKEN", token)

    transient_receipt = build_remote_receipt(
        name=args.remote_name,
        provider_kind="linode",
        host=public_ipv4,
        port=22,
        user=DEFAULT_REMOTE_USER,
        private_key_path=str(private_key_path),
        public_base_url=public_base_url,
        app_dir=DEFAULT_APP_DIR,
        service_name=DEFAULT_SERVICE_NAME,
        provider_extension={"linode": {key: value for key, value in instance.items() if value is not None}},
    )
    wait_for_ssh_ready(transient_receipt)

    with tempfile.TemporaryDirectory(prefix="vst-linode-deploy-") as temp_dir:
        work_dir = Path(temp_dir)
        archive_path, metadata_path, metadata = build_release_bundle(
            repo_root=REPO_ROOT,
            work_dir=work_dir,
        )
        bootstrap_path = write_remote_bootstrap_script(work_dir)
        copy_file_to_remote(transient_receipt, archive_path, DEFAULT_REMOTE_RELEASE_ARCHIVE_PATH)
        copy_file_to_remote(transient_receipt, metadata_path, DEFAULT_REMOTE_RELEASE_METADATA_PATH)
        copy_file_to_remote(transient_receipt, bootstrap_path, DEFAULT_REMOTE_BOOTSTRAP_PATH)
        if run_remote_bootstrap(transient_receipt, public_port=args.public_port) != 0:
            raise SystemExit("Remote bootstrap failed; inspect the Linode journal for virtual-space-trotting.")
        if args.mpulse_registry_file:
            try:
                mpulse_archive = build_setup_archive(
                    work_dir=work_dir,
                    registry_file=args.mpulse_registry_file,
                    initial_profile=args.mpulse_profile,
                    remote_receipt=transient_receipt,
                )
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            if run_remote_install(transient_receipt, mpulse_archive) != 0:
                raise SystemExit("Remote mPulse administration setup failed.")

    deployed_at = utc_now_iso()
    commit = str(metadata.get("commit") or "")
    remote_receipt_path = write_remote_receipt(
        receipts_dir=remote_receipts_dir,
        name=args.remote_name,
        provider_kind="linode",
        host=public_ipv4,
        user=DEFAULT_REMOTE_USER,
        private_key_path=str(private_key_path),
        public_base_url=public_base_url,
        app_dir=DEFAULT_APP_DIR,
        service_name=DEFAULT_SERVICE_NAME,
        last_deployed_commit=commit,
        last_deployed_at_utc=deployed_at,
        provider_extension={"linode": {key: value for key, value in instance.items() if value is not None}},
    )
    upsert_env_value(env_file, ACTIVE_REMOTE_ENV_KEY, args.remote_name)

    write_json(
        receipt_output,
        {
            "schema": "virtual_space_trotting.linode_deploy.v1",
            "mode": mode,
            "created_at_utc": deployed_at,
            "linode": instance,
            "ssh": {
                "user": DEFAULT_REMOTE_USER,
                "private_key_path": str(private_key_path),
                "public_key_path": str(public_key_path),
            },
            "runtime": {
                "app_dir": DEFAULT_APP_DIR,
                "service_name": DEFAULT_SERVICE_NAME,
                "public_base_url": public_base_url,
                "public_port": args.public_port,
            },
            "deploy": {
                "commit": commit,
                "dirty_worktree": bool(metadata.get("dirty_worktree")),
            },
            "remote_receipt_path": str(remote_receipt_path),
        },
    )

    print(f"Linode deploy complete: {public_base_url} (commit={commit})")
    print(f"Remote receipt: {remote_receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
