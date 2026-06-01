import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.deploy import linode_host_setup as setup


class FakeLinodeClient:
    def __init__(self, token: str, base_url: str = setup.DEFAULT_LINODE_API_URL) -> None:
        self.token = token
        self.base_url = base_url
        self.calls: list[tuple[str, object]] = []

    def validate_token(self) -> dict[str, object]:
        self.calls.append(("validate_token", None))
        return {"username": "jamestindall"}

    def create_instance(
        self,
        *,
        label: str,
        region: str,
        linode_type: str,
        image: str,
        ssh_public_key: str,
    ) -> dict[str, object]:
        self.calls.append(
            (
                "create_instance",
                {
                    "label": label,
                    "region": region,
                    "linode_type": linode_type,
                    "image": image,
                    "ssh_public_key": ssh_public_key,
                },
            )
        )
        return {"id": 123}

    def wait_for_instance_running(self, instance_id: int, *, attempts: int = 90, poll_interval_seconds: int = 2):
        self.calls.append(("wait_for_instance_running", instance_id))
        return {
            "id": instance_id,
            "label": "vst-test",
            "status": "running",
            "ipv4": ["198.51.100.24"],
            "region": "us-east",
            "type": "g6-nanode-1",
            "image": "linode/ubuntu24.04",
        }

    def get_instance(self, instance_id: int) -> dict[str, object]:
        self.calls.append(("get_instance", instance_id))
        return {
            "id": instance_id,
            "label": "existing-vst",
            "status": "running",
            "ipv4": ["198.51.100.25"],
            "region": "us-east",
            "type": "g6-nanode-1",
            "image": "linode/ubuntu24.04",
        }


class LinodeHostSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vst-linode-"))
        self.env_file = self.temp_dir / ".env.local"
        self.receipt_path = self.temp_dir / ".vst" / "linode-host-setup.json"
        self.remote_receipts_dir = self.temp_dir / ".vst" / "remotes"

    def test_fresh_instance_persists_env_setup_receipt_and_remote_receipt(self) -> None:
        client = FakeLinodeClient("linode-secret")

        with patch.object(setup, "LinodeApiClient", return_value=client), patch.object(
            setup,
            "ensure_ssh_keypair",
            return_value=(
                Path("/Users/test/.ssh/virtual-space-trotting-linode"),
                Path("/Users/test/.ssh/virtual-space-trotting-linode.pub"),
                "ssh-ed25519 AAAATEST virtual-space-trotting-linode",
            ),
        ):
            rc = setup.main(
                [
                    "--linode-token",
                    "linode-secret",
                    "--env-file",
                    str(self.env_file),
                    "--receipt-output",
                    str(self.receipt_path),
                    "--remote-name",
                    "prod",
                    "--remote-receipts-dir",
                    str(self.remote_receipts_dir),
                    "--label",
                    "vst-test",
                    "--operator-ip",
                    "203.0.113.8/32",
                    "--yes",
                ]
            )

        self.assertEqual(rc, 0)
        env_text = self.env_file.read_text(encoding="utf-8")
        self.assertIn("LINODE_TOKEN=linode-secret", env_text)
        self.assertIn("VST_OPERATOR_IP_ALLOWLIST=203.0.113.8/32", env_text)
        self.assertIn("VST_ACTIVE_REMOTE=prod", env_text)

        receipt = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["mode"], "fresh-instance")
        self.assertEqual(receipt["linode"]["instance_id"], 123)
        self.assertEqual(receipt["linode"]["public_ipv4"], "198.51.100.24")
        self.assertEqual(receipt["ssh"]["user"], "vst")

        remote_receipt = json.loads((self.remote_receipts_dir / "prod.json").read_text(encoding="utf-8"))
        self.assertEqual(remote_receipt["schema"], "virtual_space_trotting.remote_target.v1")
        self.assertEqual(remote_receipt["runtime"]["service_name"], "virtual-space-trotting")
        self.assertEqual(remote_receipt["provider"]["linode"]["instance_id"], 123)

    def test_existing_instance_uses_saved_token_without_creating_instance(self) -> None:
        self.env_file.write_text("LINODE_TOKEN=stored-token\n", encoding="utf-8")
        client = FakeLinodeClient("stored-token")

        with patch.object(setup, "LinodeApiClient", return_value=client), patch.object(
            setup,
            "ensure_ssh_keypair",
            return_value=(
                Path("/Users/test/.ssh/virtual-space-trotting-linode"),
                Path("/Users/test/.ssh/virtual-space-trotting-linode.pub"),
                "ssh-ed25519 AAAATEST virtual-space-trotting-linode",
            ),
        ):
            rc = setup.main(
                [
                    "--env-file",
                    str(self.env_file),
                    "--receipt-output",
                    str(self.receipt_path),
                    "--remote-name",
                    "prod",
                    "--remote-receipts-dir",
                    str(self.remote_receipts_dir),
                    "--existing-instance-id",
                    "456",
                    "--operator-ip",
                    "198.51.100.9/32",
                    "--yes",
                ]
            )

        self.assertEqual(rc, 0)
        self.assertIn(("get_instance", 456), client.calls)
        self.assertFalse(any(name == "create_instance" for name, _ in client.calls))
        receipt = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["mode"], "existing-instance")
        self.assertEqual(receipt["linode"]["instance_id"], 456)
        remote_receipt = json.loads((self.remote_receipts_dir / "prod.json").read_text(encoding="utf-8"))
        self.assertEqual(remote_receipt["ssh"]["host"], "198.51.100.25")
        self.assertEqual(remote_receipt["runtime"]["public_base_url"], "https://198.51.100.25.sslip.io")


if __name__ == "__main__":
    unittest.main()
