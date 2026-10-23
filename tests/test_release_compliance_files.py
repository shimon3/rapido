from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTICE = ROOT / "THIRD-PARTY-NOTICES.md"
GATES = ROOT / "docs" / "release-signing-and-license-gates.md"
WORKFLOW = ROOT / ".github" / "workflows" / "windows.yml"
SIGNING_PLAN = ROOT / "scripts" / "windows_signing_plan.ps1"
MSIX_STUDY = ROOT / "docs" / "msix-browser-compatibility.md"
UPDATE_CONTRACT = ROOT / "docs" / "update-security-contract.md"
PUBLICATION_CHECKLIST = ROOT / "docs" / "beta-publication-checklist.md"
AUTHENTICODE_OPTIONS = ROOT / "docs" / "authenticode-options-israel.md"
README = ROOT / "README.md"
BETA_NOTES = ROOT / "docs" / "beta-release-notes.md"


def test_third_party_notice_exposes_evidence_and_copyleft_sources():
    text = NOTICE.read_text(encoding="utf-8")
    for required in (
        "third-party/inventory.json",
        "third-party/payload.json",
        "pystray 0.19.5",
        "COPYING.LGPL",
        "certifi 2026.10.19",
        "MPL-2.0",
        "proxy_tools 0.1.0",
        "UPSTREAM-LICENSE.txt",
        "not a legal opinion",
        "third-party/source/pystray-0.19.5/",
        "third-party/source/certifi-2026.10.19/",
        "Bootloader Exception",
    ):
        assert required in text


def test_third_party_notice_paths_match_the_collector_layout():
    text = NOTICE.read_text(encoding="utf-8")
    collector = (ROOT / "scripts" / "collect_license_evidence.py").read_text(encoding="utf-8")
    # The WebView2 SDK texts are written under the pywebview package folder.
    assert "third-party/webview2-sdk/" not in text
    assert "third-party/packages/pywebview/Microsoft.Web.WebView2-1.0.3856.49/" in text
    assert '"packages/pywebview/Microsoft.Web.WebView2-1.0.3856.49/"' in collector
    assert 'f"source/{reviewed[\'folder\']}/{relative}"' in collector


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
    assert "bounded to 2 MiB" in text
    assert "exact HTTPS GitHub API endpoint" in text
    assert "exact publisher" in text
    assert "Windows 10 and Windows 11" in text
    assert "current manual update link is\nthe safe beta behavior" in text


def test_unsigned_ci_artifacts_cannot_reach_the_release_job():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    release = workflow.split("\n  release:\n", 1)[1]
    assert "publishable: ${{ steps.ver.outputs.publishable }}" in workflow
    assert 'echo "publishable=false"' in workflow
    assert "needs.build.outputs.publishable == 'true'" in release
    assert "UNPUBLISHED-Rapido-" in workflow
    assert "ci-artifact-provenance.json" in workflow
    assert "official_release = $false" in workflow
    assert "production_signed = $false" in workflow
    assert "retention-days: 14" in workflow
    assert "Exécuter quand même" not in release


def test_publication_checklist_keeps_external_gates_open():
    text = PUBLICATION_CHECKLIST.read_text(encoding="utf-8")
    assert "Windows 10" in text and "Windows 11" in text
    assert "Chrome" in text and "Edge" in text and "Firefox" in text
    assert "Human legal review" in text
    assert "Do not publish" in text
    assert "Track P" in text and "Track S" in text
    assert "verify_release_candidate.ps1 -Record" in text
    # Every remaining task states whether it blocks and who acts next.
    rows = [line for line in text.splitlines() if line.startswith(("| P", "| S")) and not line.startswith("| ID")]
    assert len(rows) >= 10
    assert all(line.count("|") == 9 for line in rows)


def test_authenticode_options_do_not_claim_a_purchase_or_eligibility():
    text = AUTHENTICODE_OPTIONS.read_text(encoding="utf-8")
    assert "No certificate has been purchased" in text
    assert "Samuel Bentouza" in text
    assert "Israel" in text
    assert "eligibility must be confirmed" in text
    assert "SHA-256" in text and "RFC 3161" in text


def test_public_docs_do_not_tell_users_to_bypass_smartscreen_or_publish_by_tag():
    readme = README.read_text(encoding="utf-8")
    notes = BETA_NOTES.read_text(encoding="utf-8")
    combined = readme + "\n" + notes
    assert "Run anyway" not in combined
    assert "Exécuter quand même" not in combined
    assert "A tag alone cannot create a release" in readme
    assert "Un tag seul ne peut plus publier" in notes
    assert "UNPUBLISHED-*" in readme
