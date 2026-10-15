# Rapido — restart checkpoint

Updated 2026-10-15 (Claude). Latest validated code: 5d7659f, CI #206. Start here; do not repeat repository overview or completed PR reconciliation.

## Goal and authority

First stable Windows beta, essential corrections only. Branch `work/beta-engine-guards-20261015`, draft PR #33 targets draft PR #32's `work/security-26-followup-20261015` (dependent on #29).
Allowed: ordinary dedicated-branch pushes, draft PR updates, nonpublishing Actions. Forbidden: main edits, force-push, merges, publication tags/releases/deployments, tests on user's PC. Verify workflow before each push. One focused task; targeted tests first; preserve security checks. #30 reconciliation complete; #3/#26/#28 remain open.
Main last verified `18e0997ed0e09ed73d3723faef0904f2c5964af0`; check again before changes.

## Completed focus — Chromium cmd.exe relay in launcher admission (Claude, 5d7659f)

Windows 10 22H2 VM (Edge 155) diagnosis: extension saw downloads (capture on, mp4 configured, 0 cookies) but `capabilities` returned only `["ping"]`; passive process watch showed `msedge.exe -> cmd.exe /d /s /c "...RapidoNativeHost.exe" chrome-extension://<id>/ --parent-window=0 -> bootloader -> host`. `trusted_launcher` required a browser as direct parent, so IPC failed and every Edge download stayed in Edge (fail-closed). Earlier Rapido windows came from the clipboard watcher, not interception. Video button/menu failure is the intentional S3 disable (`captureVideo`), but its UI says "Rapido n'est pas lancé" (defect, not fixed). Fix: admit exactly one System32 `cmd.exe` (CSIDL_SYSTEM, not %ComSpec%) between helper and a recognized Chromium browser, same SID/creation/link checks; refuse second relay, non-browser/Firefox/desktop/helper above it, copied cmd, unknown System32. Shell command line not inspected (#26 residual). 4 tests (+subtests incl. real System32). [CI #206](https://github.com/shimon3/rapido/actions/runs/38784141121) SUCCESS: 240 passed /5 skipped /136 subtests; artifact `11996883975` digest `669209f4b0fbd8c3d67f6011dfc0f2b368d3e3ba9b971cf1c8395dbe2ab479c8`. VM retest pending (owner installs). Concurrent doc commit 9e8904d (`docs/windows-10-vm-verification-20261015.md`) fast-forwarded, untouched.

## Owner decision — beta without full #26 (2026-10-15)

Owner chose: beta 1.3.0-beta.1 ships without full #26; #26 stays open. Added `docs/beta-release-notes.md` (draft, unpublished: limits incl. same-user compromise, unsigned exe/SmartScreen, DPAPI history not readable by older versions, Server 2025-only automated tests, dev extensions). Release body (still tag-only) prepends a beta warning when prerelease. Readiness table and threat model record the decision. A personal #26 preparation document for the owner was created as a Claude Doc (decisions, purchases, steps 1-9, VM access options, resolution criteria, checklist). [CI #204](https://github.com/shimon3/rapido/actions/runs/38724218566) SUCCESS on 08fa540: 236 passed /5 skipped /126 subtests; release skipped. Observation: the self-test step (passed, `ok: true`) logged an asyncio proactor `ConnectionResetError` [WinError 10054] traceback for the first time; absent from #197–#203; #204 changed only docs, tests and the tag-only release text, so cause not identified (possibly remote/network). Watch on next runs. Next #26 steps doable without purchase (await owner go): CI browser-policy test, signing inventory, unsigned-build marking, verifier refusal rules.

## Completed focus — distinct beta version 1.3.0-beta.1 (Claude, 1c07ac2)

Owner chose `1.3.0-beta.1`. Single source `rapido_version.py`: beta N -> numeric X.Y.Z.N, final -> X.Y.Z.100 (final newer than its betas). engine.VERSION, exe version resource (numeric filevers, text ProductVersion), installer (VersionInfoVersion numeric via /DAppFileVersion, product text version), Chromium manifest `version` 1.3.0.1 + `version_name` (Firefox build drops it), update check (remote stays final-only via /releases/latest). Workflow: passes numeric file version; release job (still tag-only, unchanged condition) would mark a beta as prerelease and never latest. Rights holder change validated by [CI #202](https://github.com/shimon3/rapido/actions/runs/38722272069) (230 passed). [CI #203](https://github.com/shimon3/rapido/actions/runs/38722975650) SUCCESS on 1c07ac2: 236 passed /5 skipped /126 subtests /1 warning; installer built as Rapido-Setup-1.3.0-beta.1.exe with /DAppFileVersion=1.3.0.1; install/uninstall and portable coexistence passed; release skipped. No tag/release created.

Pending owner decisions: Windows 10/11 VM location, legal questions (Microsoft runtimes, proxy_tools, pystray LGPL).

## Completed focus — cffi libffi notice, WebBrowserInterop provenance, rights holder (Claude, e6f6ccd + next)

cffi 2.1.1: shipped `_cffi_backend` (21b7160d…be8d) = official cp313 win_amd64 wheel; imports no libffi DLL; Windows x64 setup.py compiles bundled `src/c/libffi_x86_x64` (identical to upstream tag v2.1.1 commit fd33e770). Verbatim leading MIT notices of the 6 compiled files shipped in `packaging/licenses/cffi-2.1.1/LIBFFI-NOTICES.txt`. pywebview WebBrowserInterop.x64/x86.dll byte-identical to binaries committed at pywebview tag 6.2.1 (2fc63cd6), sources `interop/mshtml` under repo BSD-3; build from that source not reproduced. [CI #201](https://github.com/shimon3/rapido/actions/runs/38721595000) SUCCESS on e6f6ccd: 230 passed /5 skipped /120 subtests; collector OK; release skipped.

Rights holder: owner confirmed on 2026-10-15 that the legal name is **Samuel Bentouza**. LICENSE changed from "Samuel Tuil" to "Samuel Bentouza"; exe LegalCopyright now "Copyright (c) 2026 Samuel Bentouza. MIT License."; installer AppPublisher already Bentouza. Validation: CI on the commit following e6f6ccd (see git log / Actions).

Remaining licence items needing owner/legal input: Microsoft runtime redistribution terms, proxy_tools MIT/BSD, LGPL relinking adequacy.

## Completed focus — pydantic_core Rust crate notices (Claude, 6f1f7cd)

Official sdist (SHA-256 e50d7b94…6e09) `Cargo.lock` (ac24753c…452d) lists 99 crates.io packages; each `.crate` downloaded from static.crates.io matched its lockfile checksum. Top-level LICENSE/COPYING/NOTICE/COPYRIGHT/UNLICENSE files (171, 54 unique, LF-normalized) stored in `packaging/licenses/pydantic_core-2.50.1/texts/<sha256>.txt` with `crates.json` index (declared licenses) and NOTICE.md. Shipped `.pyd` = official cp313 win_amd64 wheel (6c320aa8…3f7c). Collector requires module hash, self-certifying text names and exact index/text set equality, else build stops. Superset (build-only/other-platform crates); r-efi 5.2.0 and wit-bindgen-rt 0.39.0 have no license file (UEFI/wasm only). Wheel-from-this-lockfile and dual-license choice not established. [CI #200](https://github.com/shimon3/rapido/actions/runs/38720604527) SUCCESS: 230 passed /5 skipped /120 subtests /1 warning; signatures 15 passed; collector OK; release skipped.

Remaining licence items: cffi static libffi notice, WebBrowserInterop.dll provenance, Microsoft runtime redistribution terms, proxy_tools MIT/BSD, Tuil/Bentouza ownership, LGPL relinking adequacy.

## Completed focus — native runtime notices (Claude, c4b6442)

Artifact #198 (`11963273495`, ZIP SHA-256 40280d25…a369 matches GitHub) downloaded as data and inspected without execution: pystray/certifi notices present. Native inventory = 71 CPython Windows-build files + 19 package natives. Python 3.13.16 LICENSE.txt covers PSF, Microsoft Distributable Code, bzip2, libffi, OpenSSL, Tcl/Tk only. Added `packaging/licenses/cpython-3.13.16-windows/`: verbatim `Doc/license.rst` (expat, libmpdec, zlib, mimalloc…) and HACL* MIT header from commit cbc944f4 (tag v3.13.16), plus external versions from `PCbuild/get_externals.bat` and verified cpython-source-deps tag SHAs; SQLite/xz liblzma public domain noted. Copied to `third-party/python/…` only when interpreter == 3.13.16, else build stops. Pillow 12.3.0: 7 shipped `.pyd` byte-identical to the official PyPI cp313 win_amd64 wheel; notice + FreeType FTL credit (1996-2026, from VER-2-14-3 freetype.h) shipped and added to README. [CI #199](https://github.com/shimon3/rapido/actions/runs/38719557821) SUCCESS on c4b6442: 229 passed (227 + 2 new tests) /5 skipped /120 subtests /1 warning; signatures 15 passed; collector OK; release skipped. Artifact #199 not independently inspected.

Still open: Rust crates statically linked in pydantic_core (no notice), Microsoft VC runtime/UCRT/api-ms-win redistribution terms, cffi's static libffi (only covered indirectly by Python's notice), WebBrowserInterop.dll provenance, proxy_tools MIT/BSD, Tuil/Bentouza ownership, LGPL relinking adequacy. No compliance verdict.

## Completed focus — LGPL/MPL source notices (Claude, e890163)

pystray 0.19.5 (LGPLv3, wheel only on PyPI) and certifi 2026.7.22 (MPL-2.0): every wheel module file compared byte-for-byte (LF) with upstream tagged commits pystray `1907f8681d6d421517c63d94f425f9cdd74d0034` (tag v0.19.5) and certifi `5379b709be8a8595803a7bd907f87e302fc6ae1d` (tag 2026.07.22): 13/13 and 7/7 identical. Wheel already ships COPYING (GPLv3) + COPYING.LGPL; certifi's LICENSE only links to MPL, so verbatim MPL-2.0 text (mozilla.org, SHA-256 3f3d9e00…9d04) added. New `packaging/licenses/{pystray-0.19.5,certifi-2026.7.22}/SOURCE.md` give exact source URLs/hashes and pystray replacement path (public Rapido source + pinned constraints + workflow rebuild). Collector copies them into `third-party/packages/<pkg>/…` only when every installed source file matches the reviewed hashes; other version/modified source → `source-notice-identity-unverified` and build stops. Two new tests. No local tests run (user PC forbidden); validation = [CI #198](https://github.com/shimon3/rapido/actions/runs/38718058955) SUCCESS on e890163: 227 passed (225 + 2 new) /5 signed-fixture skips /120 subtests /1 warning; signatures 15 passed; collector 41 distributions with no source-notice stop on the real Windows install; advisory gate 41/41; packaged lifecycle steps passed; release job skipped. Artifact #198 not downloaded or independently inspected. Not a compliance verdict: LGPLv3 §4 relinking adequacy for PyInstaller bytecode, proxy_tools MIT/BSD, native/codec/runtime attributions and provenance (Tuil/Bentouza) remain open.

#26 split recorded in `docs/windows-managed-integrity-contract.md` ("Realisable now vs absent external prerequisites"). #26 open.

Claude environment: clone in session scratch folder, `core.longpaths=true` required. Git CLI push works via gh credentials (ordinary push, no force).

## Completed focus — native registration ownership

Reproduced: non-object manifest JSON raised AttributeError/TypeError during ownership checks; duplicate keys/non-JSON numbers/oversized descriptions could be accepted; a foreign manifest or registry owner introduced after preflight could be adopted/overwritten. `native_registration.py` now reads regular manifests with a 16-KiB bound, rejects invalid/ambiguous/non-object/deep/invalid-UTF8 JSON and preserves such files during uninstall while continuing other cleanup.

Registration stages all manifest files, then revalidates all manifests and registry owners before its first registry write. Tests inject foreign changes after preflight and assert rejection without registry writes. This is best-effort revalidation, NOT an atomic transaction or a same-user trust anchor: changes after the final check and partial registry-write failures remain outside this guarantee. Own newly staged files can remain after failure for repair/uninstall; no risky rollback deletes potentially replaced files.

Local focused: 28 passed /7 Windows-fixture skips /18 subtests; full Linux 194 passed /36 Windows-fixture skips /116 subtests /1 existing warning. Real Windows registry test now also corrupts a Chrome manifest with JSON null, preserves it, completes Firefox cleanup and preserves a foreign Edge owner under a unique test-only host name. CI #197 SUCCESS on d882f644ef195a8ad2f2a42da0a53946b5e86c43: 225 passed /5 signed-fixture skips /120 subtests /1 warning; real registry cleanup, packaged lifecycle and Firefox 157.0.1 passed. Release skipped. User chose a pause/handoff after this validated step; licences have not been started in this segment. Resume from docs/claude-handoff-20261015.md. Workflow reviewed unchanged: one workflow, PR build read-only, release requires explicit tag push, no deployment. Main SHA checked unchanged.

## Completed focus — native launcher paths and Firefox

Shared `native_paths.has_linked_component` now applies registration's best-effort symlink/junction policy to launcher admission: helper, desktop, recognized browser image and Firefox manifest, including ancestors. Capture refusal occurs before pipe transfer. Actual Windows junction fixtures and real known-folder discovery pass. No runtime attestation, independent policy or race-free guarantee; #26 stays open.

The separate, unshipped Firefox adapter uses the original background and a random 192-bit loopback control path. Expected phases report once; unknown/replayed/oversized/invalid reports fail. Fallback starts only after the native record is checked and test registration removed. Actual native prepare/abort, automatic transfer and absent-host browser download remain mandatory. No privileged WebDriver DOM commands, remote-system-access switch or browser security preference downgrade.

Diagnostics/restart facts: #192 exposed Firefox's privileged-context DOM rejection; #193/#194 then found an accidentally removed `Path` import used by `_folder`. New regression first reproduced NameError, then passed after restoration; Windows discovery now runs without mocking it. #195 passed all tests and Firefox **156.0.1**, not 157.0.1. #196 separately passed **157.0.1** using Mozilla's official installer, fixed SHA-512 and valid Mozilla Authenticode, with installed/WebDriver version checks. Installer runs only on GitHub-hosted Windows; no allowlist exception. Browser fixture is not shipped or part of the 41-package inventory. Mozilla source/installer provenance is linked in `packaging/firefox-ci-fixture.json` and https://firefox-source-docs.mozilla.org/browser/installer/windows/installer/FullConfig.html .

Evidence: `docs/native-launcher-validation-20261015.json`. Final local full suite: 190 passed /36 Windows-fixture skips /106 subtests /1 existing warning; launcher/registration/Firefox targeted: 28 passed /7 skips /3 subtests. Browser/release checks after fixture pin: 9 passed /11 subtests. Workflows checked before pushes; publication remains explicit-tag-only on this branch.

## Latest validated code — CI #197 SUCCESS

`d882f644ef195a8ad2f2a42da0a53946b5e86c43`:
https://github.com/shimon3/rapido/actions/runs/38715835112

- 225 general regression tests passed, 5 signed-fixture skips after separate execution, 120 subtests, 1 warning.
- Dedicated signature execution: 15 passed/no skips — 9 policy/unit tests, 1 real unsigned-file test, 5 real signed-PE fixture tests. Counts overlap general suite; never call all 15 real signed fixtures or sum as unique tests.
- Python 3.13.16/OpenSSL 3.5.9 baseline and pip check passed. All 41 exact installed versions/PyPI responses passed the new gate; no active advisory or yank returned then. Not complete vulnerability coverage.
- Both actual WebView2 confirmation probes, desktop/native compilation, real-window engine/yt-dlp test, native protocol, installer/portable coexistence and real Firefox 157.0.1 passed. Build token Contents:read; release skipped.
- Runner Windows Server 2025, not Windows 10/11 certification. Immediate PowerShell exits after failed pip/Selenium installs prevent masking by later commands.

A documentation-only checkpoint follows with [skip ci]; do not claim that documentation HEAD itself ran CI. Code/tests/workflow identical to validated d882f64. Future authorized integration needs exact-head/integration checks.

## Latest independently inspected artifact — #190

Artifact `11954004962`, code `b6a5740`, CI run `38696191089`. Archive digest matched GitHub:
`46713a203094f27e1b5600358701df2d056c25d9bca75c7092612594bd4929fc`.
154 payload file hashes/exact membership, 55 embedded native-host binary hashes, 117 package license-text hashes, Python license and unchanged project LICENSE checked. 41 versions match constraints; embedded advisory report has 41 verified responses. Five SDK DLLs and both original SDK text hashes checked; no pytest/_pytest module names. Later ZIPs, including #195/#196/#197, were not independently downloaded/inspected; do not attach #190 hashes to them.

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

1. Finish exact runtime/native vulnerability/attribution/source/replacement/license review: LGPL/MPL notices now shipped (e890163) but legal adequacy unreviewed; proxy MIT/BSD discrepancy, embedded codecs and platform runtimes. Collection, pins and empty registry lists are not compliance/security clearance.
2. Provenance: rights holder Samuel Bentouza confirmed by owner and aligned (LICENSE, installer, version resource). No IDM similarity clearance claimed.
3. #26 requires independently protected production policy/installation, signer/version lifecycle, enforced browser selection and PyInstaller dependency protection before admission. No production signer/managed anchor supplied. No claim against injection, mapped writers or all ancestor races; keep issue open.
4. Clean Windows 10/11 VM matrix plus Chrome/Edge/Firefox private/cookie/absent-host/restart/upgrade/manual capture/error/keyboard paths. Do not use user's PC or substitute Server CI.
5. Defender, distinct beta version, repair/rollback and integration review before distribution. #8/#9 nonessential features deferred. No beta approved. Prior 5–10 effective-day estimate is conditional, excludes full #26 and external certificate/VM/provenance delays; not a delivery promise.

## Efficient tools/restart

Relevant map: engine.py/ytworker.py downloads; app.py/local_auth.py/trusted_api.py API; desktop.py/webview_auth.py UI; native_host.py/native_pipe.py/windows_peer.py/native_launcher.py IPC; native_registration.py/packaging/rapido.iss lifecycle; extension/background.js browser.
Local venv `/workspace/scratch/a15d48cb1e30/rapido-test-venv/bin/python` is Python 3.12 (not Windows 3.13). Latest targeted advisory/license/payload/release tests: 33 passed +12 subtests; actual local PyPI gate 41/41. PyInstaller/pefile/socksio installed locally only for analysis/environment; no production req change for these.
Git-data argument map: create_tree(repository_full_name, base_tree_sha, tree_elements); create_commit(repository_full_name, tree_sha, parent_sha, message); update_ref(repository_full_name, branch_name, sha, expected_sha, force=false). fetch_pr(repo_full_name, pr_number) returns structuredContent.pull_request; job logs are structuredContent.content. Filter outputs; do not print full PR diffs/logs.
Git CLI lacks write credentials: GitHub Git-data tree/commit with correct parent, update_ref expected_sha/force=false, verify remote SHA. Fetch, compare staged content to FETCH_HEAD, soft-reset only if identical. Never overwrite concurrent work.
Only `.github/workflows/windows.yml`: this work branch has no push trigger, PR build read-only. Reviewed workflow releases only on explicit publication-tag push plus build success; no deploy. Guards are NOT on main, which still has historical auto-release. Any future authorized integration must preserve tag-only guard before running main; none authorized now.
