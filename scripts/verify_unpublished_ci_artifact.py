"""Verify a downloaded *unpublished* Rapido Windows CI artifact without running code.

This is an unsigned/private-beta integrity check, NOT an Authenticode
verification, a licence review or a public-release authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

HEX = re.compile(r"^[a-fA-F0-9]{64}$")
SHA_LINE = re.compile(r"^([a-fA-F0-9]{64})  ([A-Za-z0-9_.()-]+)$")
SETUP = re.compile(r"^Rapido-Setup-[0-9][A-Za-z0-9._-]*\.exe$")
PORTABLE = re.compile(r"^Rapido-[0-9][A-Za-z0-9._-]*-portable\.zip$")
REQUIRED = {"Rapido.exe", "RapidoNativeHost.exe"}
MAX_MEMBERS = 3000
MAX_MEMBER_BYTES = 500 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(directory: Path, run_id: int, tested_source_commit: str) -> dict:
    directory = Path(directory).resolve(strict=True)
    if not directory.is_dir() or run_id <= 0:
        raise ValueError("Expected directory and positive GitHub run ID")
    if not re.fullmatch(r"[a-fA-F0-9]{40}", tested_source_commit):
        raise ValueError("Expected full 40-character tested commit")
    expected_files = {
        "SHA256SUMS.txt", "ci-artifact-provenance.json",
        "signing-plan.json", "signing-rehearsal.json"
    }
    actual = {p.name for p in directory.iterdir()}
    if any(p.is_symlink() or not p.is_file() for p in directory.iterdir()):
        raise ValueError("Artifact contains non-regular files or symlinks")
    if len(actual) != len(list(directory.iterdir())):
        raise ValueError("Duplicate or ambiguous artifact names")
    candidates = actual - expected_files
    installers = [x for x in candidates if SETUP.fullmatch(x)]
    archives = [x for x in candidates if PORTABLE.fullmatch(x)]
    if len(installers) != 1 or len(archives) != 1 or candidates != set(installers + archives):
        raise ValueError("Unexpected missing or extra distributable files")
    if not expected_files.issubset(actual):
        raise ValueError("Missing CI provenance or hash evidence")
    provenance = json.loads((directory / "ci-artifact-provenance.json").read_text(encoding="utf-8-sig"))
    if provenance.get("official_release") is not False or provenance.get("production_signed") is not False:
        raise ValueError("Not an unpublished unsigned test artifact")
    if provenance.get("workflow_run_id") not in (str(run_id), run_id):
        raise ValueError("Wrong workflow run provenance")
    if str(provenance.get("head_commit", "")).lower() != tested_source_commit.lower():
        raise ValueError("Wrong tested checkout commit")
    sums = {}
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines():
        match = SHA_LINE.fullmatch(line)
        if not match:
            raise ValueError("Unexpected SHA256SUMS format")
        digest, name = match.groups()
        if name in sums:
            raise ValueError("Duplicate SHA256SUMS entry")
        sums[name] = digest.lower()
    if set(sums) != set(installers + archives) | REQUIRED:
        raise ValueError("Unexpected or missing SHA256SUMS entry")

    for name in installers + archives:
        if sha256_file(directory / name) != sums[name]:
            raise ValueError("Distributable SHA-256 mismatch: " + name)

    found = {}
    total_size = 0
    seen = set()
    with zipfile.ZipFile(directory / archives[0]) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("Portable ZIP has too many members")
        for info in infos:
            name = info.filename
            rel = PurePosixPath(name)
            if not name or "\\" in name or rel.is_absolute() or ".." in rel.parts or name in seen:
                raise ValueError("Unsafe or duplicate portable ZIP member")
            seen.add(name)
            if info.create_system == 3 and stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError("Portable ZIP contains symlink")
            if info.file_size > MAX_MEMBER_BYTES:
                raise ValueError("Oversized portable ZIP member")
            total_size += info.file_size
            if total_size > MAX_TOTAL_BYTES:
                raise ValueError("Excessive portable ZIP expansion")
            if name in ("Rapido/Rapido.exe", "Rapido/RapidoNativeHost.exe"):
                with archive.open(info) as stream:
                    digest = hashlib.sha256()
                    while data := stream.read(1024 * 1024):
                        digest.update(data)
                found[rel.name] = digest.hexdigest()
    if set(found) != REQUIRED:
        raise ValueError("Missing Rapido executable in portable ZIP")
    for name in REQUIRED:
        if found[name] != sums[name]:
            raise ValueError("Portable executable SHA-256 mismatch: " + name)
    return {"status": "UNPUBLISHED_ARTIFACT_HASHES_MATCH",
            "release_authorized": False, "production_signed": False,
            "workflow_run_id": run_id, "tested_source_commit": tested_source_commit.lower(),
            "installer": installers[0], "portable": archives[0],
            "verified_sha256_entries": sorted(sums)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--tested-source-commit", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.artifact_directory, args.run_id, args.tested_source_commit),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
