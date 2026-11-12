"""Read-only verification of the official pydantic-core CPython 3.13 Windows x64 wheel.

Checks archive identity and inventories the packaged native module. This does
NOT attest source-to-binary reproducibility, Rust crate licences or trusted
publisher provenance; independent review remains mandatory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

WHEEL = "pydantic_core-2.50.2-cp313-cp313-win_amd64.whl"
PYPI_SHA256 = "e5c801bdf3cc92274b8fc2c7023c8751e5ae81260c009ac558ff55ce712a2d45"
MODULE = "pydantic_core/_pydantic_core.cp313-win_amd64.pyd"
MAX_ARCHIVE_BYTES = 12 * 1024 * 1024
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 40 * 1024 * 1024
MAX_ENTRIES = 500


def inspect_wheel(path: Path, *, expected_sha256: str = PYPI_SHA256) -> dict:
    path = Path(path)
    if path.name != WHEEL or path.is_symlink() or not path.is_file():
        raise ValueError("Unexpected or non-regular wheel")
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Wheel archive exceeds size limit")
    with path.open("rb") as f:
        archive_sha = hashlib.file_digest(f, "sha256").hexdigest()
    if archive_sha != expected_sha256:
        raise ValueError("Wheel SHA-256 does not match PyPI")
    binaries = []
    names = set()
    total = 0
    with zipfile.ZipFile(path) as z:
        entries = z.infolist()
        if len(entries) > MAX_ENTRIES:
            raise ValueError("Too many archive members")
        for entry in entries:
            name = entry.filename
            rel = PurePosixPath(name)
            if not name or "\\" in name or rel.is_absolute() or ".." in rel.parts or name in names:
                raise ValueError("Unsafe or duplicate archive member")
            names.add(name)
            if entry.create_system == 3 and stat.S_IFMT(entry.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError("Symlink member refused")
            if entry.file_size > MAX_FILE_BYTES:
                raise ValueError("Member too large")
            total += entry.file_size
            if total > MAX_TOTAL_BYTES:
                raise ValueError("Archive expansion limit exceeded")
            if name == MODULE:
                with z.open(entry) as f:
                    # Hash the native binary as raw bytes, never LF-normalize.
                    data = f.read(MAX_FILE_BYTES + 1)
                if len(data) != entry.file_size:
                    raise ValueError("Unexpected native module size")
                binaries.append({"path": name, "sha256": hashlib.sha256(data).hexdigest()})
    if len(binaries) != 1:
        raise ValueError("Expected Windows x64 native extension missing")
    return {"package": "pydantic-core", "version": "2.50.2", "wheel_sha256": archive_sha,
            "status": "REVIEW_CANDIDATE_ONLY", "has_pypi_provenance_attestation": False,
            "native_modules": binaries,
            "rust_crate_license_review": "REQUIRED_BEFORE_APPROVAL"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect_wheel(args.wheel), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
