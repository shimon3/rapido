from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTICE = ROOT / "THIRD-PARTY-NOTICES.md"
GATES = ROOT / "docs" / "release-signing-and-license-gates.md"
WORKFLOW = ROOT / ".github" / "workflows" / "windows.yml"
SIGNING_PLAN = ROOT / "scripts" / "windows_signing_plan.ps1"
MSIX_STUDY = ROOT / "docs" / "msix-browser-compatibility.md"
UPDATE_CONTRACT = ROOT / "docs" / "update-security-contract.md"


def test_third_party_notice_exposes_evidence_and_copyleft_sources():
    text = NOTICE.read_text(encoding="utf-8")
    for required in (
        "third-party/inventory.json",
        "third-party/payload.json",
        "pystray 0.19.5",
        "COPYING.LGPL",
        "certifi 2026.7.22",
        "MPL-2.0",
        "proxy_tools 0.1.0",
        "UPSTREAM-LICENSE.txt",
        "not a legal opinion",
    ):
        assert required in text


def test_release_gate_does_not_claim_signing_or_issue_26_completion():
    text = GATES.read_text(encoding="utf-8")
    assert "does not contain a\ncertificate, private key, secret" in text
    assert "Signing alone does not prevent" in text
    assert "keep #26 open" in text
    assert "must never be committed" in text


def test_windows_bundle_contains_top_level_notice():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    expected = (
        "Copy-Item -LiteralPath THIRD-PARTY-NOTICES.md "
        "-Destination dist/Rapido/THIRD-PARTY-NOTICES.md"
    )
    assert expected in workflow


def test_signing_readiness_is_audit_only_and_is_run_by_ci():
    script = SIGNING_PLAN.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "Get-AuthenticodeSignature" in script
    assert "production_signing_enabled = $false" in script
    assert "Private-key material must not be present" in script
    assert "signtool" not in script.lower()
    assert "Set-AuthenticodeSignature" not in script
    assert "windows_signing_plan.ps1" in workflow
    assert "dist/signing-plan.json" in workflow


def test_msix_study_keeps_browser_compatibility_unproven():
    text = MSIX_STUDY.read_text(encoding="utf-8")
    assert "Keep the Inno Setup installer for the current beta" in text
    assert "Chrome, Edge, and Firefox" in text
    assert "unvirtualizedResources" in text
    assert "MSIX remains a research path" in text


def test_automatic_updates_remain_gated_on_production_signing():
    text = UPDATE_CONTRACT.read_text(encoding="utf-8")
    assert "does not silently download or execute" in text
    assert "exact publisher" in text
    assert "Windows 10 and Windows 11" in text
    assert "current manual update link is\nthe safe beta behavior" in text
