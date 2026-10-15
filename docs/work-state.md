# Rapido — restart checkpoint

Updated 2026-10-15. Start here; do not repeat the repository overview or completed PR reconciliation.

## Goal, branches and authority

First stable Windows beta; essential corrections only. Branch `work/beta-engine-guards-20261015`, draft PR #33 targets draft PR #32's `work/security-26-followup-20261015` (dependent on #29).

Allowed: ordinary dedicated-branch pushes, draft PR updates, nonpublishing Actions. Forbidden: direct main changes, force-push, merges, publication tags/releases/deployments, tests on the user's PC. Check workflows before each push. One targeted task at a time; targeted tests first; preserve security checks.

Main last verified `18e0997ed0e09ed73d3723faef0904f2c5964af0`. #30 reconciliation is complete. #3/#26/#28 remain open because fixes are unmerged or acceptance gates unresolved.

## Latest validated code — CI #187 SUCCESS

Code `6ba9c229b3cfae3d106b71687553abe18c81a00f`:
https://github.com/shimon3/rapido/actions/runs/38691471314

- 190 general regression tests passed, 5 signed-fixture skips after separate execution, 105 subtests, 1 warning.
- Dedicated signature run: 15 passed, no skips — 9 policy/unit tests, 1 real unsigned-file test and 5 real signed-PE fixture tests. Previous wording implying all 15 were real signed fixtures was inaccurate; PR #32 and current report are corrected. The two executions overlap, do not sum them as unique tests.
- Desktop/native compilation, real-window self-test, installer/uninstaller, installed/portable coexistence and real Firefox all passed. Build token Contents:read; release skipped.
- Runner Windows Server 2025 is not Windows 10/11 validation.
- Python is pinned to 3.13.16; build TLS reports OpenSSL 3.5.9. Actual DLL VERSIONINFO resources in downloaded ZIP report the same. Resource strings are not publisher verification.

Final documentation-only checkpoint follows this SHA with [skip ci]. No runtime/build/test/workflow changes after validated code. Do not claim documentation HEAD itself ran CI; future authorized integration requires exact-head/integration checks.

## Actual artifact inspection

Artifact `11952756207`; archive digest matches GitHub:
`d5eb35976f535c69f2c28011048043f44e3402e8d97b0d22c724c8a30fb441f7`.

154 payload files (excluding generated third-party evidence), all file hashes and exact file membership checked. All 55 embedded native-host binary hashes independently checked from final executable bytes. No pytest/_pytest module names. 41 build-environment distributions, 115 package license texts plus Python 3.13.16 license verified; project LICENSE text unchanged after line-ending normalization. No Python312.dll remains on disk.

Durable current evidence:
- `docs/beta-payload-inspection-20261015.json`: #187 archive/asset hashes, module/native candidates and unmatched native list.
- `docs/beta-build-inventory-20261015.json`: complete #187 observed versions/license evidence. Includes build/test tools, not all assumed shipped.
- `docs/beta-native-version-resources-20261015.json`: actual on-disk native hashes and PE resource strings, method/provenance explicit.
- `docs/beta-readiness-20261015.md`: detailed review, remaining gates/difficulty/conditional effort plan. Old `beta-artifact-verification-20261015.json` concerns #183 only.

Full module/native payload manifest is `third-party/payload.json` inside #187's artifact. Module ownership candidates match exact installed RECORD names (not bytecode identity); native candidates match size/SHA-256. Unknown/ambiguous entries remain explicit. This is not runtime admission or license/security clearance.

## Completed corrections — do not reapply

1. #26/PR #32 (`a4cae19`, CI #179): held-file Authenticode verifier rejects non-disk/directory/reparse inputs and differing kernel-resolved final path before verification/admission; exact SHA-256 leaf pin, exact-zero trust result, held handle through caller use, cleanup. Real Windows signed, unsigned, wrong signer, tamper, replacement, junction and symlink tests passed. Primitive only; no production runtime admission.
2. PR inventory exposed #11's missing engine guards; selectively restored in #33: persisted strong validators, correct If-Range/date rules, resource/range/body rejection, bounded Retry-After, ENOSPC/quota/short-write handling with unbuffered writes, identity-safe partial URL refresh with scheduler pause, dynamic split requested-end validation. 21 focused engine tests. No historical workflow reintroduced.
3. Build-only license collector adds actual texts/hashes and Python LICENSE. proxy_tools 0.1.0 sdist omits its license: exact source/module identity matched upstream `db43f1e35d4f90a65c5a4d56d9e9af88212ec6e6`; authentic BSD text/provenance supplemented only for matching module bytes. MIT metadata/BSD source conflict stays flagged. pystray LGPLv3 and certifi MPL-2.0 need obligation review; do not call all dependencies MIT.
4. New build-only payload collector parses both executables and their two standard-library ZIPs without executing bundled code. Includes file/native hashes and distribution candidates. Raw Chrome extension copy moves before evidence so installer and portable contents match. CI #184 succeeded; observed three _pytest entries led to explicit exclusion and forbidden-root check, validated in #185 and #187. Do not remove other incidental packages without checking dependency use.
5. #184 PE resources exposed Python 3.12.10 / OpenSSL 3.0.16. Official OpenSSL affected-version ranges include 3.0.16; Rapido exploitability is NOT established. Official Python 3.13.16 release includes OpenSSL 3.5.9 and Windows binaries. Updated/pinned build runtime; `scripts/check_build_runtime.py` rejects other Python or OpenSSL below 3.5.9. CI #186 initially failed because legacy OPENSSL_VERSION_INFO fields were misread; semantic version parsing plus 4 tests fixes the gate, without lowering its floor. CI #187 validates final baseline and full app flow.

Sources: https://openssl-library.org/news/vulnerabilities-3.0/ ; https://www.python.org/downloads/release/python-31211/ ; https://www.python.org/downloads/release/python-31316/ .

## Current task — critical confirmation dialogs

Selective follow-up to PR #2, without its version bump or old publishing workflow: custom async confirmations for redownload, delete/deletefile, handoff recovery and progress cancellation. Cancellation is default focus; Escape/cancel and external close refuse; re-entry cannot steal a resolver. Action items are copied before waiting and a busy guard prevents duplicate requests. Delete/Ctrl+A shortcuts do not act while editing fields. Pause/resume/cancellation errors stay visible; failed pause does not close the popup.

16 targeted dialog/release-policy/WebView auth/API auth tests and 50 subtests passed locally (1 existing warning); both generated self-test JS variants parse. New self-test drives the actual DOM and action handlers in WebView2 with destructive POSTs intercepted. Synthetic cancel events cover the Escape handler, not a physical keyboard certification. CI #188 on `24a2df9` has passed general regression, actual WebView2 main/popup confirmation probes and installer checks; full run/Firefox completion still to verify. #187 validates only the previous code.

The initial engine-only suspicion was refined by reading app.redownload: a SINGLE API request already awaits _cancel_task correctly. Real concurrent-task reproduction found the actual defect: _cancel_task popped the old writer before cleanup completed, so a second API request could delete/reset early. Another reproduction showed caller cancellation could interrupt cleanup and still commit restart. Two regression tests failed before correction; a third checks completed-file preservation.

Current backend correction retains the old task until completion, issues cancellation once, shields cleanup from caller cancellation and propagates cancelled operations instead of committing restart. Interrupted active downloads remain paused with partial state. Finished-task removal checks identity to preserve a replacement task. 35 targeted engine/restart/dialog/API tests and 42 subtests pass locally (1 existing warning). New full Windows validation pending for this engine change; do not claim #188 tested it.

## Remaining gates and next task

- Review exact runtime/native attribution, embedded library notices, LGPL/MPL/source/replacement requirements and proxy_tools MIT/BSD discrepancy. Inventory collection is done; compliance is not established. Dependency vulnerability review must cover exact observed versions/native components, not only pip names. Python pin is a reviewed baseline requiring future maintenance, not perpetual security assurance.
- Provenance/attribution: repo LICENSE says Samuel Tuil, installer publisher Samuel Bentouza. Preserve rights; no authority to invent ownership or claim IDM provenance clearance.
- #26 needs independently protected production policy/installation, signer/version lifecycle, browser host-selection enforcement and PyInstaller dependency protection before runtime admission. No production signer or managed trust anchor provided. No claim to prevent injection, mapped writers or all ancestor races. Keep issue open.
- Clean Windows 10/11 VM matrix plus Chrome/Edge/Firefox private/cookie/absent-host/restart/upgrade flows remain. No tests on user's PC; Server CI is not a substitute.
- Critical WebView2 dialogs (#2) need targeted cancel/delete/restart review; dependency/security review, Defender, distinct beta version and rollback gates remain before distribution. #8/#9 nonessential features deferred; #11 selected guards already present. No beta approved.

The report's 5–10 effective-day estimate is conditional, excludes complete #26 resolution and external signing/VM/provenance delays. Do not promise a delivery date.

## Efficient restart and tooling

Only read relevant files. engine.py/ytworker.py: downloads; app.py/local_auth.py/trusted_api.py: API; desktop.py/webview_auth.py: desktop; native_host.py/native_pipe.py/windows_peer.py/native_launcher.py: IPC; native_registration.py/packaging/rapido.iss: lifecycle; extension/background.js: browser.

Local venv `/workspace/scratch/a15d48cb1e30/rapido-test-venv/bin/python` is Python 3.12, not the new Windows runtime. 18 targeted evidence/runtime/license/extension tests plus 17 subtests passed locally. PyInstaller/pefile installed only as local analysis tools; socksio installed only for this environment's SOCKS proxy. No production requirement change for these.

Git CLI lacks write credentials. Use GitHub Git-data connector: base current tree, correct parent, update_ref with expected_sha and force=false. Verify remote SHA, fetch, compare staged content to FETCH_HEAD, then soft-reset only when identical. Never overwrite concurrent work.

Only workflow `.github/workflows/windows.yml`: branch has no push trigger; PR build read-only. Reviewed branch workflow releases only on explicit publication tag push plus successful build; no deployment step. These guards are NOT on main, which retains historical auto-release behavior. Any future authorized integration must preserve tag-only guard before running on main. No such action is authorized now.
