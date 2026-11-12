# Windows 10/11 owner acceptance record — Rapido 1.3.0-beta.2

**Status: NOT EXECUTED.** This template does not represent test evidence.

Use [windows-validation-matrix.md](windows-validation-matrix.md) for the full
20-scenario signed beta matrix and
[private-beta/checklist-windows.md](private-beta/checklist-windows.md) only for
the separate private unsigned track. The final signed artifact may differ from
the currently green unsigned GitHub Actions artifact.

## Identity of exact tested files

| Field | Windows 10 | Windows 11 |
| --- | --- | --- |
| Test date / tester | PENDING | PENDING |
| OS edition and build | PENDING | PENDING |
| Browser Chrome/Edge/Firefox versions | PENDING | PENDING |
| WebView2 Runtime version | PENDING | PENDING |
| Candidate source commit | PENDING | PENDING |
| Installer SHA-256 | PENDING | PENDING |
| Portable ZIP SHA-256 | PENDING | PENDING |
| Approved candidate manifest / signature pin | PENDING | PENDING |
| Before/after evidence JSON | PENDING | PENDING |

The exact candidate must be independently verified by
`scripts/verify_release_candidate.ps1` **before running the installer**.
Attach the generated evidence files to the private review, not to a public bug
report if they contain user data.

## Required tests

| # | Test | Windows 10 | Windows 11 |
| --- | --- | --- | --- |
| 1 | Clean user-mode installation, certificate and UAC | PENDING | PENDING |
| 2 | First launch, no traceback | PENDING | PENDING |
| 3 | WebView2 window and interaction | PENDING | PENDING |
| 4 | Tray controls work | PENDING | PENDING |
| 5 | Browser Native Messaging registrations correct | PENDING | PENDING |
| 6 | Chrome + Edge + Firefox real native handoff | PENDING | PENDING |
| 7 | Single download hash matches | PENDING | PENDING |
| 8 | At least three concurrent downloads | PENDING | PENDING |
| 9 | Interrupted download resumes to correct SHA-256 | PENDING | PENDING |
| 10 | Upgrade from last stable version retains settings | PENDING | PENDING |
| 11 | Same-version reinstall | PENDING | PENDING |
| 12 | Installer repair of missing native host | PENDING | PENDING |
| 13 | Uninstall keeps unrelated processes | PENDING | PENDING |
| 14 | This install's browser registrations cleanly removed | PENDING | PENDING |
| 15 | History and user downloads remain after uninstall | PENDING | PENDING |
| 16 | Portable continues after installed copy removed | PENDING | PENDING |
| 17 | Exact signed publisher, timestamp and trust | PENDING | PENDING |
| 18 | Manifest / extracted payload / installer and ZIP SHA-256 | PENDING | PENDING |
| 19 | SmartScreen behaviour recorded, no bypass prescribed | PENDING | PENDING |
| 20 | Untrusted replacement rejected where enforced; per-user residual risk stated | PENDING | PENDING |

Use `PASS` / `FAIL` / `NOT APPLICABLE` only with explicit evidence and a
reason. Any issue must link to a bug and an owner decision. Do not falsify a
test result from GitHub Server 2025 automation.

## Owner sign-off

- Windows 10 evaluator: **PENDING**
- Windows 11 evaluator: **PENDING**
- Any blocking failures: **UNDETERMINED**
- Signed candidate ready: **NO**
- Approval date and signer: **PENDING**
