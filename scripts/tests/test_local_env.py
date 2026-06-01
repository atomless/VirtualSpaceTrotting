import tempfile
import unittest
from pathlib import Path

from scripts.deploy import local_env


class LocalEnvTests(unittest.TestCase):
    def test_parse_env_text_ignores_comments_and_strips_wrapping_quotes(self) -> None:
        values = local_env.parse_env_text(
            """
            # comment
            LINODE_TOKEN='secret'
            VST_ACTIVE_REMOTE="prod"
            EMPTY=
            """
        )

        self.assertEqual(values["LINODE_TOKEN"], "secret")
        self.assertEqual(values["VST_ACTIVE_REMOTE"], "prod")
        self.assertEqual(values["EMPTY"], "")

    def test_upsert_env_value_preserves_other_keys_and_locks_permissions(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="vst-env-"))
        env_file = temp_dir / ".env.local"
        env_file.write_text("LINODE_TOKEN=old\nOTHER=value\n", encoding="utf-8")

        local_env.upsert_env_value(env_file, "LINODE_TOKEN", "new")
        local_env.upsert_env_value(env_file, "VST_ACTIVE_REMOTE", "prod")

        self.assertEqual(
            env_file.read_text(encoding="utf-8"),
            "LINODE_TOKEN=new\nOTHER=value\nVST_ACTIVE_REMOTE=prod\n",
        )
        self.assertEqual(env_file.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
