"""Fail-closed checks for the beta.2 public release readiness evidence.

These tests never authorize a release; they protect documentation from
mistakenly presenting an unsigned CI artifact as production-ready.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
READINESS = DOCS / "beta2-public-release-readiness-2026-11-11.md"
CHECKLIST = DOCS / "beta-publication-checklist.md"
WINDOWS = DOCS / "beta2-windows-acceptance-record.md"
LEGAL = DOCS / "beta2-licence-review-worksheet.md"
NOTES = DOCS / "beta-release-notes.md"
WORKFLOW = ROOT / ".github" / "workflows" / "windows.yml"


def test_readiness_does_not_approve_signing_or_owner_security_decision():
    text = READINESS.read_text(encoding="utf-8")
    assert "NO-GO for public distribution" in text
    assert "awaiting owner sign-off" in text
    assert "issue #26" in text
    assert "No checkbox in this dossier constitutes an automatic authorization" in text
    assert "No approved publisher certificate" in text or "Unsigned." in text
    assert "release-signing" in text
    assert "publishable=false" in text


def test_real_windows_acceptance_remains_explicitly_unperformed():
    text = WINDOWS.read_text(encoding="utf-8")
    assert "**Status: NOT EXECUTED.**" in text
    assert "Server 2025" in text
    assert "PENDING" in text
    assert "Windows 10" in text and "Windows 11" in text
    # Twenty real acceptance rows, each must remain pending until evidence exists.
    rows = [line for line in text.splitlines()
            if line.startswith("| ") and line.split("|", 2)[1].strip().isdigit()]
    assert len(rows) == 20
    assert all(row.count("PENDING") == 2 for row in rows)


def test_licence_review_requires_written_human_signoff():
    text = LEGAL.read_text(encoding="utf-8")
    assert "PENDING HUMAN REVIEW" in text
    assert "not legal clearance" in text
    for question in ("L1a", "L1b", "L2", "L3", "L4", "L5", "L6"):
        assert f"| {question} |" in text
    assert "signed" in text.lower()
    assert "certifi 2026.10.23" in text
    assert "pydantic-core 2.50.2" in text


def test_beta_notes_are_draft_and_do_not_claim_option_a_approved():
    notes = NOTES.read_text(encoding="utf-8")
    assert "n'est **pas publiée**" in notes
    assert "Option A proposée, mais non encore approuvée" in notes
    assert "UNPUBLISHED-*" in notes


def test_release_guard_remains_hardcoded_false_and_readiness_matches():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    release = workflow.split("\n  release:\n", 1)[1]
    readiness = READINESS.read_text(encoding="utf-8")
    checklist = CHECKLIST.read_text(encoding="utf-8")
    assert 'echo "publishable=false"' in workflow
    assert "needs.build.outputs.publishable == 'true'" in release
    assert "NO-GO" in readiness and "NO-GO" in checklist
    assert "before 2026-11-10" not in checklist
    dossier_artifact = re.search(r'^\| Unpublished artifact \|.*artifact ID `(\d+)`', readiness, re.MULTILINE)
    checklist_artifact = re.search(r'^\| P1 \|.*artifact `(\d+)`', checklist, re.MULTILINE)
    assert dossier_artifact, "readiness dossier must identify its current unpublished artifact"
    assert checklist_artifact, "private-beta checklist must identify the frozen artifact"
    assert dossier_artifact.group(1) == checklist_artifact.group(1)
