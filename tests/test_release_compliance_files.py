from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTICE = ROOT / "THIRD-PARTY-NOTICES.md"
GATES = ROOT / "docs" / "release-signing-and-license-gates.md"
WORKFLOW = ROOT / ".github" / "workflows" / "windows.yml"


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
    assert "does not contain a certificate, private key, secret" in text
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
