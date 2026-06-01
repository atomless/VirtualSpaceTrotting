#!/usr/bin/env python3
"""Create a Linode-ready release bundle from the exact checked-out git HEAD."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from scripts.deploy.local_env import read_env_value  # noqa: E402

BOOMERANG_API_KEY_ENV = "BOOMERANG_API_KEY"


def run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result.stdout.strip()


def extract_head_tree(repo_root: Path, destination: Path) -> None:
    archive_path = destination / "head.tar"
    subprocess.run(
        ["git", "archive", "--format=tar", "--output", str(archive_path), "HEAD"],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )
    with tarfile.open(archive_path, "r") as archive:
        archive.extractall(destination)
    archive_path.unlink()


def boomerang_build_env(repo_root: Path) -> dict[str, str]:
    key = (read_env_value(repo_root / ".env.local", BOOMERANG_API_KEY_ENV) or os.environ.get(BOOMERANG_API_KEY_ENV, "")).strip()
    if not key:
        return {}
    return {BOOMERANG_API_KEY_ENV: key}


def run_build_target(checkout_root: Path, target: str, *, env_overrides: Optional[dict[str, str]] = None) -> None:
    build_env = os.environ.copy()
    build_env.update(env_overrides or {})
    result = subprocess.run(
        ["make", "--no-print-directory", target],
        cwd=str(checkout_root),
        env=build_env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"make {target} failed"
        raise RuntimeError(f"Failed to build release bundle with make {target}: {detail}")


def write_release_archive(source_root: Path, archive_output: Path) -> None:
    archive_output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_output, "w:gz") as archive:
        for path in sorted(source_root.rglob("*")):
            relative_path = path.relative_to(source_root)
            if not relative_path.parts:
                continue
            if relative_path.parts[0] in {".git", "node_modules", "target"}:
                continue
            archive.add(path, arcname=str(relative_path), recursive=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, help="Path to the local git repository root")
    parser.add_argument("--archive-output", required=True, help="Path to output tar.gz archive")
    parser.add_argument("--metadata-output", required=True, help="Path to output JSON metadata")
    parser.add_argument(
        "--build-target",
        default="build",
        help="Make target to run inside the archived checkout before bundling",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Archive committed HEAD without running the build target",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    archive_output = Path(args.archive_output).resolve()
    metadata_output = Path(args.metadata_output).resolve()
    build_target: Optional[str] = None if args.skip_build else args.build_target

    if not repo_root.exists():
        print(f"Repository root not found: {repo_root}", file=sys.stderr)
        return 2

    try:
        commit = run_git(repo_root, "rev-parse", "HEAD")
        status_output = run_git(repo_root, "status", "--porcelain")
        dirty_worktree = bool(status_output.strip())
        env_overrides = boomerang_build_env(repo_root)

        with tempfile.TemporaryDirectory(prefix="vst-linode-bundle-") as temp_dir:
            staging_root = Path(temp_dir)
            extract_head_tree(repo_root, staging_root)
            build_ran = False
            if build_target:
                run_build_target(staging_root, build_target, env_overrides=env_overrides)
                build_ran = True
            write_release_archive(staging_root, archive_output)

        metadata_output.parent.mkdir(parents=True, exist_ok=True)
        metadata_output.write_text(
            json.dumps(
                {
                    "build_ran": build_ran,
                    "build_target": build_target or "",
                    "boomerang_api_key_present": BOOMERANG_API_KEY_ENV in env_overrides,
                    "commit": commit,
                    "dirty_worktree": dirty_worktree,
                    "repo_root": str(repo_root),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.strip() or exc.stdout.strip() or "git archive failed", file=sys.stderr)
        return 2

    if dirty_worktree:
        print("warning: local worktree is dirty; archive contains committed HEAD only", file=sys.stderr)
    print(f"created release bundle for commit {commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
