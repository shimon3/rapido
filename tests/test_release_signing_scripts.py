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


def test_powershell_release_scripts_parse_without_errors():
    import shutil
    import subprocess
    import sys
    import pytest

    if sys.platform != "win32" or not shutil.which("powershell"):
        pytest.skip("Windows PowerShell parser required")
    scripts = sorted(str(p) for p in (ROOT / "scripts").iterdir() if p.suffix in (".ps1", ".psm1"))
    command = (
        "$bad = 0; foreach ($f in $env:RAPIDO_PS_FILES.Split('|')) { $t = $null; $e = $null; "
        "[void][System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$t, [ref]$e); "
        "foreach ($x in $e) { $bad++; Write-Output ($f + ': ' + $x.Message) } }; exit $bad"
    )
    import os
    # -Command would splice extra arguments into the script text.
    env = dict(os.environ, RAPIDO_PS_FILES="|".join(scripts))
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                            capture_output=True, text=True, timeout=120, env=env)
    assert result.returncode == 0, result.stdout + result.stderr


def test_candidate_verification_runs_and_rejects_a_mismatch(tmp_path):
    import hashlib
    import json
    import shutil
    import subprocess
    import sys
    import zipfile
    import pytest

    if sys.platform != "win32" or not shutil.which("powershell"):
        pytest.skip("Windows PowerShell required")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    setup = candidate / "Rapido-Setup-9.9.9.exe"
    setup.write_bytes(b"not a real installer")
    archive = candidate / "Rapido-9.9.9-portable.zip"
    payload = {"Rapido/Rapido.exe": b"exe fixture", "Rapido/RapidoNativeHost.exe": b"host fixture",
               "Rapido/third-party/x.txt": b"notice"}
    with zipfile.ZipFile(archive, "w") as z:
        for name, data in payload.items():
            z.writestr(name, data)
    sha = lambda data: hashlib.sha256(data).hexdigest()
    pin = "ab" * 32
    approved = {
        "schema": 1, "version": "9.9.9", "commit": "0" * 40, "signer_certificate_sha256": pin,
        "files": [{"path": setup.name, "sha256": sha(setup.read_bytes()), "bytes": 1},
                  {"path": archive.name, "sha256": sha(archive.read_bytes()), "bytes": 1}],
        "payload": [{"path": "Rapido.exe", "sha256": sha(b"exe fixture"), "bytes": 1},
                    {"path": "RapidoNativeHost.exe", "sha256": "0" * 64, "bytes": 1},
                    {"path": "missing.dll", "sha256": "1" * 64, "bytes": 1}],
    }
    manifest = tmp_path / "approved.json"
    manifest.write_text(json.dumps(approved), encoding="utf-8")
    import os
    # Windows PowerShell must not inherit PowerShell 7's module path.
    env = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(ROOT / "scripts" / "verify_release_candidate.ps1"), "-CandidateDir", str(candidate),
         "-ApprovedManifest", str(manifest), "-ExpectedCertificateSha256", pin,
         "-ExpectedSubject", "CN=Fixture, O=Test", "-ReportPath", str(tmp_path / "report.json")],
        capture_output=True, text=True, timeout=180, env=env)
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "Candidate REJECTED" in output
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8-sig"))
    problems = report["problems"]
    assert "payload:hash-mismatch:RapidoNativeHost.exe" in problems
    assert "payload:missing-from-candidate:missing.dll" in problems
    assert "payload:unexpected-in-candidate:third-party/x.txt" in problems
    assert any(p.startswith("signature:Rapido-Setup-9.9.9.exe:") for p in problems)
