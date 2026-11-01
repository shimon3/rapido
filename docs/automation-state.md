# Rapido 1.3.0-beta.2 automation state

Last updated: 2026-10-27

## Windows 10 follow-up, 2026-11-01

- Owner authorized correction branch: `automation/rapido-beta2-webview-20261101`,
  based on exact frozen candidate `105dd961df203e52bbbf1b3e10f1cd16cee1316d`.
- Latest unchanged-branch Windows CI run `41279231023` succeeded: 431 tests,
  6 skips, 271 subtests; release skipped. This is Windows Server 2025 evidence.
- Instrumented Python 3.13.16 / pywebview 6.2.1 baseline on Windows 10 detected
  runtime 156.0.4314.50. Initialization succeeds, but GPU children exit with
  STATUS_ACCESS_DENIED (0xc0000022), renderer launch fails (49), and browser
  exits. A minimal HTTP page receives a backend request and still fails.
  Software rendering reproduces the failure. Current executor token is
  restricted; independent DPAPI probe fails with Windows error 2. These are
  environmental blockers, not evidence of a repaired graphical startup.
- Focused corrections: stop the self-test before JavaScript evaluation when
  the loaded event is missing; use one persistent, framed stdio host session
  for the dependent Native Messaging checks instead of seven process launches.
  Keep the existing 8-second per-exchange deadline and peer/security policy.
- Regression attempt 1 found a cleanup error on a timed-out blocked writer.
  Attempt 2 preserves the original timeout while reaping its owned child;
  focused suite passed (18 passed, 1 skipped). No third correction attempt.
- Full source suite rerun: 404 passed, the same 23 failed, 9 skipped,
  7 deselected, 265 subtests. No new failure introduced. Build run 41293695793
  on 7ef43c1 is in progress at this checkpoint.
- Added a fail-fast 20-cycle compiled GUI/Native Messaging check to Windows CI;
  every cycle requires the real loaded main page, authenticated WebView API,
  prepare/abort/commit, normal exit and released port. Its JSON report records
  the OS and executable digest; Server 2025 results do not count as Windows 10.
- Run 41293695793 succeeded with 437 passed, 6 skipped, 273 subtests, real GUI,
  authenticated native handoff, installer lifecycle, portable coexistence and
  Firefox. Run 41294030093 is executing the 20-cycle campaign on 80b62fc.
- Final diff review preserves desktop.py's original CRLF bytes through a Git
  blob upload; no further Python behavior changed. The resulting source commit
  must receive its own build and 20-cycle evidence before it is called tested.
- Run 41294030093 passed 13 full cycles and failed cycle 14; its initial runner
  did not preserve the failed selftest JSON. Evidence-collection correction 1:
  print the failed row and always upload startup JSON/console logs. Do not
  call this a product root cause or a successful 20-cycle campaign. Run
  41295196912 on the CRLF-only follow-up is already in progress, not restarted.
- Confirmed timeout cleanup mechanism: a helper descendant retaining stdout
  made a 0.2-second request take 2.207 seconds after only the launcher was killed.
  Add a per-session Windows KILL_ON_JOB_CLOSE job, distinct from other workers;
  close that owned job before draining streams on timeout. The descendant
  regression failed before the fix and passed after it. Focused suite now
  19 passed, 1 skipped. This fixes bounded cleanup; it does not prove the root
  cause of the historical eight-second authenticated capture_prepare timeout.
- Full local suite rerun for this final lifetime change is in progress.
- Evidence upload initially preceded the distributable upload and exposed a
  release-policy assertion that selects the first upload block (run 41295295262).
  Preserve the unchanged security assertion: move diagnostics upload after
  the distributable upload, still guarded by always(). This retains failed
  cycle logs without changing signing or publication policy. Attempt 1.
  Previous local suite: 398 passed, 23 failed, 9 skipped, 7 deselected; 19 failures
  depend on unavailable DPAPI, four require absent yt-dlp. No gate weakened.
- The historical portable capture_prepare timeout is NOT declared fixed:
  persistent framing and fail-closed behavior pass with the exact old helper,
  but authenticated prepare/abort/commit and 20 graphical starts of the rebuilt
  candidate on Windows 10 remain required. No release or merge authorized.

## Identity

- Repository: `shimon3/rapido`
- Dedicated branch: `automation/rapido-beta2-20261027`
- Reference branch: `public/1.3.0-beta.2`
- Reference commit: `5e08c9501492ea1c4fb8b0bc4cccf8940b1b5624`
- Persistent GitHub log: issue #37
- Local isolated clone: `C:\Users\samue\Downloads\rapido-auto-20261027`

## Reference baseline

- GitHub Actions run `39929795694` succeeded on reference commit `5e08c95`.
- Regression suite: 430 passed, 6 skipped, 1 warning, 271 subtests passed.
- Isolated Authenticode fixtures: 15 passed, 39 subtests passed.
- Packaging, graphical self-test, native messaging, installer lifecycle,
  installed/portable coexistence, real Firefox handoff, licence evidence,
  SHA-256 generation and non-publishing artifact upload succeeded.

## Current correction

- Confirmed on 2026-10-27: `setuptools==84.0.0` is affected by
  `GHSA-xmj3-9gf7-h52w` on Windows.
- First patched version: `84.1.0`; PyPI reports it as non-yanked, MIT, with no
  active version-specific advisory at the time of review.
- Change: reviewed build constraint updated to `setuptools==84.1.0`.
- Validation attempt 1: run `40470512836` installed `84.1.0` and passed the
  Authenticode fixtures, then stopped at one stale static assertion; 430 tests
  passed, 6 were skipped, 1 failed, and 271 subtests passed.
- Confirmed cause: the test treated the dated 2026-10-23 build inventory as a
  mutable copy of the current constraints. Historical evidence must remain
  unchanged. Exact candidate versions are already checked against the fresh
  CI inventory by `check_dependency_advisories.py`.
- Validation attempt 2: run `40470899050` succeeded on commit `75d3ddb`.
- Final test counts: 431 passed, 6 skipped, 1 Starlette deprecation
  warning, and 271 subtests passed. Authenticode: 15 passed and 39 subtests.
- The fresh build inventory contained 41 reviewed distributions and the PyPI
  advisory gate verified 41/41 responses successfully.
- Packaging, graphical self-test, native messaging, installer lifecycle,
  installed/portable coexistence and real Firefox 157.0.1 handoff passed.
- Retry counter for this root cause: attempt 2 of 3 succeeded; no third attempt
  was started.

## Current unpublished candidate

- Validated source commit: `98e79211c1a02cd4981f5acb4b306af4d2359846`.
- Workflow run: `40503343084`.
- Artifact: `12734780024`,
  `UNPUBLISHED-Rapido-1.3.0-beta.2-windows`, retained until 2026-11-10.
- Artifact archive digest:
  `09ed1f1ebc67afcff418dff99c85561a4a35941a8ca584ce4dda7c5ca0fc56bf`.
- Installer SHA-256:
  `de1935d565ea20bdba3e044682a0a74f29b5d363445b3f498d63fc48883f11ae`.
- Portable ZIP SHA-256:
  `a9d01a2fd59d67905174dd89a0a77e026d3887b366ed0e6445ee633af806ca9a`.
- The release job was skipped; no release or production signature was created.

## CI reliability follow-up

- Dependabot PR #45 exposed an intermittent test failure in
  `test_sauvegarde_de_progression_ne_bloque_pas_la_boucle_si_le_fichier_est_verrouille`.
- Confirmed cause: the test monkeypatched `engine.time.sleep`, which mutates the
  process-wide standard-library `time` module. A surviving clipboard thread
  could therefore append unrelated 0.8-second sleeps to the test observation.
- The production save path already requests exactly one replacement attempt.
  The regression test now observes that explicit `attempts=1` contract without
  changing global time or running Rapido.
- Retry counter for this root cause: attempt 1 of 3 succeeded in run
  `40503343084`; 431 tests passed, 6 were skipped, 1 warning remained and 271
  subtests passed. No second attempt was started.

## Local preparation checks

- `git diff --check`: passed.
- Static workflow and dependency-pin invariants: passed.
- The repository safety wrapper created an isolated profile successfully, but
  the local Python installation has no `pytest`; no package was installed on
  the owner computer. The complete validation is delegated to GitHub Actions.
- Rapido was not installed or executed locally.

## Automation status

- Pushes to `automation/rapido-beta2-*` run the existing complete Windows
  workflow.
- Concurrency prevents simultaneous runs for the same ref.
- The guarded dispatcher is present and active on `main` with cron expression
  `17 */3 * * *` UTC. Manual run `40500457713` dispatched successful beta run
  `40500511039`. No `schedule` event had appeared yet at this checkpoint, so
  unattended periodic execution is configured but not yet empirically proven.
- Dependabot is active and has opened PRs #43 through #46. PR #45 exposed the
  flaky assertion fixed above; action-major updates remain unmerged.
- The guarded Codex workflow remains draft in PR #41 and has no activation
  variable, environment or API secret. It has made no paid API call.
- Each eligible run appends its commit, result and run URL to issue #37.
- CI artifacts remain unsigned, unpublished and retained for 14 days.

## Open tasks

1. Review the exact-candidate licence and payload evidence; CI generation and
   automated gates passed, but they are not a legal compliance verdict.
2. Prepare and execute exact-candidate Windows 10 and Windows 11 VM checklists.
3. Validate Chrome and Edge on authorized isolated profiles. Firefox 157.0.1
   passed the automated real-browser handoff, but manual UX checks remain.
4. Address the non-blocking Node 20 action-runtime and Starlette deprecation
   warnings without widening beta scope.
5. Await owner decisions for issue #26, legal review and production signing.

## Next action

Review the exact-candidate evidence, execute the Windows 10/11 and Chromium
manual gates on authorized disposable machines, and do not publish or sign
without explicit owner approval.

## Windows 10 interactive evidence correction, 2026-11-01

- Branch head verified at 208613f; run 41296361048 succeeded on Server 2025.
- Preserved local interactive-results/20261101-134029-2084 without edits:
  four recorded cycles loaded the main DOM and popup, passed native acceptance,
  but only selftest.png existed. A fifth on-disk selftest reports popup load failure.
- Root cause of absent native files is in the test: capture_public and committed
  handoff intentionally remain pending until user confirmation by default. The
  test never confirmed them and exited without waiting for completed bytes.
  Keep product confirmation semantics; confirm through the authenticated API,
  then require completion, size and SHA-256 for all three transfers.
- Confirmed cp1255 UnicodeEncodeError at desktop.py:442 when final JSON prints
  the French popup title. Emit ASCII-escaped JSON, preserve UTF-8 result files,
  and escape unsupported diagnostic characters in existing redirected streams.
- Confirmed watchdog activity after gui-stopped/finished. Explicitly stop it
  before window destruction and join its worker before CLR finalization.
  This removes a lifetime bug; no claim that all WinForms shutdown hangs are fixed.
- Popup timeout now fails before evaluate_js on an unloaded window, preserving
  the failed loaded flag rather than waiting again in JavaScript evaluation.
- Regression attempt 1: 40 passed, 1 skipped, 4 subtests locally, with DPAPI and
  real WebView2 still unavailable under CodexSandboxOffline. Full suite pending.
- Build strengthened: all 20 CI cycles require completed native transfer hashes,
  not just protocol acknowledgements. No security/signing/publication gate changed.
- Retry counters: native transfer test semantics 1/3; cp1255 output 1/3;
  watchdog shutdown 1/3. Windows 10 interactive revalidation still required.
- No merge, tag, release, production signature or Windows policy change.
