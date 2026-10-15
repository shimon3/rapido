# Rapido — restart checkpoint

Updated 2026-10-15. Start here; do not repeat repository overview or completed PR reconciliation.

## Goal and authority

First stable Windows beta, essential corrections only. Branch `work/beta-engine-guards-20261015`, draft PR #33 targets draft PR #32's `work/security-26-followup-20261015` (dependent on #29).
Allowed: ordinary dedicated-branch pushes, draft PR updates, nonpublishing Actions. Forbidden: main edits, force-push, merges, publication tags/releases/deployments, tests on user's PC. Verify workflow before each push. One focused task; targeted tests first; preserve security checks. #30 reconciliation complete; #3/#26/#28 remain open.
Main last verified `18e0997ed0e09ed73d3723faef0904f2c5964af0`; check again before changes.

## Current focused correction — launcher path components

Registration already rejected linked ancestors; runtime admission only rejected leaf symlinks. Shared `native_paths.has_linked_component` now applies the same best-effort symlink/junction check to the helper, desktop, recognized browser image and Firefox manifest. A regression first failed before the fix at process inspection; afterward the capture is refused before process inspection/pipe request. Windows-only tests use a real junction for both executables, the manifest and recognized browser path. No fixture executable is launched by these new tests.

Local focused run: 33 passed, 12 Windows/signature-fixture skips, 36 subtests. Full Linux suite: 186 passed, 35 platform/fixture skips, 103 subtests, 1 existing deprecation warning. Windows CI for this correction is pending; #191 below validates the previous code. No independently protected policy, executable attestation or race-free path guarantee is added; #26 remains open. Workflows reviewed before push: one workflow, no work-branch push trigger, PR build read-only, publication job requires explicit tag push. Main SHA rechecked unchanged.

## Latest validated code — CI #191 SUCCESS

`b9a7136ca21d93fe6e0adf811660c73158cd2154`:
https://github.com/shimon3/rapido/actions/runs/38697169313

- 214 general regression tests passed, 5 signed-fixture skips after separate execution, 105 subtests, 1 warning.
- Dedicated signature execution: 15 passed/no skips — 9 policy/unit tests, 1 real unsigned-file test, 5 real signed-PE fixture tests. Counts overlap general suite; never call all 15 real signed fixtures or sum as unique tests.
- Python 3.13.16/OpenSSL 3.5.9 baseline and pip check passed. All 41 exact installed versions/PyPI responses passed the new gate; no active advisory or yank returned then. Not complete vulnerability coverage.
- Both actual WebView2 confirmation probes, desktop/native compilation, real-window engine/yt-dlp test, native protocol, installer/portable coexistence and real Firefox passed. Build token Contents:read; release skipped.
- Runner Windows Server 2025, not Windows 10/11 certification. #191 includes immediate PowerShell exits after each failed pip install; no masking by later pip check.

A documentation-only checkpoint follows with [skip ci]; do not claim that documentation HEAD itself ran CI. Code/tests/workflow identical to validated b9a7136. Future authorized integration needs exact-head/integration checks.

## Latest independently inspected artifact — #190

Artifact `11954004962`, code `b6a5740`, CI run `38696191089`. Archive digest matched GitHub:
`46713a203094f27e1b5600358701df2d056c25d9bca75c7092612594bd4929fc`.
154 payload file hashes/exact membership, 55 embedded native-host binary hashes, 117 package license-text hashes, Python license and unchanged project LICENSE checked. 41 versions match constraints; embedded advisory report has 41 verified responses. Five SDK DLLs and both original SDK text hashes checked; no pytest/_pytest module names. #191's ZIP was not independently downloaded/inspected; do not attach #190 hashes to it.

Current #190 evidence: `docs/beta-payload-inspection-20261015.json`, `docs/beta-build-inventory-20261015.json`, `docs/beta-native-version-resources-20261015.json`, `docs/dependency-advisory-snapshot-20261015.json`.
Full manifest: `third-party/payload.json` inside artifact. Module distribution candidates match RECORD names (not bytecode identity); native candidates match bytes; unknown/ambiguous entries remain visible. PE VERSIONINFO strings are declarative, not signer verification. Historical `beta-artifact-verification` and `critical-actions-validation` JSON files concern #183/#189 respectively. Current review/difficulty/conditional effort plan: `docs/beta-readiness-20261015.md`.

## Completed — do not reapply

- #26/#32 (`a4cae19`, CI #179): standalone held-file Authenticode verifier with exact-zero trust result/exact SHA-256 leaf pin. Rejects non-disk, directory/reparse and differing kernel-resolved final path. Real Windows tamper/signer/lock/replacement/junction/symlink checks passed. Primitive only; no production runtime admission.
- PR inventory found #11 guards absent: #33 selectively adds strong persisted ETag/date If-Range, changed resource/range/body rejection, bounded Retry-After, unbuffered short-write/disk-full/quota handling, identity-safe URL refresh with scheduler pause and dynamic-split requested-end validation. 21 focused engine tests; old workflows not reapplied.
- #2 confirmations selected/hardened in #33, no version bump: default cancel focus, refusal on cancel/Escape/external close, busy guards, frozen item snapshots, editing shortcuts fixed, visible pause errors. Node tests execute real helpers/handlers with simulated DOM; WebView2 uses real DOM with destructive POSTs intercepted. Synthetic cancel events are not physical-keyboard certification.
- Concurrent restart defect reproduced: old writer was removed before cleanup finished; another request could reset early. Caller cancellation could interrupt cleanup and still commit reset. Retain shared task, cancel once, shield cleanup, propagate caller cancellation, preserve partial state paused. Three real asyncio/temporary-file tests include completed-file preservation; #189 onward validate.
- Build-only license/payload collectors preserve actual texts/file hashes, both CArchive/PYZs and standard-library ZIPs. Original project LICENSE preserved. Proxy_tools 0.1.0 module matched upstream db43f1e35d4f90a65c5a4d56d9e9af88212ec6e6; authentic missing BSD text supplemented only for exact bytes, MIT/BSD conflict retained. Pystray LGPLv3/certifi MPL-2.0 obligations remain under review.
- #187 upgraded old Python 3.12.10/OpenSSL 3.0.16 to reviewed 3.13.16/3.5.9. Correct semantic OpenSSL comparison; old legacy-tuple error fixed. No Rapido exploitability claim from version ranges alone. Pytest internals excluded and actual archive names checked.
- #190/#191: `packaging/constraints-windows-build.txt` pins 41 reviewed build versions (incl pip), applied to normal/build constraints, pip check and advisory gate. Gate rejects drift/missing/unknown packages before queries, active advisories, yanks, invalid/unknown responses or invalid withdrawal timestamps; bounded retries. Snapshot is dated registry evidence, not authenticity/native coverage/hash-locked install/byte reproducibility. Isolated tools not listed and later Selenium smoke dependencies remain outside this matrix.
- SDK `Microsoft.Web.WebView2 1.0.3856.49` fetched from official NuGet; all five SDK DLLs in #187/#190 match package entries. Original LICENSE/NOTICE plus exact package/native/text hashes/provenance saved in packaging/licenses. Collector checks carrier pywebview 6.2.1 + all five binaries + both texts before copying; mismatch stops build. WebBrowserInterop files and separate system WebView2 runtime are outside this SDK match. No legal/source-obligation verdict.

Sources: https://docs.pypi.org/api/json/ ; https://pip.pypa.io/en/stable/user_guide/ ; https://www.python.org/downloads/release/python-31316/ ; https://openssl-library.org/news/vulnerabilities-3.0/ . SDK/proxy immutable provenance URLs are in their packaging/licenses folders.

## Remaining priorities / real gates

1. Finish exact runtime/native vulnerability/attribution/source/replacement/license review: LGPL/MPL, proxy MIT/BSD discrepancy, embedded codecs and platform runtimes. Collection, pins and empty registry lists are not compliance/security clearance.
2. Provenance: repo LICENSE says Samuel Tuil, installer publisher Samuel Bentouza. Preserve existing rights; no authority to invent ownership or claim IDM similarity clearance.
3. #26 requires independently protected production policy/installation, signer/version lifecycle, enforced browser selection and PyInstaller dependency protection before admission. No production signer/managed anchor supplied. No claim against injection, mapped writers or all ancestor races; keep issue open.
4. Clean Windows 10/11 VM matrix plus Chrome/Edge/Firefox private/cookie/absent-host/restart/upgrade/manual capture/error/keyboard paths. Do not use user's PC or substitute Server CI.
5. Defender, distinct beta version, repair/rollback and integration review before distribution. #8/#9 nonessential features deferred. No beta approved. Prior 5–10 effective-day estimate is conditional, excludes full #26 and external certificate/VM/provenance delays; not a delivery promise.

## Efficient tools/restart

Relevant map: engine.py/ytworker.py downloads; app.py/local_auth.py/trusted_api.py API; desktop.py/webview_auth.py UI; native_host.py/native_pipe.py/windows_peer.py/native_launcher.py IPC; native_registration.py/packaging/rapido.iss lifecycle; extension/background.js browser.
Local venv `/workspace/scratch/a15d48cb1e30/rapido-test-venv/bin/python` is Python 3.12 (not Windows 3.13). Latest targeted advisory/license/payload/release tests: 33 passed +12 subtests; actual local PyPI gate 41/41. PyInstaller/pefile/socksio installed locally only for analysis/environment; no production req change for these.
Git CLI lacks write credentials: GitHub Git-data tree/commit with correct parent, update_ref expected_sha/force=false, verify remote SHA. Fetch, compare staged content to FETCH_HEAD, soft-reset only if identical. Never overwrite concurrent work.
Only `.github/workflows/windows.yml`: this work branch has no push trigger, PR build read-only. Reviewed workflow releases only on explicit publication-tag push plus build success; no deploy. Guards are NOT on main, which still has historical auto-release. Any future authorized integration must preserve tag-only guard before running main; none authorized now.
