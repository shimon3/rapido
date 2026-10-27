"""Security regression tests for the disabled guarded Codex workflow."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / ".github" / "codex" / "validate_autofix.py"
WORKFLOW = ROOT / ".github" / "workflows" / "rapido-codex-autofix.yml"

spec = importlib.util.spec_from_file_location("rapido_autofix_policy", VALIDATOR)
policy = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(policy)


def result(decision: str = "propose") -> dict:
    return {
        "decision": decision,
        "root_cause": "Confirmed regression",
        "summary": "Constrained correction",
        "test_plan": ["Run the focused regression test"],
        "risk_notes": ["Human review remains required"],
    }


SAFE_PATCH = b"""diff --git a/engine.py b/engine.py
index 1111111..2222222 100644
--- a/engine.py
+++ b/engine.py
@@ -1 +1 @@
-OLD = True
+OLD = False
"""


def test_patch_headers_cannot_escape_the_allowlist():
    spoofed = SAFE_PATCH.replace(
        b"--- a/engine.py\n+++ b/engine.py",
        b"--- a/.github/workflows/windows.yml\n+++ b/.github/workflows/windows.yml",
    )
    with pytest.raises(policy.PolicyError, match="header does not match"):
        policy.validate_patch(spoofed)


def test_stop_decision_requires_an_empty_patch(tmp_path):
    result_path = tmp_path / "result.json"
    patch_path = tmp_path / "change.patch"
    result_path.write_text(json.dumps(result("stop")), encoding="utf-8")
    patch_path.write_bytes(SAFE_PATCH)
    with pytest.raises(policy.PolicyError, match="must not modify"):
        policy.validate_files(result_path, patch_path)


def test_credential_shaped_output_is_rejected():
    unsafe = SAFE_PATCH.replace(
        b"OLD = False", b"TOKEN = 'sk-proj-abcdefghijklmnopqrstuvwxyz'"
    )
    with pytest.raises(policy.PolicyError, match="credential-like"):
        policy.validate_patch(unsafe)


def test_workflow_trusts_only_bot_attempt_markers_and_separates_privileges():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert '.user.login == "github-actions[bot]" and .user.type == "Bot"' in source

    generate = source.split("\n  generate:\n", 1)[1].split("\n  publish:\n", 1)[0]
    publish = source.split("\n  publish:\n", 1)[1].split("\n  dispatch_validation:\n", 1)[0]
    dispatch = source.split("\n  dispatch_validation:\n", 1)[1].split("\n  report_stop:\n", 1)[0]

    assert "contents: write" not in generate
    assert "RAPIDO_CODEX_OPENAI_API_KEY" in generate
    assert "RAPIDO_CODEX_OPENAI_API_KEY" not in publish
    assert "actions: write" not in publish
    assert "actions: write" in dispatch
    assert "contents: write" not in dispatch
    assert "gh pr merge" not in source
    assert "gh release" not in source
    assert "git tag" not in source
