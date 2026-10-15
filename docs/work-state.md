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

Prepare a reviewable managed-mode contract for #26, including host-selection enforcement before browser payload, full packaged dependency coverage, unsigned behavior, lifecycle rules and Windows acceptance evidence.

Files: `docs/windows-managed-integrity-contract.md`, existing threat-model link, this checkpoint. No runtime or workflow changes planned in this task.

## Validation and handoff

Completed the proposed managed-mode contract and linked it from the threat model. Primary vendor documentation checked for Edge discovery/policy, Chromium policy, Mozilla registration, WinVerifyTrust and App Control. Runtime and workflow files unchanged.

Focused baseline: Python 3.12/Linux, isolated virtual environment, Node 24.19.0. Command:

```bash
python -m pytest -q -rs tests/test_native_registration.py tests/test_windows_peer_identity.py tests/test_native_launcher_policy.py tests/test_native_pipe_transport.py tests/test_installer_process_scope.py
```

Result: **26 passed, 15 skipped** (Windows-specific API/registry/junction/pipe tests), 0.17 s. This checks existing behavior only, not the proposed integrity mechanism. `git diff --check` passed. No full suite or Windows packaging rerun for this documentation-only change. Windows API, registry, junction, compiled installer and real-browser validation must not be inferred from Linux results.

Next targeted work: review/select the concrete enforcement profile for #26 before runtime implementation. Required inputs remain production signer lifecycle and a supported managed browser/OS deployment profile, including PyInstaller payload coverage and Firefox selection evidence. Until then #26 stays open; no automatic downgrade from managed mode is acceptable. No new PR is needed just to preserve this checkpoint.

The Windows workflow can publish on a `v*` tag and on `main` when the version tag is absent. Never use those refs for this work. A documentation checkpoint does not need a new PR or a packaging rerun.

The earlier push was rejected by automatic approval review; explicit user authorization has now resolved that limitation. Pre-push inspection found only `.github/workflows/windows.yml`: push branches are `main` and `staging/pr-29-restack-20261014`, tags `v*`. This work branch matches none, so its push does not trigger that workflow. PR runs have `GITHUB_REF=refs/pull/.../merge`, making the existing release output false; no deployment step is present. Further CI hardening is planned before creating a draft PR.
