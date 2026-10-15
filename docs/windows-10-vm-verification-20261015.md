# Windows 10 VM verification — 2026-10-15

Scope: read-only inventory through Remote Desktop Commander and current GitHub/Actions metadata. No Rapido installation, system changes, or VM restart performed. No credentials or passwords recorded.

## VM checks

| Check | Result | Evidence / limit |
|---|---|---|
| Remote access | PASS via Remote Desktop Commander | Device DESKTOP-F2ALUG9 responded to ping and read-only PowerShell inventory. |
| Direct SSH from this executor | BLOCKED | TCP probe to 192.168.8.137:22 failed here. The owner reports SSH works from their PC; that route is not available from this executor. |
| Identity and OS | PASS | DESKTOP-F2ALUG9; DESKTOP-F2ALUG9\samue; Windows 10 Pro 22H2, build 19045.6456, 64-bit. Last boot reported 2026-10-15 16:08:42 (machine-local time). |
| WebView2 and browsers | PASS | Edge WebView2 Runtime 155.0.4283.45; Chrome 155.0.8059.40; Edge 155.0.4283.45; Firefox 158.0. Executables were present at the standard install locations. |
| Defender | PASS | Antivirus and real-time protection enabled; Defender service enabled. Signature timestamp: 2026-10-15 08:22:06 (machine-local time). |
| Rapido presence | PASS — not found in checked locations | No Rapido uninstall entry, running process, or executable in the common per-user/Program Files locations queried. This was not a full-disk search. |
| Snapshot | USER-CONFIRMED | Snapshot “Win10-22H2-avant-Rapido” was reported as created; not independently inspected by the connector. |

## Repository and CI

- Default branch `main`: `18e0997ed0e09ed73d3723faef0904f2c5964af0`.
- Draft PR #33 branch `work/beta-engine-guards-20261015`: `f9932c7a9130cd93acd029a5872232e69d11a961`, based on draft PR #32 at `a4cae19e43cffa8028814e46f42b125e1971d918`. PR #33's latest commit only changes `docs/work-state.md`; it records CI #204 and is marked `[skip ci]`.
- Latest successful Windows build: run #204, ID `38724218566`, triggered by `pull_request`. The tested code commit was `08fa5400a64d4ac6ea392982e7ea440ab3c384cb`, parent of the documentation-only PR head above.
- CI summary in the existing tracking file: 236 passed, 5 skipped, 126 subtests. The build, packaged lifecycle checks, Firefox bridge/handoff and artifact upload passed. The self-test returned `ok: true` but logged an asyncio proactor `ConnectionResetError [WinError 10054]`; cause is unknown and should be watched.
- Candidate artifact: `Rapido-1.3.0-beta.1-windows`, 88,892,173 bytes, artifact ID `11967271551`, created 2026-10-15 11:05:07Z, expires 2027-01-13 11:00:10Z. GitHub reports archive digest `sha256:9e0b2410da936093b54e749aa0ddd283f540d8d967b5d2f3b39730143a828f93`. This digest is available for a later download comparison; the archive has not yet been downloaded or independently checked. The executable is unsigned; no Authenticode signature is available.
- CI ran on GitHub-hosted Windows Server 2025. It does not certify installation or browser behavior on this Windows 10 VM.
- The beta readiness notes explicitly state that #26 remains open and the beta is not published. Do not treat the version as a release.

## Workflow safety review

The branch contains one workflow, `.github/workflows/windows.yml`. It grants read-only contents permissions to the build. Pull-request events run the build; the release job requires a push event for a `v*` tag and a true release output. Thus a documentation commit on this PR branch can trigger CI but cannot publish a release. No deployment workflow is present.

## Concrete next test plan — not yet started

1. Download artifact ID `11967271551`; compare the downloaded ZIP SHA-256 to GitHub's reported digest before extraction.
2. Inspect the archive contents and installer metadata without executing it; confirm version and unsigned status.
3. After owner review of these findings and plan, copy the verified candidate into this VM only and install for the current user, with Defender left enabled.
4. Verify install/uninstall entries, running process, app version, WebView2 launch, and Chrome/Edge/Firefox integration using harmless test URLs. Record each browser scenario separately.
5. Do not restart unless the installer or a test demonstrably requires it; if required, report that before restarting. The provided pre-install snapshot is the rollback point.

No installation, reboot, release, or system modification has been performed.
