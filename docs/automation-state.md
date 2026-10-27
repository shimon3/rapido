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

- Validated source commit: `75d3ddbc67f83057b176649bf36f348de6a91655`.
- Workflow run: `40470899050`.
- Artifact: `12719195364`,
  `UNPUBLISHED-Rapido-1.3.0-beta.2-windows`, retained until 2026-11-10.
- Artifact archive digest:
  `dbd5705c7b92341947e456aa57e5d1b9a3284152ed09337d9d13577b8525d684`.
- Installer SHA-256:
  `f44ef1c777f39942d9c667443b065b1421fc9836bce5b31d1f48f6b29f692e7d`.
- Portable ZIP SHA-256:
  `076c85258efb8c356e29a1351f58235554bf5f92c63331ff1f009f41150c264e`.
- The release job was skipped; no release or production signature was created.

## Local preparation checks

- `git diff --check`: passed.
- Static workflow and dependency-pin invariants: passed.
- The repository safety wrapper created an isolated profile successfully, but
  the local Python installation has no `pytest`; no package was installed on
  the owner computer. The complete validation is delegated to GitHub Actions.
- Rapido was not installed or executed locally.

## Automation configured in this branch

- Pushes to `automation/rapido-beta2-*` run the existing complete Windows
  workflow.
- Concurrency prevents simultaneous runs for the same ref.
- A prepared cron expression (`17 */3 * * *`, UTC) targets the dedicated
  branch every three hours.
- GitHub only activates scheduled workflows stored on the default branch.
  Therefore the cron is **prepared but not active** while this workflow exists
  only on the dedicated branch.
- Each eligible run appends its commit, result and run URL to issue #37.
- CI artifacts remain unsigned, unpublished and retained for 14 days.

## Open tasks

1. Review the exact-candidate licence and payload evidence; CI generation and
   automated gates passed, but they are not a legal compliance verdict.
2. Prepare and execute exact-candidate Windows 10 and Windows 11 VM checklists.
3. Validate Chrome and Edge on authorized isolated profiles. Firefox 157.0.1
   passed the automated real-browser handoff, but manual UX checks remain.
4. Consolidate stale beta.1/security wording for the beta.2 candidate.
5. Address the non-blocking Node 20 action-runtime and Starlette deprecation
   warnings without widening beta scope.
6. Await owner decisions for issue #26, legal review and production signing.

## Next action

Keep the validated source frozen. Review the exact-candidate evidence, prepare
the Windows 10/11 and Chromium manual gates, and do not publish or sign without
explicit owner approval.
