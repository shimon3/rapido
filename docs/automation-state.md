# Rapido 1.3.0-beta.2 automation state

Last updated: 2026-10-27

## Identity

- Repository: `shimon3/rapido`
- Dedicated branch: `automation/rapido-beta2-20261027`
- Reference branch: `public/1.3.0-beta.2`
- Reference commit: `5e08c9501492ea1c4fb8b0bc4cccf8940b1b5624`
- Persistent GitHub log: issue #37
- Local isolated clone: `C:\Users\samue\Downloads\rapido-auto-20261027`

## Last validated baseline

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
- Validation state: pending the complete Windows GitHub Actions workflow.
- Retry counter for this root cause: attempt 1 of 3.

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

1. Obtain a complete green CI run after the setuptools update.
2. Inspect the generated dependency, licence and payload evidence.
3. Prepare exact-candidate Windows 10 and Windows 11 VM checklists.
4. Validate Chrome, Edge and Firefox on authorized isolated profiles.
5. Consolidate stale beta.1/security wording for the beta.2 candidate.
6. Await owner decisions for issue #26, legal review and production signing.

## Next action

Commit and push the focused dependency and automation changes, then inspect the
first GitHub Actions run. Correct only confirmed failures, with at most three
attempts for a single root cause.
