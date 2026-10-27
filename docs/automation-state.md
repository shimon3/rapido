# Rapido 1.3.0-beta.2 automation state

Last updated: 2026-10-27

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
