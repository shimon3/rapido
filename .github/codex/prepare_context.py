#!/usr/bin/env python3
"""Build a small, instruction-file-free Codex context from an exact Git tree."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath


MAX_FILES = 300
MAX_SOURCE_BYTES = 20_000_000
MAX_LOG_BYTES = 120_000


def git(repo: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ["git", "-c", f"safe.directory={repo.resolve().as_posix()}", "-C", str(repo), *arguments],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def prepare(repo: Path, revision: str, destination: Path, log_path: Path) -> None:
    control = Path(__file__).resolve().parent
    sys.path.insert(0, str(control))
    from validate_autofix import allowed_path

    if destination.exists() or destination.is_symlink():
        raise ValueError("destination must be a new directory")
    destination.mkdir(parents=True)

    listing = git(repo, "ls-tree", "-rz", "--full-tree", revision)
    total = 0
    file_count = 0
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, object_type, _object_id = metadata.decode("ascii").split(" ", 2)
        path = raw_path.decode("utf-8")
        if not allowed_path(path):
            continue
        if PurePosixPath(path).name.casefold() in {"agents.md", "agents.override.md"}:
            continue
        if mode != "100644" or object_type != "blob":
            raise ValueError(f"refusing non-regular source file: {path}")
        file_count += 1
        if file_count > MAX_FILES:
            raise ValueError(f"source context exceeds {MAX_FILES} files")
        contents = git(repo, "show", f"{revision}:{path}")
        total += len(contents)
        if total > MAX_SOURCE_BYTES:
            raise ValueError(f"source context exceeds {MAX_SOURCE_BYTES} bytes")
        target = destination.joinpath(*PurePosixPath(path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)

    log = log_path.read_bytes()
    if len(log) > MAX_LOG_BYTES:
        raise ValueError(f"failure log exceeds {MAX_LOG_BYTES} bytes")
    (destination / ".codex-ci-failure.log").write_bytes(log)
    git(destination, "init", "--quiet")
    git(destination, "config", "core.hooksPath", "NUL" if os.name == "nt" else "/dev/null")
    git(destination, "add", "-f", "--", ".")
    subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={destination.resolve().as_posix()}",
            "-C",
            str(destination),
            "-c",
            "user.name=Rapido isolated context",
            "-c",
            "user.email=rapido-context@users.noreply.github.com",
            "commit",
            "--quiet",
            "--no-gpg-sign",
            "-m",
            "Create isolated read-only Codex context",
        ],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare(args.repo, args.revision, args.destination, args.log)
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"refusing Codex context: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
