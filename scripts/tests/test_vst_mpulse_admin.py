import fcntl
import json
import tempfile
import unittest
from pathlib import Path

from scripts.deploy.vst_mpulse_admin import AdminError, MPulseAdmin


KEY = "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY"


def registry_text(*names: str) -> str:
    profiles = {
        name: {
            "description": f"Profile {name}",
            "script_base_url": f"https://{name}.example.com/boomerang/",
            "api_key": KEY,
        }
        for name in names
    }
    return json.dumps({"schema": "virtual-space-trotting.mpulse-profiles.v1", "profiles": profiles})


class MPulseAdminTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vst-mpulse-admin-"))
        self.registry_path = self.temp_dir / "etc" / "mpulse-profiles.json"
        self.state_dir = self.temp_dir / "state"
        self.public_dir = self.temp_dir / "public"
        self.lock_path = self.temp_dir / "run" / "vst-mpulse.lock"
        self.probes = []
        self.verifications = []
        self.audits = []
        self.clock_value = 0
        self.admin = MPulseAdmin(
            registry_path=self.registry_path,
            state_dir=self.state_dir,
            public_dir=self.public_dir,
            lock_path=self.lock_path,
            probe=lambda profile: self.probes.append(profile.name),
            verify=lambda profile: self.verifications.append(profile.name),
            audit=self.audits.append,
            clock=self.clock,
            apply_ownership=lambda _path, _kind: None,
            backup_limit=2,
        )

    def clock(self) -> str:
        self.clock_value += 1
        return f"20260630T12000{self.clock_value}Z"

    def install(self, *names: str) -> None:
        self.admin.install_registry(registry_text(*names), actor="james")

    def test_installs_canonical_registry_with_restricted_mode(self) -> None:
        self.install("dev-alma")

        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        self.assertEqual(list(payload["profiles"]), ["dev-alma"])
        self.assertEqual(self.registry_path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.audits[-1]["action"], "install-registry")
        self.assertNotIn(KEY, json.dumps(self.audits))

    def test_registry_install_backs_up_and_rotates_previous_versions(self) -> None:
        self.install("one")
        self.install("one", "two")
        self.install("one", "two", "three")
        self.install("one", "two", "three", "four")

        backups = sorted((self.state_dir / "registry-backups").glob("*.json"))
        self.assertEqual(len(backups), 2)

    def test_registry_install_rejects_removing_active_profile(self) -> None:
        self.install("one", "two")
        self.admin.switch("one", actor="james")

        with self.assertRaisesRegex(AdminError, "active profile"):
            self.admin.install_registry(registry_text("two"), actor="james")

        self.assertIn("one", self.registry_path.read_text(encoding="utf-8"))

    def test_switch_probes_writes_and_verifies_profile(self) -> None:
        self.install("dev-alma")

        self.admin.switch("dev-alma", actor="james")

        self.assertEqual(self.probes, ["dev-alma"])
        self.assertEqual(self.verifications, ["dev-alma"])
        self.assertEqual((self.state_dir / "active-profile").read_text(encoding="utf-8"), "dev-alma\n")
        browser_config = (self.public_dir / "mpulse-config.js").read_text(encoding="utf-8")
        self.assertIn('"name":"dev-alma"', browser_config)
        self.assertEqual((self.public_dir / "mpulse-config.js").stat().st_mode & 0o777, 0o640)
        history = (self.state_dir / "history.jsonl").read_text(encoding="utf-8")
        self.assertIn('"action": "switch"', history)
        self.assertNotIn(KEY, history)

    def test_probe_failure_leaves_active_files_unchanged(self) -> None:
        self.install("one", "two")
        self.admin.switch("one", actor="james")
        original_active = (self.state_dir / "active-profile").read_bytes()
        original_config = (self.public_dir / "mpulse-config.js").read_bytes()
        self.admin.probe = lambda _profile: (_ for _ in ()).throw(AdminError("probe failed"))

        with self.assertRaisesRegex(AdminError, "probe failed"):
            self.admin.switch("two", actor="james")

        self.assertEqual((self.state_dir / "active-profile").read_bytes(), original_active)
        self.assertEqual((self.public_dir / "mpulse-config.js").read_bytes(), original_config)

    def test_verification_failure_restores_previous_profile(self) -> None:
        self.install("one", "two")
        self.admin.switch("one", actor="james")
        self.admin.verify = lambda profile: (
            (_ for _ in ()).throw(AdminError("public verification failed"))
            if profile.name == "two"
            else None
        )

        with self.assertRaisesRegex(AdminError, "public verification failed"):
            self.admin.switch("two", actor="james")

        self.assertEqual((self.state_dir / "active-profile").read_text(encoding="utf-8"), "one\n")
        self.assertIn('"name":"one"', (self.public_dir / "mpulse-config.js").read_text(encoding="utf-8"))
        self.assertEqual(self.audits[-1]["outcome"], "rolled-back")

    def test_rollback_reactivates_previous_profile(self) -> None:
        self.install("one", "two")
        self.admin.switch("one", actor="james")
        self.admin.switch("two", actor="james")

        self.admin.rollback(actor="james")

        self.assertEqual((self.state_dir / "active-profile").read_text(encoding="utf-8"), "one\n")
        self.assertEqual(self.audits[-1]["action"], "rollback")

    def test_rollback_without_previous_profile_is_rejected(self) -> None:
        self.install("one")
        self.admin.switch("one", actor="james")

        with self.assertRaisesRegex(AdminError, "previous profile"):
            self.admin.rollback(actor="james")

    def test_mutation_refuses_to_wait_on_existing_lock(self) -> None:
        self.lock_path.parent.mkdir(parents=True)
        with self.lock_path.open("w", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(AdminError, "in progress"):
                self.install("one")

    def test_idempotent_switch_verifies_without_rewriting_history(self) -> None:
        self.install("one")
        self.admin.switch("one", actor="james")
        history_before = (self.state_dir / "history.jsonl").read_text(encoding="utf-8")

        self.admin.switch("one", actor="james")

        self.assertEqual((self.state_dir / "history.jsonl").read_text(encoding="utf-8"), history_before)
        self.assertEqual(self.verifications, ["one", "one"])


if __name__ == "__main__":
    unittest.main()
