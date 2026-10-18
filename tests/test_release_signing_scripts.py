"""Static guards for the signing order, rehearsal isolation and secret hygiene."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "scripts" / "RapidoSigning.psm1").read_text(encoding="utf-8")
REHEARSAL = (ROOT / "scripts" / "rehearse_release_signing.ps1").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "windows.yml").read_text(encoding="utf-8")
INSTALLER = (ROOT / "packaging" / "rapido.iss").read_text(encoding="utf-8-sig")
VERIFY = (ROOT / "scripts" / "verify_release_candidate.ps1").read_text(encoding="utf-8")


def test_installer_takes_every_executable_from_the_verified_payload_only():
    sources = re.findall(r'^Source:\s*"([^"]+)"', INSTALLER, flags=re.MULTILINE)
    assert '{#PayloadDir}\\*' in sources
    # A second copy of the native host would overwrite the signed one.
    assert not [s for s in sources if s.lower().endswith(".exe")]
    assert '#define PayloadDir "..\\dist\\Rapido"' in INSTALLER


def test_signing_uses_sha256_digest_and_rfc3161_sha256_timestamp():
    for flag in ("'/fd', 'SHA256'", "'/tr', $TimestampUrl, '/td', 'SHA256'", "'/sha1'"):
        assert flag in MODULE
    assert "Get-RapidoCertificateSha256 $cert) -ne $pin" in MODULE
    assert "'unexpected-signer'" in MODULE and "'missing-timestamp'" in MODULE
    assert "verify /pa /v" in MODULE


def test_signing_code_never_handles_exported_keys_or_secrets():
    combined = (MODULE + REHEARSAL + VERIFY).lower()
    for forbidden in ("export-pfxcertificate", ".pfx", ".p12", "/p ", "-password", "convertto-securestring"):
        assert forbidden not in combined
    assert "secrets." not in WORKFLOW


def test_rehearsal_is_disposable_and_cannot_look_official():
    assert "$env:RUNNER_ENVIRONMENT -ne 'github-hosted'" in REHEARSAL
    assert "NOT AN OFFICIAL SIGNATURE" in REHEARSAL
    assert "-KeyExportPolicy NonExportable" in REHEARSAL
    assert "-DeleteKey" in REHEARSAL
    assert "$env:RUNNER_TEMP" in REHEARSAL
    assert "official_signature = $false" in REHEARSAL
    for case in ("'unsigned'", "'status-HashMismatch'", "'unexpected-signer'", "'missing-timestamp'"):
        assert case in REHEARSAL


def test_rehearsal_follows_the_production_order():
    order = [REHEARSAL.index(marker) for marker in (
        "Stage 1: sign and verify both first-party executables",
        "Stage 2: build the installer only from the verified signed payload",
        "Stage 3: sign and verify the installer",
        "Stage 4: portable ZIP from the same verified payload",
    )]
    assert order == sorted(order)
    assert '"/DPayloadDir=$payload"' in REHEARSAL


def test_workflow_runs_rehearsal_after_installer_and_uploads_only_its_report():
    build = WORKFLOW.index("- name: Build installer (Inno Setup)")
    rehearsal = WORKFLOW.index("- name: Signing order rehearsal")
    audit = WORKFLOW.index("- name: Production signing readiness (audit only)")
    assert build < rehearsal < audit
    upload = WORKFLOW.split("actions/upload-artifact", 1)[1].split("retention-days", 1)[0]
    assert "dist/signing-rehearsal.json" in upload
    assert "rehearsal" not in upload.replace("dist/signing-rehearsal.json", "")


def test_candidate_verification_compares_with_an_approved_manifest():
    assert "ApprovedManifest" in VERIFY
    assert "Test-RapidoSignature" in VERIFY
    assert "missing-from-candidate" in VERIFY and "unexpected-in-candidate" in VERIFY
    assert "hash-mismatch" in VERIFY
