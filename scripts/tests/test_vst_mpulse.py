import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.deploy.vst_mpulse import CLIError, MPulseCLI


KEY = "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY"


def registry_text() -> str:
    return json.dumps(
        {
            "schema": "virtual-space-trotting.mpulse-profiles.v1",
            "profiles": {
                "dev-alma": {
                    "description": "Alma development",
                    "script_base_url": "https://alma.example.com/boomerang/",
                    "api_key": KEY,
                },
                "tenant-two": {
                    "description": "Second tenant",
                    "script_base_url": "https://two.example.com/boomerang/",
                    "api_key": "12345-67890-ABCDE-FGHIJ-KLMNO",
                },
            },
        }
    )


class MPulseCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vst-mpulse-cli-"))
        self.registry_path = self.temp_dir / "mpulse-profiles.json"
        self.registry_path.write_text(registry_text(), encoding="utf-8")
        self.state_dir = self.temp_dir / "state"
        self.state_dir.mkdir()
        (self.state_dir / "active-profile").write_text("dev-alma\n", encoding="utf-8")
        self.privileged_calls = []
        self.output = io.StringIO()
        self.cli = MPulseCLI(
            registry_path=self.registry_path,
            state_dir=self.state_dir,
            helper_path=Path("/fixed/vst-mpulse-admin"),
            run_privileged=self.run_privileged,
            run_editor=lambda _path: 0,
            probe=lambda _profile: None,
            verify_public=lambda _profile: None,
            output=self.output,
        )

    def run_privileged(self, args, input_text=None):
        self.privileged_calls.append((list(args), input_text))
        return 0

    def test_list_marks_active_profile_without_printing_keys(self) -> None:
        self.cli.list_profiles()

        output = self.output.getvalue()
        self.assertIn("* dev-alma", output)
        self.assertIn("  tenant-two", output)
        self.assertNotIn(KEY, output)

    def test_current_prints_endpoint_and_key_fingerprint(self) -> None:
        self.cli.show_current()

        output = self.output.getvalue()
        self.assertIn("dev-alma", output)
        self.assertIn("alma.example.com", output)
        self.assertIn("key fingerprint:", output)
        self.assertNotIn(KEY, output)

    def test_verify_invokes_profile_and_public_checks(self) -> None:
        checked = []
        self.cli.probe = lambda profile: checked.append(("probe", profile.name))
        self.cli.verify_public = lambda profile: checked.append(("public", profile.name))

        self.cli.verify()

        self.assertEqual(checked, [("probe", "dev-alma"), ("public", "dev-alma")])
        self.assertIn("verified", self.output.getvalue())

    def test_history_reads_sanitized_json_lines(self) -> None:
        (self.state_dir / "history.jsonl").write_text(
            json.dumps(
                {
                    "timestamp": "20260630T120000Z",
                    "actor": "james",
                    "action": "switch",
                    "old_profile": "tenant-two",
                    "new_profile": "dev-alma",
                    "outcome": "success",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        self.cli.show_history()

        output = self.output.getvalue()
        self.assertIn("james", output)
        self.assertIn("tenant-two -> dev-alma", output)

    def test_registry_validate_does_not_invoke_privileged_helper(self) -> None:
        self.cli.validate_registry_file(self.registry_path)

        self.assertEqual(self.privileged_calls, [])
        self.assertIn("valid", self.output.getvalue())

    def test_registry_edit_validates_then_pipes_canonical_json(self) -> None:
        def edit(path: Path) -> int:
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["profiles"]["third"] = {
                "description": "Third",
                "script_base_url": "https://third.example.com/boomerang/",
                "api_key": "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE",
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            return 0

        self.cli.run_editor = edit

        self.cli.edit_registry()

        self.assertEqual(self.privileged_calls[0][0], ["install-registry"])
        installed = json.loads(self.privileged_calls[0][1])
        self.assertIn("third", installed["profiles"])

    def test_registry_edit_rejects_invalid_or_unchanged_content(self) -> None:
        self.cli.edit_registry()
        self.assertEqual(self.privileged_calls, [])

        def write_invalid(path: Path) -> int:
            path.write_text("{}", encoding="utf-8")
            return 0

        self.cli.run_editor = write_invalid
        with self.assertRaisesRegex(CLIError, "missing fields"):
            self.cli.edit_registry()
        self.assertEqual(self.privileged_calls, [])

    def test_switch_accepts_only_profiles_in_registry(self) -> None:
        self.cli.switch("tenant-two")
        self.assertEqual(self.privileged_calls[-1], (["switch", "tenant-two"], None))

        with self.assertRaisesRegex(CLIError, "Unknown"):
            self.cli.switch("missing")

    def test_rollback_uses_fixed_helper_command(self) -> None:
        self.cli.rollback()

        self.assertEqual(self.privileged_calls, [(["rollback"], None)])


if __name__ == "__main__":
    unittest.main()
