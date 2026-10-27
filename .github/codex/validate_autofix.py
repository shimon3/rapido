#!/usr/bin/env python3
"""Validate a Codex-generated Rapido patch before any privileged job applies it."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path


MAX_PATCH_BYTES = 100_000
MAX_FILES = 8
MAX_CHANGED_LINES = 300
ALLOWED_EXACT = {
    "app.py",
    "desktop.py",
    "engine.py",
    "index.html",
    "native_host.py",
    "rapido_version.py",
    "window.html",
    "ytworker.py",
}
ALLOWED_PREFIXES = ("extension/", "tests/")
SAFE_PATH = re.compile(r"^[A-Za-z0-9._/-]+$")
DIFF_HEADER = re.compile(r"^diff --git a/([^ ]+) b/([^ ]+)$")
SECRET_VALUE = re.compile(
    r"(?i)(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{16,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
FORBIDDEN_ADDITIONS = (
    "OPENAI_API_KEY",
    "GITHUB_TOKEN",
    "danger-full-access",
    "pull_request_target",
    "permissions: write-all",
    "publishable=true",
    "action-gh-release",
    "gh release ",
)


class PolicyError(ValueError):
    pass


def allowed_path(path: str) -> bool:
    if not SAFE_PATH.fullmatch(path):
        return False
    if path.startswith("/") or path.startswith(".") or ".." in path.split("/"):
        return False
    if path.rsplit("/", 1)[-1].casefold() in {"agents.md", "agents.override.md"}:
        return False
    return path in ALLOWED_EXACT or path.startswith(ALLOWED_PREFIXES)


def validate_result(data: object) -> dict:
    if not isinstance(data, dict):
        raise PolicyError("Codex result must be a JSON object")
    expected = {"decision", "patch", "root_cause", "summary", "test_plan", "risk_notes"}
    if set(data) != expected:
        raise PolicyError("Codex result has missing or unexpected properties")
    if data["decision"] not in {"propose", "stop"}:
        raise PolicyError("Invalid decision")
    if not isinstance(data["patch"], str) or len(data["patch"].encode("utf-8")) > MAX_PATCH_BYTES:
        raise PolicyError("Invalid or oversized patch field")
    for name, limit in (("root_cause", 2000), ("summary", 1000)):
        if not isinstance(data[name], str) or not data[name].strip() or len(data[name]) > limit:
            raise PolicyError(f"Invalid {name}")
    for name in ("test_plan", "risk_notes"):
        value = data[name]
        if not isinstance(value, list) or len(value) > 8:
            raise PolicyError(f"Invalid {name}")
        if any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in value):
            raise PolicyError(f"Invalid item in {name}")
    if SECRET_VALUE.search(json.dumps(data, ensure_ascii=False)):
        raise PolicyError("Codex result contains a credential-like value")
    return data


def validate_patch(patch: bytes) -> dict:
    if not patch:
        raise PolicyError("Patch is empty")
    if len(patch) > MAX_PATCH_BYTES:
        raise PolicyError(f"Patch exceeds {MAX_PATCH_BYTES} bytes")
    try:
        text = patch.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PolicyError("Patch is not UTF-8 text") from exc
    if SECRET_VALUE.search(text):
        raise PolicyError("Patch contains a credential-like value")

    forbidden_metadata = (
        "GIT binary patch",
        "Binary files ",
        "deleted file mode ",
        "old mode ",
        "rename from ",
        "rename to ",
        "copy from ",
        "copy to ",
        "Subproject commit ",
    )
    files: list[str] = []
    changed_lines = 0
    current_path: str | None = None
    old_header_seen = False
    new_header_seen = False
    new_file = False
    in_hunk = False

    def finish_file() -> None:
        if current_path is not None and not (old_header_seen and new_header_seen):
            raise PolicyError(f"Patch headers are incomplete for {current_path}")

    for line in text.splitlines():
        if line.startswith("diff --git "):
            finish_file()
            match = DIFF_HEADER.fullmatch(line)
            if not match or match.group(1) != match.group(2):
                raise PolicyError("Quoted, renamed, or malformed path in patch")
            path = match.group(1)
            if not allowed_path(path):
                raise PolicyError(f"Path is outside the autofix allowlist: {path}")
            files.append(path)
            current_path = path
            old_header_seen = False
            new_header_seen = False
            new_file = False
            in_hunk = False
            continue
        if line.startswith(forbidden_metadata):
            raise PolicyError(f"Forbidden patch metadata: {line[:80]}")
        if current_path is None:
            if line.startswith(("--- ", "+++ ", "@@ ")):
                raise PolicyError("Patch data appears before a file header")
            continue
        if not in_hunk and line.startswith("new file mode "):
            if line != "new file mode 100644":
                raise PolicyError("Only regular non-executable new files are allowed")
            new_file = True
            continue
        if not in_hunk and line.startswith("--- "):
            expected = "/dev/null" if new_file else f"a/{current_path}"
            if old_header_seen or line != f"--- {expected}":
                raise PolicyError(f"Old-file header does not match {current_path}")
            old_header_seen = True
            continue
        if not in_hunk and line.startswith("+++ "):
            if not old_header_seen or new_header_seen or line != f"+++ b/{current_path}":
                raise PolicyError(f"New-file header does not match {current_path}")
            new_header_seen = True
            continue
        if line.startswith("@@ "):
            if not (old_header_seen and new_header_seen):
                raise PolicyError(f"Patch hunk appears before headers for {current_path}")
            in_hunk = True
            continue
        if in_hunk and line.startswith("+"):
            changed_lines += 1
            if any(token in line for token in FORBIDDEN_ADDITIONS):
                raise PolicyError("Patch adds an automation, credential, or release token")
        elif in_hunk and line.startswith("-"):
            changed_lines += 1

    finish_file()

    unique_files = list(dict.fromkeys(files))
    if not unique_files:
        raise PolicyError("Patch does not contain a file diff")
    if len(unique_files) != len(files):
        raise PolicyError("A file appears in multiple independent diffs")
    if len(unique_files) > MAX_FILES:
        raise PolicyError(f"Patch changes more than {MAX_FILES} files")
    if changed_lines > MAX_CHANGED_LINES:
        raise PolicyError(f"Patch changes more than {MAX_CHANGED_LINES} lines")

    return {
        "files": unique_files,
        "file_count": len(unique_files),
        "changed_lines": changed_lines,
        "bytes": len(patch),
    }


def validate_files(result_path: Path, patch_path: Path) -> dict:
    result = validate_result(json.loads(result_path.read_text(encoding="utf-8")))
    patch = patch_path.read_bytes()
    try:
        proposal = result["patch"].encode("utf-8")
    except UnicodeEncodeError as exc:
        raise PolicyError("Patch field is not valid UTF-8") from exc
    if proposal != patch:
        raise PolicyError("Patch file does not match the JSON patch field")
    if result["decision"] == "stop":
        if patch.strip():
            raise PolicyError("A stop decision must not modify tracked files")
        return {"files": [], "file_count": 0, "changed_lines": 0,
                "bytes": len(patch), "decision": "stop"}
    report = validate_patch(patch)
    report["decision"] = result["decision"]
    return report


def self_test() -> None:
    safe_patch = b"""diff --git a/engine.py b/engine.py
index 1111111..2222222 100644
--- a/engine.py
+++ b/engine.py
@@ -1 +1 @@
-OLD = True
+OLD = False
"""
    result = {
        "decision": "propose",
        "patch": safe_patch.decode("utf-8"),
        "root_cause": "Confirmed regression",
        "summary": "Constrained correction",
        "test_plan": ["Run the existing regression test"],
        "risk_notes": ["Human review remains required"],
    }
    unsafe_patch = safe_patch.replace(b"engine.py", b".github/workflows/windows.yml")
    delete_patch = safe_patch.replace(b"index 1111111..2222222 100644", b"deleted file mode 100644")
    spoofed_headers = safe_patch.replace(
        b"--- a/engine.py\n+++ b/engine.py",
        b"--- a/.github/workflows/windows.yml\n+++ b/.github/workflows/windows.yml",
    )
    secret_patch = safe_patch.replace(b"OLD = False", b"TOKEN = 'sk-proj-abcdefghijklmnopqrstuvwxyz'")
    validate_result(result)
    validate_patch(safe_patch)
    for candidate in (unsafe_patch, delete_patch, spoofed_headers, secret_patch):
        try:
            validate_patch(candidate)
        except PolicyError:
            continue
        raise AssertionError("Unsafe fixture unexpectedly passed")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "result.json").write_text(json.dumps(result), encoding="utf-8")
        (root / "change.patch").write_bytes(safe_patch)
        validate_files(root / "result.json", root / "change.patch")
        (root / "change.patch").write_bytes(safe_patch + b"\n")
        try:
            validate_files(root / "result.json", root / "change.patch")
        except PolicyError:
            pass
        else:
            raise AssertionError("A patch that differs from the JSON proposal passed")
        (root / "change.patch").write_bytes(safe_patch)
        result["decision"] = "stop"
        result["patch"] = ""
        (root / "result.json").write_text(json.dumps(result), encoding="utf-8")
        (root / "change.patch").write_bytes(b"")
        validate_files(root / "result.json", root / "change.patch")
        (root / "change.patch").write_bytes(safe_patch)
        try:
            validate_files(root / "result.json", root / "change.patch")
        except PolicyError:
            pass
        else:
            raise AssertionError("A stop decision unexpectedly carried a patch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path)
    parser.add_argument("--patch", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
            print("autofix policy self-test: ok")
            return 0
        if not args.result or not args.patch:
            parser.error("--result and --patch are required unless --self-test is used")
        print(json.dumps(validate_files(args.result, args.patch), sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, PolicyError) as exc:
        print(f"autofix policy rejected output: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
