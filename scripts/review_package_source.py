"""Read-only reviewer inventory for source-notice-sensitive Python packages.

This tool does NOT approve any new hash, modify SOURCE_NOTICES, or establish
legal compliance. Compare its reported digests independently against official
upstream artifacts before updating pinned versions.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path
import re

SUPPORTED = {
    "certifi": re.compile(r"^certifi/(?:[^/]+)$"),
    "pydantic-core": re.compile(r"^pydantic_core/(?:[^/]+)$"),
}
MAX_FILE_SIZE = 20 * 1024 * 1024


def inventory(package: str) -> dict:
    if package not in SUPPORTED:
        raise ValueError("Unsupported package")
    distribution = metadata.distribution(package)
    root = Path(distribution.locate_file("")).resolve(strict=True)
    items = []
    for record in distribution.files or ():
        relative = record.as_posix()
        if not SUPPORTED[package].fullmatch(relative):
            continue
        path = Path(distribution.locate_file(record))
        # Reject leaf symlinks and resolved paths outside the distribution.
        if path.is_symlink():
            raise ValueError("Symbolic-link file refused")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError("Outside package or not a regular file")
        if resolved.stat().st_size > MAX_FILE_SIZE:
            raise ValueError("Oversized package member")
        data = resolved.read_bytes()
        is_binary = resolved.suffix.lower() in {".pyd", ".dll", ".so", ".dylib"}
        digest = hashlib.sha256(data if is_binary else data.replace(b"\r\n", b"\n")).hexdigest()
        items.append({"path": relative, "sha256": digest, "mode": "binary" if is_binary else "lf-normalized"})
    if not items:
        raise ValueError("No package members discovered")
    return {"package": package, "version": distribution.version,
            "status": "UNREVIEWED_CANDIDATE_ONLY",
            "files": sorted(items, key=lambda item: item["path"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", choices=sorted(SUPPORTED))
    args = parser.parse_args()
    print(json.dumps(inventory(args.package), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
