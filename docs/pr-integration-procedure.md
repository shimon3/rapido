# PR #34 / #35 integration procedure

Checked from the Git branches on 2026-10-18. **Nothing has been merged and
`main` is unchanged.** Merging needs the owner's explicit authorization.

## Actual structure

- PR #35 (`work/release-compliance-gates-20261018`) has base
  `audit/pr33-windows-stability-20261018`, which is PR #34's head. PR #34's
  head is an ancestor of PR #35's head. The order **#34, then #35** is confirmed.
- PR #34 has base `work/beta-engine-guards-20261015` (PR #33), not `main`.
  The full stack down to `main` is:
  `#6 → #7 → #10 → #17 → #18 → #19 → #20 → #21 → #22 → #23 → #24 → #25 → #27 → #29 → #32 → #33 → #34 → #35`.
- `main` is an ancestor of PR #35. PR #35 is 214 commits ahead of `main`. PRs
  #12–#16 (based on #10) are already contained in that stack.
- PR #36 (MSIX research, draft) is based on an older head of PR #35. It is
  1 commit ahead and 14+ commits behind it. Rebase it later, and do not merge
  it for the beta.
- GitHub reports every stacked PR as `MERGEABLE`.

## Open PRs **not** contained in the stack

| PR | Content | Contained in #35? | Recommendation |
| --- | --- | --- | --- |
| #11 engine guards | `engine.py` corrections | Reworked version present (`tests/test_engine_five_guards.py`); 10 original commits absent by patch identity | Compare the diff, then close as superseded if nothing is missing |
| #2 dialogs 1.2.3 | themed confirmations | `tests/test_dialog_behavior.py` present | Compare, then close as superseded |
| #5 cookie fail-closed | interim S3 guard | Superseded by native cookie guard tests; its own test file absent | Close as superseded after review |
| #9 update notifications | notification groundwork | Replaced by `docs/update-security-contract.md` and the bounded checker | Close as superseded after review |
| #4 S2/S3 design doc | `docs/security-s2-s3.md` | Absent | Merge separately or archive (documentation only) |
| #8 FR/EN/HE language | `tests/test_language.py`, installer language | **Absent**: the beta has no in-app language selector from this PR | Not needed for the beta; rebase on `main` after the stack |

All of these modify `.github/workflows/windows.yml`. Expect conflicts if they
are merged after the stack.

## Recommended procedure (reproducible)

1. Freeze PR #35 at the commit whose CI is green and which the private-beta
   validation used. Record the SHA in `docs/beta-publication-checklist.md`.
2. Review PR #34 (7 commits on top of #33), then PR #35 (commits on top of #34).
3. **Option 1 (recommended):** after approval, open one integration PR
   `work/release-compliance-gates-20261018 → main` with a merge commit (no
   squash), so the tested SHAs stay in history. Run CI on it. Then close
   #6–#34 as "merged via the integration PR", with a link.
   **Option 2:** merge the stack bottom-up (#6 first) with merge commits, and
   re-run CI each time GitHub retargets the next PR to `main`. This takes about
   17 merges and 17 CI runs.
4. After the merge, check that `main` equals the tested tree:
   `git diff <tested-sha> origin/main --stat` must be empty.
5. Handle the side PRs from the table above.

Nothing in this procedure creates a tag or a release.
