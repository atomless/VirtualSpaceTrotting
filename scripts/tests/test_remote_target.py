import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.deploy import remote_target


class RemoteTargetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vst-remote-"))
        self.env_file = self.temp_dir / ".env.local"
        self.receipts_dir = self.temp_dir / ".vst" / "remotes"
        self.receipts_dir.mkdir(parents=True)
        self.receipt_path = self.receipts_dir / "prod.json"
        remote_target.write_json(
            self.receipt_path,
            {
                "schema": "virtual_space_trotting.remote_target.v1",
                "identity": {
                    "name": "prod",
                    "backend_kind": "ssh_systemd",
                    "provider_kind": "linode",
                },
                "ssh": {
                    "host": "198.51.100.24",
                    "port": 22,
                    "user": "vst",
                    "private_key_path": "/Users/test/.ssh/virtual-space-trotting-linode",
                },
                "runtime": {
                    "app_dir": "/opt/virtual-space-trotting",
                    "service_name": "virtual-space-trotting",
                    "public_base_url": "https://imaginary.example.com",
                },
                "deploy": {
                    "health_path": "/health",
                },
                "metadata": {
                    "last_deployed_commit": "abc123",
                    "last_deployed_at_utc": "2026-06-01T10:00:00Z",
                },
                "provider": {"linode": {"instance_id": 123456}},
            },
        )

    def test_default_remote_receipts_dir_uses_durable_project_state(self) -> None:
        self.assertEqual(remote_target.DEFAULT_REMOTE_RECEIPTS_DIR, remote_target.REPO_ROOT / ".vst" / "remotes")
        self.assertNotIn("/.spin/", str(remote_target.DEFAULT_REMOTE_RECEIPTS_DIR))

    def test_script_can_be_invoked_directly_from_repo_root(self) -> None:
        result = subprocess.run(
            [sys.executable, str(remote_target.REPO_ROOT / "scripts" / "deploy" / "remote_target.py"), "--help"],
            cwd=remote_target.REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage:", result.stdout)

    def test_use_command_persists_active_remote_in_env_file(self) -> None:
        rc = remote_target.main(
            [
                "--env-file",
                str(self.env_file),
                "--receipts-dir",
                str(self.receipts_dir),
                "use",
                "--name",
                "prod",
            ]
        )

        self.assertEqual(rc, 0)
        self.assertIn("VST_ACTIVE_REMOTE=prod", self.env_file.read_text(encoding="utf-8"))

    def test_status_uses_active_remote_from_env_file(self) -> None:
        self.env_file.write_text("VST_ACTIVE_REMOTE=prod\n", encoding="utf-8")

        with patch.object(subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
            rc = remote_target.main(
                [
                    "--env-file",
                    str(self.env_file),
                    "--receipts-dir",
                    str(self.receipts_dir),
                    "status",
                ]
            )

        self.assertEqual(rc, 0)
        self.assertEqual(
            run.call_args.args[0],
            [
                "ssh",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-p",
                "22",
                "-i",
                "/Users/test/.ssh/virtual-space-trotting-linode",
                "vst@198.51.100.24",
                "sudo systemctl status virtual-space-trotting --no-pager",
            ],
        )

    def test_start_stop_and_logs_use_systemd_service_name(self) -> None:
        cases = {
            "start": "sudo systemctl start virtual-space-trotting",
            "stop": "sudo systemctl stop virtual-space-trotting",
            "logs": "sudo journalctl -u virtual-space-trotting -n 200 --no-pager",
        }
        for command_name, expected in cases.items():
            with self.subTest(command_name=command_name):
                with patch.object(subprocess, "run") as run:
                    run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
                    rc = remote_target.main(
                        [
                            "--env-file",
                            str(self.env_file),
                            "--receipts-dir",
                            str(self.receipts_dir),
                            command_name,
                            "--name",
                            "prod",
                        ]
                    )
                self.assertEqual(rc, 0)
                self.assertEqual(run.call_args.args[0][-1], expected)

    def test_open_site_uses_public_base_url(self) -> None:
        with patch.object(remote_target.shutil, "which", side_effect=["/usr/bin/open", None]), patch.object(
            subprocess, "run"
        ) as run:
            run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
            rc = remote_target.main(
                [
                    "--env-file",
                    str(self.env_file),
                    "--receipts-dir",
                    str(self.receipts_dir),
                    "open-site",
                    "--name",
                    "prod",
                ]
            )

        self.assertEqual(rc, 0)
        self.assertEqual(run.call_args.args[0], ["open", "https://imaginary.example.com"])

    def test_write_linode_receipt_uses_project_defaults(self) -> None:
        rc = remote_target.main(
            [
                "--env-file",
                str(self.env_file),
                "--receipts-dir",
                str(self.receipts_dir),
                "write-linode-receipt",
                "--name",
                "new-prod",
                "--host",
                "198.51.100.30",
                "--private-key-path",
                "/Users/test/.ssh/virtual-space-trotting-linode",
                "--public-base-url",
                "https://new.example.com",
                "--instance-id",
                "789",
            ]
        )

        self.assertEqual(rc, 0)
        receipt = json.loads((self.receipts_dir / "new-prod.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["schema"], "virtual_space_trotting.remote_target.v1")
        self.assertEqual(receipt["ssh"]["user"], "vst")
        self.assertEqual(receipt["runtime"]["app_dir"], "/opt/virtual-space-trotting")
        self.assertEqual(receipt["runtime"]["service_name"], "virtual-space-trotting")
        self.assertEqual(receipt["deploy"]["health_path"], "/health")

    def test_update_uploads_bundle_runs_install_and_refreshes_metadata(self) -> None:
        self.env_file.write_text(
            "VST_ACTIVE_REMOTE=prod\nBOOMERANG_API_KEY=ABCDE-FGHIJ-KLMNO-PQRST-UVWXY\n",
            encoding="utf-8",
        )
        bundle_dir = self.temp_dir / "bundle"
        bundle_dir.mkdir()
        archive_path = bundle_dir / "release.tar.gz"
        archive_path.write_text("bundle\n", encoding="utf-8")
        metadata_path = bundle_dir / "release.json"
        metadata_path.write_text(json.dumps({"commit": "deadbeef", "dirty_worktree": False}) + "\n", encoding="utf-8")
        update_script_path = bundle_dir / "remote-update.sh"
        update_script_path.write_text("#!/bin/sh\n", encoding="utf-8")

        with patch.object(
            remote_target,
            "build_release_bundle",
            return_value=(archive_path, metadata_path, {"commit": "deadbeef"}),
        ), patch.object(remote_target, "write_remote_update_script", return_value=update_script_path), patch.object(
            remote_target, "copy_file_to_remote"
        ) as copy_file, patch.object(
            remote_target, "run_remote_update_install", return_value=0
        ) as run_install, patch.object(
            remote_target, "run_remote_health_check", return_value=0
        ) as run_health:
            rc = remote_target.main(
                [
                    "--env-file",
                    str(self.env_file),
                    "--receipts-dir",
                    str(self.receipts_dir),
                    "update",
                ]
            )

        self.assertEqual(rc, 0)
        self.assertEqual(
            [call.args[2] for call in copy_file.call_args_list],
            [
                "/tmp/vst-remote-update-release.tar.gz",
                "/tmp/vst-remote-update-release.json",
                "/tmp/vst-remote-update.sh",
            ],
        )
        run_install.assert_called_once()
        run_health.assert_called_once()
        receipt = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["metadata"]["last_deployed_commit"], "deadbeef")
        self.assertTrue(receipt["metadata"]["last_deployed_at_utc"].endswith("Z"))

    def test_update_can_build_release_without_boomerang_api_key(self) -> None:
        self.env_file.write_text("VST_ACTIVE_REMOTE=prod\n", encoding="utf-8")
        bundle_dir = self.temp_dir / "bundle-no-boomerang"
        bundle_dir.mkdir()
        archive_path = bundle_dir / "release.tar.gz"
        archive_path.write_text("bundle\n", encoding="utf-8")
        metadata_path = bundle_dir / "release.json"
        metadata_path.write_text(json.dumps({"commit": "deadbeef", "dirty_worktree": False}) + "\n", encoding="utf-8")
        update_script_path = bundle_dir / "remote-update.sh"
        update_script_path.write_text("#!/bin/sh\n", encoding="utf-8")

        with patch.object(
            remote_target,
            "build_release_bundle",
            return_value=(archive_path, metadata_path, {"commit": "deadbeef"}),
        ) as build_release, patch.object(
            remote_target, "write_remote_update_script", return_value=update_script_path
        ), patch.object(
            remote_target, "copy_file_to_remote"
        ), patch.object(
            remote_target, "run_remote_update_install", return_value=0
        ), patch.object(
            remote_target, "run_remote_health_check", return_value=0
        ):
            rc = remote_target.main(
                [
                    "--env-file",
                    str(self.env_file),
                    "--receipts-dir",
                    str(self.receipts_dir),
                    "update",
                ]
            )

        self.assertEqual(rc, 0)
        self.assertIsNone(build_release.call_args.kwargs["boomerang_api_key"])

    def test_remote_update_script_can_swap_opt_app_directory(self) -> None:
        script_path = remote_target.write_remote_update_script(self.temp_dir)
        script = script_path.read_text(encoding="utf-8")

        self.assertIn("sudo mkdir -p \"${NEXT_APP_DIR}\"", script)
        self.assertIn("sudo mv \"${REMOTE_APP_DIR}\" \"${PREV_APP_DIR}\"", script)
        self.assertIn("sudo mv \"${NEXT_APP_DIR}\" \"${REMOTE_APP_DIR}\"", script)
        self.assertIn("sudo chown -R \"$(id -u):$(id -g)\" \"${REMOTE_APP_DIR}\"", script)


if __name__ == "__main__":
    unittest.main()
