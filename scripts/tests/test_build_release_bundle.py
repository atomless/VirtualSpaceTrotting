import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "deploy" / "build_release_bundle.py"


def run_bundle(
    repo_root: Path,
    archive_output: Path,
    metadata_output: Path,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--repo-root",
            str(repo_root),
            "--archive-output",
            str(archive_output),
            "--metadata-output",
            str(metadata_output),
            *extra_args,
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


class BuildReleaseBundleTests(unittest.TestCase):
    def create_git_repo(self) -> Path:
        temp_dir = Path(tempfile.mkdtemp(prefix="vst-bundle-"))
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True)
        (temp_dir / "README.md").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=temp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=temp_dir, check=True, capture_output=True)
        return temp_dir

    def test_builds_archive_from_exact_head_and_writes_metadata(self) -> None:
        repo_root = self.create_git_repo()
        archive_output = repo_root / "release.tar.gz"
        metadata_output = repo_root / "release.json"

        result = run_bundle(repo_root, archive_output, metadata_output, "--skip-build")

        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        metadata = json.loads(metadata_output.read_text(encoding="utf-8"))
        expected_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(metadata["commit"], expected_head)
        self.assertFalse(metadata["dirty_worktree"])
        self.assertFalse(metadata["build_ran"])

        with tarfile.open(archive_output, "r:gz") as archive:
            names = archive.getnames()
        self.assertIn("README.md", names)
        self.assertNotIn(".git", names)

    def test_reports_dirty_worktree_in_metadata(self) -> None:
        repo_root = self.create_git_repo()
        archive_output = repo_root / "release.tar.gz"
        metadata_output = repo_root / "release.json"
        (repo_root / "README.md").write_text("changed\n", encoding="utf-8")

        result = run_bundle(repo_root, archive_output, metadata_output, "--skip-build")

        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        metadata = json.loads(metadata_output.read_text(encoding="utf-8"))
        self.assertTrue(metadata["dirty_worktree"])

    def test_optional_build_target_outputs_are_included_in_archive(self) -> None:
        repo_root = self.create_git_repo()
        (repo_root / "Makefile").write_text(
            "build:\n\t@mkdir -p dist/site\n\t@printf '<h1>Site</h1>\\n' > dist/site/index.html\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "Makefile"], cwd=repo_root, check=True)
        subprocess.run(["git", "commit", "-m", "add build"], cwd=repo_root, check=True, capture_output=True)
        archive_output = repo_root / "release.tar.gz"
        metadata_output = repo_root / "release.json"

        result = run_bundle(repo_root, archive_output, metadata_output)

        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        metadata = json.loads(metadata_output.read_text(encoding="utf-8"))
        self.assertTrue(metadata["build_ran"])
        with tarfile.open(archive_output, "r:gz") as archive:
            self.assertIn("dist/site/index.html", archive.getnames())

    def test_build_target_receives_boomerang_api_key_from_env_file_without_archiving_env(self) -> None:
        repo_root = self.create_git_repo()
        (repo_root / "Makefile").write_text(
            "build:\n"
            "\t@mkdir -p dist/site\n"
            "\t@printf '%s\\n' \"$$BOOMERANG_API_KEY\" > dist/site/boomerang-key.txt\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "Makefile"], cwd=repo_root, check=True)
        subprocess.run(["git", "commit", "-m", "add build"], cwd=repo_root, check=True, capture_output=True)
        (repo_root / ".env.local").write_text(
            "LINODE_TOKEN=do-not-expose\nBOOMERANG_API_KEY=ABCDE-FGHIJ-KLMNO-PQRST-UVWXY\n",
            encoding="utf-8",
        )
        archive_output = repo_root / "release.tar.gz"
        metadata_output = repo_root / "release.json"

        result = run_bundle(repo_root, archive_output, metadata_output)

        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        metadata = json.loads(metadata_output.read_text(encoding="utf-8"))
        self.assertIs(metadata["boomerang_api_key_present"], True)
        with tarfile.open(archive_output, "r:gz") as archive:
            names = archive.getnames()
            self.assertNotIn(".env.local", names)
            key_file = archive.extractfile("dist/site/boomerang-key.txt")
            assert key_file is not None
            self.assertEqual(key_file.read().decode("utf-8").strip(), "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY")


if __name__ == "__main__":
    unittest.main()
