# Rapido — Work restart checkpoint

Updated 2026-10-15. Start here; do not repeat the repository overview or completed stack reconciliation.

## Goal and authority

First stable Windows beta; essential corrections only. Working branch `work/beta-engine-guards-20261015`, draft PR #33 targeting `work/security-26-followup-20261015` (draft PR #32, itself dependent on #29).

Allowed: ordinary dedicated-branch pushes, draft PR creation/updates and nonpublishing Actions. Forbidden: direct main changes, force-push, merges, publication tags/releases/deployments, tests on the user's PC. Verify workflow triggers before every push. Work on one focused task, targeted tests first; no security reductions to save quota.

Main last verified `18e0997ed0e09ed73d3723faef0904f2c5964af0`; verify again before changes. #30 reconciliation is complete. #3/#26/#28 remain open because fixes are unmerged or acceptance gates unresolved.

## Latest validated code and evidence

**Code `c33041ab36a68632625734f9824bb297b206217c`, CI #183 SUCCESS**:
https://github.com/shimon3/rapido/actions/runs/38685767705

- Full regression: 179 passed, 5 signed-fixture skips after dedicated execution, 88 subtests, 1 warning.
- Dedicated real Authenticode fixtures: 15 passed, no skips. Includes NTFS junction/symlink and independent-process replacement tests.
- Desktop/native builds, real-window self-test, installer lifecycle/portable coexistence, real Firefox, packaging and artifact upload passed.
- Actual build token Contents:read; release job skipped. Runner is Windows Server 2025, not proof of Windows 10/11 desktop validation.
- Artifact `11949821998` was downloaded and inspected: 394 portable entries, 46 installed-distribution records, 121 package license texts plus Python 3.12.10 LICENSE and project LICENSE. All referenced license hashes match. The archive SHA-256 matches GitHub metadata.
- `docs/beta-build-inventory-20261015.json` preserves complete observed versions/license evidence; `docs/beta-artifact-verification-20261015.json` preserves artifact hashes/inspection results. No full compliance verdict is claimed.

Documentation checkpoint `a83859e` follows this code with [skip ci]. Runtime code/tests/workflow remain identical to the validated SHA. Do not claim the documentation HEAD itself ran CI; exact-head/integration checks remain required before any future authorized merge/release.

## Completed during this session

1. #26/PR #32: held-file verifier rejects non-disk/reparse/directory input or a differing kernel-resolved final path, checked before verification/admission. Real Windows replacement/junction/symlink tests passed. CI #179 on `a4cae19` independently validates that branch. It remains a primitive, not runtime capture admission or an independent system trust anchor.
2. PR inventory revealed #11 engine guards absent from #32. PR #33 selectively carries them without old workflows: persisted ETag/Last-Modified/probe Date, correct strong If-Range, resource/range/body-size rejection, disk-full/quota/short-write abort, unbuffered writes, bounded 429/503 Retry-After. Partial URL refresh requires the same usable validator, restores metadata on refusal and pauses scheduler state while probing. Dynamic splitting validates the originally requested range while clipping writes to current segment ownership. 21 focused engine tests; Linux extended checks 40 passed/13 Windows skips.
3. Actual #181 ZIP initially had only four license texts. Added build-only `scripts/collect_license_evidence.py`, with four focused tests, package-root confinement, immutable-output protection, version/license inventory, copied-text hashes, Python license requirement and explicit compliance_verified=false. Evidence is build environment (test/build tools included), not exact shipped modules/native compliance.
4. proxy_tools 0.1.0 sdist lacks LICENSE; metadata says MIT, module header says BSD. Verified PyPI archive hash and exact normalized module match against upstream commit `db43f1e35d4f90a65c5a4d56d9e9af88212ec6e6`. Preserved authentic BSD text/provenance under `packaging/licenses/proxy_tools-0.1.0/`; supplement applies only to exact version/module hash, retaining conflict as review-required. #183 actual inventory confirms the supplement and conflict flag. pystray 0.19.5 metadata is LGPLv3; certifi 2026.7.22 metadata is MPL-2.0. Never call all dependencies MIT.

## Current targeted work — payload reconciliation

Added build-only `scripts/collect_payload_evidence.py`: lists actual executable CArchive/PYZ entries, both embedded/on-disk base_library ZIP module names, and hashes bundle files/native entries. Python distribution candidates match exact installed RECORD module names; native candidates require identical size/SHA-256. Unknown/ambiguous entries remain explicit. No DLL/code execution, absolute runner paths, integrity-policy or compliance verdict. Excludes separately generated third-party evidence from recursive file inventory. Chrome extension copy moves before evidence collection so both installer/portable payloads are covered.

CI #184 SUCCESS on `862c79dddf302f0311fdc5fe8b58454bbbc80235`: 185 regression tests passed, 5 dedicated-fixture skips, 88 subtests; 15 real signature tests passed separately. All compilation, payload evidence, installer/portable and Firefox steps passed; release skipped. Actual downloaded ZIP: all 154 payload file hashes and 121 license-text hashes checked, no missing/extra payload file, archive digest matched GitHub. Four inspected archives include both base_library ZIPs; desktop 2383 entries, host 124, host 55 native entries. See `docs/beta-payload-inspection-20261015.json` for exact hashes, candidates and unmatched native files.

The new evidence exposed three `_pytest` module entries in the desktop executable. A targeted follow-up excludes `pytest` and `_pytest` from the desktop build and rejects either root in actual archive inventory (package boundary matching). 14 local collector/license/extension tests plus 4 subtests pass. New Windows CI validation is pending; do not confuse #184 with this exclusion change. Other incidental packages remain in the payload until their actual dependency role is reviewed; no blind removal.

## Remaining blockers and next task

`docs/beta-readiness-20261015.md` is the detailed PR/primary-source license review and task/difficulty/effort plan. Current next work:

- Reconcile exact runtime/native payload with the collected build-environment inventory; review LGPL/MPL/source/replacement obligations and proxy_tools MIT/BSD discrepancy. Missing-text collection is fixed, complete compliance is not established.
- Check attribution/provenance: repository LICENSE says Samuel Tuil, installer publisher says Samuel Bentouza. Preserve existing rights; no authority to invent or rewrite ownership. No IDM similarity/provenance clearance established.
- #26 requires a concrete independently protected production policy/signer lifecycle, browser host-selection enforcement and PyInstaller dependency protection before runtime admission. No production certificate or managed trust anchor is configured. Signature checks do not prevent injection/all ancestor races/mapped writers; the issue stays open.
- Clean Windows 10/11 VM matrix and Chrome/Edge/Firefox critical/private/cookie/absent-host/restart/upgrade tests remain. Do not substitute Windows Server CI results or test on the user's PC.
- Critical WebView2 dialog paths, dependency/security review, Defender, distinct beta version/provenance and rollback gates remain before distribution. Nonessential #8/#9 features deferred; #2 dialogs need targeted review. #11's selected engine fixes are now in #33; do not reapply old workflows or merge blindly.

The report's 5–10 effective-day range is a conditional engineering estimate, not a calendar promise or a full #26 guarantee. External signing/VM/provenance prerequisites are not assumed available.

## Efficient restart/tools

Only read relevant files. Architecture: engine.py/ytworker.py (downloads), app.py/local_auth.py/trusted_api.py (API), desktop.py/webview_auth.py (desktop), native_host.py/native_pipe.py/windows_peer.py/native_launcher.py (IPC), native_registration.py/packaging/rapido.iss (lifecycle), extension/background.js (browser). Full map/reconciliation need not be repeated.

Local venv `/workspace/scratch/a15d48cb1e30/rapido-test-venv/bin/python`; Node on PATH. socksio was installed in this venv only to support this environment's configured SOCKS proxy; no production dependency change for that issue.

Local Git lacks write credentials. Use GitHub Git-data connector: tree based on current tree, commit with correct parent, create branch or update_ref with expected_sha and force=false. Verify remote HEAD; fetch, compare local index/remote content, then soft-reset local HEAD only when identical. Never overwrite concurrent work.

Only workflow is `.github/workflows/windows.yml`: this work branch has no push trigger; PR build token is read-only. On the reviewed branches release requires explicit tag push plus successful build; their PR/dispatch runs cannot publish, no deployment step. These guards are NOT yet on main: main still has its historical auto-release behavior and must not be triggered. Any future authorized integration must preserve the tag-only guard before running on main. Do not change main/tags or weaken tests. Current change is build-time payload evidence only; preserve runtime code and retain exact validation identities.
