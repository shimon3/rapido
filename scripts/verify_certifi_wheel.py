"""Offline audit of the exact certifi 2026.10.23 PyPI wheel.

Candidate evidence only; this does not approve new hashes, update source
notice policies, install dependencies, access the network or certify licences.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

VERSION = "2026.10.23"
EXPECTED_WHEEL = f"certifi-{VERSION}-py3-none-any.whl"
PYPI_SHA256 = "e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1"
SOURCE_MEMBERS = frozenset({
    "certifi/__init__.py", "certifi/__main__.py", "certifi/cacert.pem",
    "certifi/core.py", "certifi/py.typed",
})
MAX_MEMBER = 2 * 1024 * 1024
MAX_TOTAL = 12 * 1024 * 1024
MAX_ENTRIES = 200


def verify_wheel(path: Path, expected_sha256: str = PYPI_SHA256) -> dict:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Refusing missing, symlinked or non-regular archive")
    if path.name != EXPECTED_WHEEL:
        raise ValueError("Unexpected wheel file name")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != expected_sha256:
        raise ValueError("Archive SHA-256 differs from official PyPI digest")
    result = []
    total = 0
    names = set()
    with zipfile.ZipFile(path) as wheel:
        infos = wheel.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ValueError("Excessive archive entries")
        for info in infos:
            name = info.filename
            rel = PurePosixPath(name)
            if (not name or "\\" in name or rel.is_absolute() or
                    ".." in rel.parts or name in names):
                raise ValueError("Invalid or duplicate archive path")
            names.add(name)
            if (info.create_system == 3 and
                    stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK):
                raise ValueError("Symlinked archive member")
            if info.file_size > MAX_MEMBER:
                raise ValueError("Oversized archive member")
            total += info.file_size
            if total > MAX_TOTAL:
                raise ValueError("Excessive uncompressed archive size")
            if name in SOURCE_MEMBERS:
                with wheel.open(info) as stream:
                    data = stream.read(MAX_MEMBER + 1)
                if len(data) != info.file_size:
                    raise ValueError("Unexpected extracted member size")
                digest = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
                result.append({"path": name, "sha256_lf": digest})
    if {item["path"] for item in result} != SOURCE_MEMBERS:
        raise ValueError("Missing package source members")
    return {"package": "certifi", "version": VERSION,
            "archive_sha256": expected_sha256, "status": "REVIEW_CANDIDATE_ONLY",
            "source_files": sorted(result, key=lambda x: x["path"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path,
                        help="Exact offline wheel downloaded from PyPI")
    args = parser.parse_args()
    print(json.dumps(verify_wheel(args.wheel), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
