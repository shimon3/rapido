# Work state — Rapido

Updated: 2026-10-15. This is a restart checkpoint, not a release report.

## Scope and rules

- Repository: `shimon3/rapido`; local branch: `work/security-26-followup-20261015`.
- Base: PR #29, `5890214882410d6e5b5a1da4a4f25d49bbad4844`.
- Main observed: `18e0997ed0e09ed73d3723faef0904f2c5964af0`.
- No merge, tag, release, store publication or tests on the user's PC.
- User authorization (2026-10-15): ordinary pushes to dedicated branches, draft PRs and non-publishing Actions are allowed. No direct main changes, force-push, merge, release, publication tag or deployment. Check workflow triggers before every push.
- Work on one task at a time; read this checkpoint before targeted files.
- Run focused checks first. Never weaken security checks to save quota.

## Repository map (initial overview completed)

| Area | Relevant files | Responsibility |
| --- | --- | --- |
| Desktop/UI | `desktop.py`, `index.html`, `window.html`, `webview_auth.py` | Native Windows windows, protected local requests |
| API | `app.py`, `local_auth.py`, `trusted_api.py` | Bearer enforcement, in-process dispatch |
| Downloads | `engine.py`, `ytworker.py`, `native_handoff.py` | Download/resume, encrypted persistence, prepare/commit recovery |
| Browser | `extension/`, `scripts/build_browser_extension.py` | Public capture; private/cookie-dependent contexts stay in browser |
| Native boundary | `native_host.py`, `native_pipe.py`, `windows_peer.py`, `native_launcher.py`, `windows_ipc.py` | Framing, pipe ACLs, kernel process identity, launcher checks |
| Deployment | `native_registration.py`, `packaging/rapido.iss`, `.github/workflows/windows.yml` | HKCU registration, per-user installer, Windows build and smoke checks |
| Verification | `tests/`, `scripts/firefox_native_smoke.py` | Security/engine regressions and compiled/browser CI |

Overview used the tracked file inventory, README, recent commits, threat-model/review documents, deployment files and boundary functions. It was not a line-by-line audit of every file.

## Confirmed remote state

- [Issue #30](https://github.com/shimon3/rapido/issues/30) closed: stack reconciliation complete; do not repeat it.
- [PR #29](https://github.com/shimon3/rapido/pull/29) open and draft; base PR #27. Earlier stack remains unmerged.
- [Issue #26](https://github.com/shimon3/rapido/issues/26) open: independent executable/registration trust anchor required. Design/review precedes runtime changes.
- Existing path/SID checks and DPAPI do not establish same-user executable integrity. No production signer or managed policy has been verified here.

## Current targeted task

Resume 2026-10-15: #26/PR #32 handle hardening. Added held-handle disk type, attribute and resolved-path checks before verification and admission. Added Windows fixtures for actual NTFS junctions, leaf symlinks, and replacement by an independent child process while held and after release. No runtime admission wiring; same-user compromise remains unresolved.

Files: `windows_signature.py`, `tests/test_windows_signature.py`, `scripts/test_windows_signature.ps1`, `.github/workflows/windows.yml`, `tests/test_workflow_release_policy.py`, contract and checkpoint.

Focused new checks on Linux: **9 passed, 6 Windows/fixture skips, 36 subtests passed**. Windows validation pending for these new changes. Workflow unchanged: dedicated branch push has no trigger; its draft PR triggers read-only builds with release gated to explicit tag pushes only. Next: inspect this revision's real Windows CI, then examine remaining PRs/licensing and produce the beta task/effort list.

Windows CI #178 (`38682472805`, `91b2fa6`) ran all 15 signed-fixture tests: 14 passed; cross-process replacement was denied with WinError 5 while the test expected WinError 32. Corrected the assertion to recognize both denial codes and additionally require the unsigned source still exists and the signed destination's SHA-256 is unchanged. Junction and symlink rejection tests passed in #178. Production verification rules unchanged; rerun Windows required.

## Validation and handoff

Completed the proposed managed-mode contract and linked it from the threat model. Primary vendor documentation checked for Edge discovery/policy, Chromium policy, Mozilla registration, WinVerifyTrust and App Control. Runtime and workflow files unchanged.

Focused baseline: Python 3.12/Linux, isolated virtual environment, Node 24.19.0. Command:

```bash
python -m pytest -q -rs tests/test_native_registration.py tests/test_windows_peer_identity.py tests/test_native_launcher_policy.py tests/test_native_pipe_transport.py tests/test_installer_process_scope.py
```

Result: **26 passed, 15 skipped** (Windows-specific API/registry/junction/pipe tests), 0.17 s. This checks existing behavior only, not the proposed integrity mechanism. `git diff --check` passed. No full suite or Windows packaging rerun for this documentation-only change. Windows API, registry, junction, compiled installer and real-browser validation must not be inferred from Linux results.

Current focused results (Linux): **35 passed, 18 skipped, 37 subtests passed** across signature, workflow publication guards, registration, process identity, launcher, pipe and installer tests. The 18 skips require Windows APIs or isolated signed fixtures. YAML parsed successfully; `git diff --check` passed. No full Linux suite needed before the Windows CI, which runs focused real signed fixtures first and the complete regression/build/browser pipeline afterward.

CI hardening: build token now read-only. The sole write-enabled release job requires a successful build AND a push event on `refs/tags/v*`. Automatic main releases are removed; dispatch and PR runs cannot publish. No deployment step exists. No publication tag is created by this work.

Draft [PR #32](https://github.com/shimon3/rapido/pull/32) created against PR #29's branch. Implementation commit `65e4e043116d5844fdead7835e8a6d8b6979d506` is confirmed remotely; local/index/remote trees matched. Windows CI #176 (run `38673085039`) reached the isolated signing step but remained there for several minutes; in-progress logs returned 404, so its exact cause is unconfirmed. The harness now uses the disposable VM's machine root store instead of per-user root-store consent, logs each stage and has a 3-minute step timeout. Required verification policy is unchanged. Certificates/keys/fixtures are removed by finally cleanup; forced runner termination relies on disposal of the GitHub-hosted VM.

## Latest validated result

Implementation HEAD: `eb450864681769f24412e3efb2137cb9c0217415`.
[Windows CI #177](https://github.com/shimon3/rapido/actions/runs/38673512236) **SUCCESS**; build job `116221787998`. Logs confirmed:

- Real signed PE/incorrect trusted signer/tamper/unsigned/file-lock tests: **10 passed, 32 subtests passed**, no skips. Exact temporary certificates/private keys/files removed by the harness.
- Complete regression suite: **152 passed, 2 skipped, 1 warning, 81 subtests passed**. The two skips are signed-fixture tests in the ordinary suite after fixture cleanup; both ran in the prior dedicated step.
- Desktop and native-host compilation, real-window self-test, installer registration/unregistration, foreign-process/portable coexistence, real Firefox handoff, packaging and artifact upload all succeeded.
- Build token's actual log reports `Contents: read`; the separate release job `116222898250` was **skipped**. No release or deployment performed.

This final checkpoint changes documentation only and uses `[skip ci]` to avoid repeating the same packaging pipeline; executable code, tests and workflow remain byte-for-byte those validated at the implementation HEAD above. Do not claim this documentation commit itself ran CI; rerun exact-head/integration checks before any future authorized merge/release.

## Remaining work and restart

Next #26 gate: review/select the concrete enforcement profile before runtime admission wiring. Required inputs remain production signer lifecycle and a supported managed browser/OS deployment profile, including PyInstaller payload coverage and Firefox selection evidence. No production certificate or enforced installation policy is configured or assumed. The verifier alone cannot close #26. No automatic downgrade from managed mode is acceptable.

Open-issue inventory checked after CI: #3 (API/extension S2/S3), #26 (independent trust), #28 (installer process scope). #3/#28 corrections already exist in the dependent draft stack through #29; they remain unmerged. Do not redo stack reconciliation or close findings that remain present on main. Next code task must address an unvalidated admission requirement from the managed contract, not duplicate existing draft fixes.

CI #176 (`38673085039`, old commit `65e4e04`) stalled in the old per-user signing harness and is not validation evidence. Its job has the existing 30-minute bound. The available connector exposes no cancellation operation; no cancellation is claimed. The corrected harness passed in #177 with a 3-minute step bound.

Never use `main` or publication tags for this work. Initial checkpoint successfully saved remotely as `6c90a7a1863d594c802fedea06e823597d8f4cd6`; Git fetch confirmed identical local/remote trees. Local Git has no write credentials, so use GitHub connector Git-data operations for ordinary fast-forward branch updates; preserve parent ancestry and verify remote HEAD after each update.

The earlier push was rejected by automatic approval review; explicit user authorization has resolved that limitation. Pre-push inspection found only `.github/workflows/windows.yml`: push branches are `main` and `staging/pr-29-restack-20261014`, tags `v*`. This work branch matches none, so its push does not trigger that workflow. PR runs cannot satisfy the new release job's event/ref gate. Review the workflow again if it changes before another push.
