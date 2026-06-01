"""Agent-oriented Linode host setup helper for VirtualSpaceTrotting."""

from __future__ import annotations

import argparse
import base64
import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.deploy.local_env import ensure_env_file, read_env_value, upsert_env_value
from scripts.deploy.remote_target import (
    ACTIVE_REMOTE_ENV_KEY,
    DEFAULT_APP_DIR,
    DEFAULT_DURABLE_STATE_DIR,
    DEFAULT_REMOTE_RECEIPTS_DIR,
    DEFAULT_REMOTE_USER,
    DEFAULT_SERVICE_NAME,
    activate_remote,
    default_public_base_url,
    write_remote_receipt,
)
from scripts.deploy.setup_common import (
    DEFAULT_ENV_FILE,
    prompt_secret,
    utc_now_iso,
    write_json,
)

DEFAULT_RECEIPT_PATH = DEFAULT_DURABLE_STATE_DIR / "linode-host-setup.json"
DEFAULT_LINODE_API_URL = "https://api.linode.com/v4"
DEFAULT_IMAGE = "linode/ubuntu24.04"
DEFAULT_PROFILE_TYPES = {
    "small": "g6-nanode-1",
    "medium": "g6-standard-1",
    "large": "g6-standard-2",
}


def ensure_ssh_keypair(private_key_path: Path, comment: str = "virtual-space-trotting-linode") -> tuple[Path, Path, str]:
    private_key_path = private_key_path.expanduser().resolve()
    public_key_path = Path(f"{private_key_path}.pub")
    private_key_path.parent.mkdir(parents=True, exist_ok=True)

    if not private_key_path.exists():
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f", str(private_key_path), "-C", comment, "-N", ""],
            check=True,
            capture_output=True,
            text=True,
        )

    if not public_key_path.exists():
        derived = subprocess.run(
            ["ssh-keygen", "-y", "-f", str(private_key_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        public_key_path.write_text(derived.stdout.strip() + "\n", encoding="utf-8")

    private_key_path.chmod(0o600)
    public_key_path.chmod(0o644)
    public_key = public_key_path.read_text(encoding="utf-8").strip()
    if not public_key:
        raise SystemExit(f"SSH public key file is empty: {public_key_path}")
    return private_key_path, public_key_path, public_key


def build_cloud_init(ssh_public_key: str) -> str:
    return "\n".join(
        [
            "#cloud-config",
            "users:",
            f"  - name: {DEFAULT_REMOTE_USER}",
            "    groups: sudo",
            "    shell: /bin/bash",
            "    sudo: ALL=(ALL) NOPASSWD:ALL",
            "    ssh_authorized_keys:",
            f"      - {ssh_public_key}",
            "disable_root: true",
            "ssh_pwauth: false",
            "package_update: true",
            "",
        ]
    )


class LinodeApiClient:
    def __init__(self, token: str, base_url: str = DEFAULT_LINODE_API_URL) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")

    def request_json(self, method: str, path: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
                reasons = [entry.get("reason", "") for entry in payload.get("errors", [])]
                reason = "; ".join(part for part in reasons if part) or body
            except json.JSONDecodeError:
                reason = body
            raise SystemExit(f"Linode API {method} {path} failed (HTTP {exc.code}): {reason}") from exc
        except urllib.error.URLError as exc:
            raise SystemExit(f"Linode API {method} {path} failed: {exc.reason}") from exc

    def validate_token(self) -> dict[str, Any]:
        return self.request_json("GET", "/profile")

    def create_instance(
        self,
        *,
        label: str,
        region: str,
        linode_type: str,
        image: str,
        ssh_public_key: str,
    ) -> dict[str, Any]:
        cloud_init = build_cloud_init(ssh_public_key)
        payload = {
            "region": region,
            "type": linode_type,
            "image": image,
            "label": label,
            "root_pass": secrets.token_hex(24),
            "booted": True,
            "metadata": {"user_data": base64.b64encode(cloud_init.encode("utf-8")).decode("utf-8")},
        }
        return self.request_json("POST", "/linode/instances", payload)

    def get_instance(self, instance_id: int) -> dict[str, Any]:
        return self.request_json("GET", f"/linode/instances/{instance_id}")

    def wait_for_instance_running(
        self,
        instance_id: int,
        *,
        attempts: int = 90,
        poll_interval_seconds: int = 2,
    ) -> dict[str, Any]:
        latest: dict[str, Any] = {}
        for _ in range(attempts):
            latest = self.get_instance(instance_id)
            ipv4 = latest.get("ipv4") or []
            if latest.get("status") == "running" and ipv4:
                return latest
            time.sleep(poll_interval_seconds)
        raise SystemExit(f"Linode instance {instance_id} did not reach running state with an IPv4 address in time.")


def summarize_instance(details: dict[str, Any]) -> dict[str, Any]:
    ipv4 = details.get("ipv4") or []
    return {
        "instance_id": details.get("id"),
        "label": details.get("label"),
        "status": details.get("status"),
        "public_ipv4": ipv4[0] if ipv4 else "",
        "region": details.get("region"),
        "type": details.get("type"),
        "image": details.get("image"),
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt-output", default=str(DEFAULT_RECEIPT_PATH))
    parser.add_argument("--remote-name", help="Day-2 remote target name to emit")
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
    parser.add_argument("--public-base-url", help="Canonical public base URL; defaults to sslip.io for the server IPv4")
    return parser.parse_args(argv)


def resolve_linode_token(args: argparse.Namespace, env_file: Path) -> str:
    token = (args.linode_token or read_env_value(env_file, "LINODE_TOKEN")).strip()
    if token:
        return token
    token = prompt_secret("Linode Personal Access Token: ").strip()
    if not token:
        raise SystemExit("LINODE_TOKEN cannot be blank.")
    return token


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    env_file = Path(args.env_file).expanduser().resolve()
    receipt_output = Path(args.receipt_output).expanduser().resolve()
    remote_receipts_dir = Path(args.remote_receipts_dir).expanduser().resolve()
    ensure_env_file(env_file)

    token = resolve_linode_token(args, env_file)
    private_key_path, public_key_path, public_key = ensure_ssh_keypair(Path(args.ssh_private_key_file))

    client = LinodeApiClient(token)
    client.validate_token()

    mode = "existing-instance" if args.existing_instance_id else "fresh-instance"
    if args.existing_instance_id:
        details = client.get_instance(args.existing_instance_id)
    else:
        created = client.create_instance(
            label=args.label,
            region=args.region,
            linode_type=args.linode_type or DEFAULT_PROFILE_TYPES[args.profile],
            image=args.image,
            ssh_public_key=public_key,
        )
        details = client.wait_for_instance_running(int(created["id"]))

    instance = summarize_instance(details)
    public_ipv4 = str(instance["public_ipv4"])
    if not public_ipv4:
        raise SystemExit("Linode instance did not expose a public IPv4 address.")
    public_base_url = (args.public_base_url or default_public_base_url(public_ipv4)).rstrip("/")
    remote_name = args.remote_name or str(instance["label"] or "prod")

    if not args.no_store_token:
        upsert_env_value(env_file, "LINODE_TOKEN", token)

    remote_receipt_path = write_remote_receipt(
        receipts_dir=remote_receipts_dir,
        name=remote_name,
        provider_kind="linode",
        host=public_ipv4,
        user=DEFAULT_REMOTE_USER,
        private_key_path=str(private_key_path),
        public_base_url=public_base_url,
        app_dir=DEFAULT_APP_DIR,
        service_name=DEFAULT_SERVICE_NAME,
        last_deployed_at_utc=utc_now_iso(),
        provider_extension={"linode": {key: value for key, value in instance.items() if value is not None}},
    )
    activate_remote(env_file, remote_receipts_dir, remote_name)

    receipt = {
        "schema": "virtual_space_trotting.linode_host_setup.v1",
        "mode": mode,
        "created_at_utc": utc_now_iso(),
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
        },
        "remote_receipt_path": str(remote_receipt_path),
    }
    write_json(receipt_output, receipt)
    print(f"Linode host ready: {public_ipv4} ({mode})")
    print(f"Remote receipt: {remote_receipt_path}")
    print(f"Active remote stored in {env_file}: {ACTIVE_REMOTE_ENV_KEY}={remote_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
