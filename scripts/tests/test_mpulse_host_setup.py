import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.deploy.mpulse_host_setup import (
    OPERATOR_GROUP,
    REMOTE_ARCHIVE_PATH,
    build_setup_archive,
    parse_args,
    render_caddyfile,
    render_install_script,
    run_remote_install,
)


KEY = "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY"


def registry_text() -> str:
    return json.dumps(
        {
            "schema": "virtual-space-trotting.mpulse-profiles.v1",
            "profiles": {
                "dev-alma": {
                    "description": "Development Alma tenant",
                    "script_base_url": "https://collector.example.com/boomerang/",
                    "api_key": KEY,
                }
            },
        }
    )


def receipt() -> dict:
    return {
        "identity": {"name": "prod"},
        "ssh": {
            "host": "172.239.117.12",
            "port": 22,
            "user": "vst",
            "private_key_path": "/tmp/id_ed25519",
        },
        "runtime": {
            "public_base_url": "https://172.239.117.12.sslip.io",
            "service_name": "virtual-space-trotting",
        },
    }


class MPulseHostSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vst-mpulse-host-"))
        self.registry_path = self.temp_dir / "profiles.json"
        self.registry_path.write_text(registry_text(), encoding="utf-8")

    def test_install_requires_explicit_registry_and_initial_profile(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["install"])
        with self.assertRaises(SystemExit):
            parse_args(["install", "--registry-file", str(self.registry_path)])

    def test_caddyfile_preserves_hardening_and_routes_runtime_config_first(self) -> None:
        caddyfile = render_caddyfile(receipt())

        self.assertIn("http://172.239.117.12", caddyfile)
        self.assertIn("redir https://172.239.117.12.sslip.io{uri} permanent", caddyfile)
        self.assertIn("encode zstd gzip", caddyfile)
        self.assertIn('Cache-Control "no-cache, max-age=0"', caddyfile)
        self.assertIn('X-Content-Type-Options "nosniff"', caddyfile)
        self.assertIn('Referrer-Policy "strict-origin-when-cross-origin"', caddyfile)
        self.assertIn('X-Frame-Options "DENY"', caddyfile)
        self.assertIn('Strict-Transport-Security "max-age=300"', caddyfile)
        self.assertIn('header Cache-Control "no-store"', caddyfile)
        self.assertIn('header Content-Type "application/javascript; charset=utf-8"', caddyfile)
        self.assertLess(caddyfile.index("handle /mpulse-config.js"), caddyfile.index("handle {"))
        self.assertIn("reverse_proxy 127.0.0.1:3000", caddyfile)

    def test_install_script_uses_restricted_paths_modes_and_operator_group(self) -> None:
        script = render_install_script(operator_user="vst", initial_profile="dev-alma")

        self.assertIn(f"groupadd --system {OPERATOR_GROUP}", script)
        self.assertIn(f"usermod -a -G {OPERATOR_GROUP} vst", script)
        self.assertNotIn("usermod -aG sudo", script)
        self.assertIn("install -o root -g root -m 0755", script)
        self.assertIn("/usr/local/bin/vst-mpulse", script)
        self.assertIn("/usr/local/lib/virtual-space-trotting/vst-mpulse-admin", script)
        self.assertIn("/usr/local/lib/virtual-space-trotting/mpulse_profiles.py", script)
        self.assertIn("install -o root -g root -m 0440", script)
        self.assertIn("visudo -cf", script)
        self.assertIn("systemd-tmpfiles --create", script)

    def test_install_script_refuses_registry_replacement_but_allows_idempotent_upgrade(self) -> None:
        script = render_install_script(operator_user="vst", initial_profile="dev-alma")

        self.assertIn('cmp -s "${PAYLOAD_DIR}/mpulse-profiles.json" "${REGISTRY_PATH}"', script)
        self.assertIn("Existing mPulse registry differs", script)
        self.assertNotIn("cp \"${PAYLOAD_DIR}/mpulse-profiles.json\" \"${REGISTRY_PATH}\"", script)

    def test_install_script_validates_caddy_before_install_and_restores_on_failure(self) -> None:
        script = render_install_script(operator_user="vst", initial_profile="dev-alma")

        validation = script.index(
            'caddy validate --config "${PAYLOAD_DIR}/Caddyfile" --adapter caddyfile'
        )
        installation = script.index('install -o root -g root -m 0644 "${PAYLOAD_DIR}/Caddyfile"')
        self.assertLess(validation, installation)
        self.assertIn('caddy validate --config "${CADDYFILE}" --adapter caddyfile', script)
        self.assertIn("systemctl reload caddy", script)
        self.assertIn('restore_caddy "${CADDY_BACKUP}"', script)
        self.assertIn("vst-mpulse-admin switch", script)

    def test_setup_archive_contains_canonical_registry_without_leaking_key_to_install_script(self) -> None:
        archive = build_setup_archive(
            work_dir=self.temp_dir,
            registry_file=self.registry_path,
            initial_profile="dev-alma",
            remote_receipt=receipt(),
        )

        self.assertEqual(archive.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(KEY, render_install_script(operator_user="vst", initial_profile="dev-alma"))
        self.assertTrue(archive.exists())

    @patch("scripts.deploy.mpulse_host_setup.subprocess.run")
    def test_remote_command_contains_no_registry_secret(self, run) -> None:
        run.return_value.returncode = 0

        result = run_remote_install(receipt(), self.temp_dir / "setup.tar.gz")

        self.assertEqual(result, 0)
        commands = " ".join(" ".join(call.args[0]) for call in run.call_args_list)
        self.assertIn(REMOTE_ARCHIVE_PATH, commands)
        self.assertNotIn(KEY, commands)
        self.assertIn("chmod 600", commands)


if __name__ == "__main__":
    unittest.main()
