import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.deploy import linode_one_shot as deploy


class FakeLinodeClient:
    def __init__(self, token: str, base_url: str = deploy.DEFAULT_LINODE_API_URL) -> None:
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


class LinodeOneShotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vst-linode-deploy-"))
        self.env_file = self.temp_dir / ".env.local"
        self.receipt_path = self.temp_dir / ".vst" / "linode-deploy.json"
        self.remote_receipts_dir = self.temp_dir / ".vst" / "remotes"
        self.bundle_dir = self.temp_dir / "bundle"
        self.bundle_dir.mkdir()
        self.archive_path = self.bundle_dir / "release.tar.gz"
        self.archive_path.write_text("release\n", encoding="utf-8")
        self.metadata_path = self.bundle_dir / "release.json"
        self.metadata_path.write_text(json.dumps({"commit": "deadbeef", "dirty_worktree": False}) + "\n")
        self.bootstrap_path = self.bundle_dir / "bootstrap.sh"
        self.bootstrap_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    def test_remote_bootstrap_script_installs_spin_service_and_health_checks(self) -> None:
        script_path = deploy.write_remote_bootstrap_script(self.temp_dir)

        script = script_path.read_text(encoding="utf-8")
        self.assertIn("https://developer.fermyon.com/downloads/install.sh", script)
        self.assertIn("sudo mkdir -p \"${NEXT_APP_DIR}\"", script)
        self.assertIn("sudo mv \"${NEXT_APP_DIR}\" \"${REMOTE_APP_DIR}\"", script)
        self.assertIn("User=$(id -un)", script)
        self.assertIn("sudo tee \"/etc/systemd/system/${REMOTE_SERVICE_NAME}.service\"", script)
        self.assertIn("ExecStart=/usr/local/bin/spin up --listen 0.0.0.0:${REMOTE_PUBLIC_PORT}", script)
        self.assertIn("http://127.0.0.1:${REMOTE_PUBLIC_PORT}/health", script)

    def test_deploy_can_build_release_without_boomerang_api_key(self) -> None:
        client = FakeLinodeClient("linode-secret")

        with patch.object(deploy, "LinodeApiClient", return_value=client), patch.object(
            deploy,
            "ensure_ssh_keypair",
            return_value=(
                Path("/Users/test/.ssh/virtual-space-trotting-linode"),
                Path("/Users/test/.ssh/virtual-space-trotting-linode.pub"),
                "ssh-ed25519 AAAATEST virtual-space-trotting-linode",
            ),
        ), patch.object(deploy, "wait_for_ssh_ready", return_value=None), patch.object(
            deploy,
            "build_release_bundle",
            return_value=(self.archive_path, self.metadata_path, {"commit": "deadbeef", "dirty_worktree": False}),
        ) as build_release, patch.object(
            deploy, "write_remote_bootstrap_script", return_value=self.bootstrap_path
        ), patch.object(
            deploy, "copy_file_to_remote"
        ), patch.object(
            deploy, "run_remote_bootstrap", return_value=0
        ):
            rc = deploy.main(
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
                ]
            )

        self.assertEqual(rc, 0)
        self.assertIsNone(build_release.call_args.kwargs["boomerang_api_key"])

    def test_fresh_deploy_creates_instance_uploads_release_and_writes_receipts(self) -> None:
        self.env_file.write_text("BOOMERANG_API_KEY=ABCDE-FGHIJ-KLMNO-PQRST-UVWXY\n", encoding="utf-8")
        client = FakeLinodeClient("linode-secret")

        with patch.object(deploy, "LinodeApiClient", return_value=client), patch.object(
            deploy,
            "ensure_ssh_keypair",
            return_value=(
                Path("/Users/test/.ssh/virtual-space-trotting-linode"),
                Path("/Users/test/.ssh/virtual-space-trotting-linode.pub"),
                "ssh-ed25519 AAAATEST virtual-space-trotting-linode",
            ),
        ), patch.object(deploy, "wait_for_ssh_ready", return_value=None), patch.object(
            deploy,
            "build_release_bundle",
            return_value=(self.archive_path, self.metadata_path, {"commit": "deadbeef", "dirty_worktree": False}),
        ), patch.object(
            deploy, "write_remote_bootstrap_script", return_value=self.bootstrap_path
        ), patch.object(
            deploy, "copy_file_to_remote"
        ) as copy_file, patch.object(
            deploy, "run_remote_bootstrap", return_value=0
        ) as run_bootstrap:
            rc = deploy.main(
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
                ]
            )

        self.assertEqual(rc, 0)
        self.assertIn(("create_instance", unittest.mock.ANY), client.calls)
        self.assertEqual(
            [call.args[2] for call in copy_file.call_args_list],
            [
                "/tmp/vst-linode-release.tar.gz",
                "/tmp/vst-linode-release.json",
                "/tmp/vst-linode-bootstrap.sh",
            ],
        )
        run_bootstrap.assert_called_once()
        self.assertIn("LINODE_TOKEN=linode-secret", self.env_file.read_text(encoding="utf-8"))
        self.assertIn("VST_ACTIVE_REMOTE=prod", self.env_file.read_text(encoding="utf-8"))

        receipt = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["mode"], "fresh-instance")
        self.assertEqual(receipt["linode"]["instance_id"], 123)
        self.assertEqual(receipt["deploy"]["commit"], "deadbeef")

        remote_receipt = json.loads((self.remote_receipts_dir / "prod.json").read_text(encoding="utf-8"))
        self.assertEqual(remote_receipt["ssh"]["host"], "198.51.100.24")
        self.assertEqual(remote_receipt["runtime"]["public_base_url"], "http://198.51.100.24:3000")
        self.assertEqual(remote_receipt["metadata"]["last_deployed_commit"], "deadbeef")

    def test_existing_instance_can_override_public_base_url(self) -> None:
        self.env_file.write_text(
            "LINODE_TOKEN=stored-token\nBOOMERANG_API_KEY=ABCDE-FGHIJ-KLMNO-PQRST-UVWXY\n",
            encoding="utf-8",
        )
        client = FakeLinodeClient("stored-token")

        with patch.object(deploy, "LinodeApiClient", return_value=client), patch.object(
            deploy,
            "ensure_ssh_keypair",
            return_value=(
                Path("/Users/test/.ssh/virtual-space-trotting-linode"),
                Path("/Users/test/.ssh/virtual-space-trotting-linode.pub"),
                "ssh-ed25519 AAAATEST virtual-space-trotting-linode",
            ),
        ), patch.object(deploy, "wait_for_ssh_ready", return_value=None), patch.object(
            deploy,
            "build_release_bundle",
            return_value=(self.archive_path, self.metadata_path, {"commit": "cafebabe", "dirty_worktree": False}),
        ), patch.object(
            deploy, "write_remote_bootstrap_script", return_value=self.bootstrap_path
        ), patch.object(
            deploy, "copy_file_to_remote"
        ), patch.object(
            deploy, "run_remote_bootstrap", return_value=0
        ):
            rc = deploy.main(
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
                    "--public-base-url",
                    "https://imaginary.example.com",
                ]
            )

        self.assertEqual(rc, 0)
        self.assertIn(("get_instance", 456), client.calls)
        remote_receipt = json.loads((self.remote_receipts_dir / "prod.json").read_text(encoding="utf-8"))
        self.assertEqual(remote_receipt["runtime"]["public_base_url"], "https://imaginary.example.com")


if __name__ == "__main__":
    unittest.main()
