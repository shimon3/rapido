# Rapido 1.3.0-beta.1 — remaining publication tasks

Status date: 2026-10-18. This checklist lists **only the work still to do**.
Completed items are recorded in the CI evidence and in the documents linked
below. It does not authorize a merge, tag, release, deployment, purchase or
production signature. **Do not publish** while a blocking task of the target
track is open.

- Track P (**private beta**, unsigned, 2 to 5 named testers):
  `docs/private-beta/README.md`.
- Track S (**public beta**, signed): this checklist plus
  `docs/authenticode-signing-procedure.md`.

Latest evidence: CI run CI_RUN_PLACEHOLDER on commit COMMIT_PLACEHOLDER.

## Track P — private unsigned beta

| ID | Task and objective | Real state | Evidence | Missing | Blocking | Next owner | Validation criterion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | Freeze the candidate: one commit, one green run, one artifact | Candidate built by CI | Run summary with SHA-256 block, `SHA256SUMS.txt` | Owner downloads and archives the artifact within 14 days | Yes | Owner | Archived files match the job-summary hashes |
| P2 | Clean Windows 10 validation of that exact artifact | Earlier artifacts passed on a Windows 10 VM (CI #218, `docs/windows-10-vm-verification-20261018.md`) | Earlier report only | Run `docs/private-beta/checklist-windows.md` on the frozen artifact | Yes | Owner (machine access) | Checklist sections A–F meet the "validated for sending" rule |
| P3 | Clean Windows 11 validation of that exact artifact | Earlier artifacts passed on Windows 11 (CI #221, `docs/windows-11-pc-verification-20261018.md`) | Earlier report only | Same as P2 on Windows 11 | Yes | Owner | Same as P2 |
| P4 | At least one of Chrome, Edge and Firefox works end to end on both systems | Firefox automated in CI; Edge validated earlier; Chrome's normal install path not recorded | CI Firefox step, earlier reports | Checklist rows D1–D3 | Yes, for one browser. No, for all three | Owner | One browser passes on both systems; others recorded |
| P5 | Feedback channel ready | Issue forms and `SECURITY.md` on the work branch | `.github/ISSUE_TEMPLATE/` | GitHub reads forms only from `main`: until the owner authorizes a merge, use private messages. Enable private vulnerability reporting and create the labels `beta-privee` and `feedback` | No | Owner | A tester can report privately, and a security report never needs a public issue |
| P6 | Testers informed | Notice and guide written | `docs/private-beta/notice-securite-version-non-signee.md`, `guide-testeur.md` | Owner sends them with the hashes on a second channel | Yes | Owner | Each tester confirmed reading the notice |
| P7 | Licence gates pass on the candidate and `payload.json` is reviewed | Gates enforced by CI; FFmpeg and Deno not added by the workflow | `docs/private-beta/revue-licences-bloquantes.md` | Review `third-party/payload.json` of the frozen artifact | Yes | Owner | No unexpected component |

## Track S — public signed beta (after Track P)

| ID | Task and objective | Real state | Evidence | Missing | Blocking | Next owner | Validation criterion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | Certificate for "Samuel Bentouza", Israel | Not purchased | `docs/authenticode-options-israel.md`, `docs/authenticode-signing-procedure.md` §1 | Written confirmation from SSL.com (IV for Israel, CKA or CodeSignTool CI, total price), then the purchase | Yes | Owner | Certificate issued; SHA-256 pin recorded |
| S2 | Wire production signing in CI | Order, checks and negative cases rehearsed with disposable certificates | `scripts/rehearse_release_signing.ps1`, `signing-rehearsal.json` in the artifact | `release-signing` environment and secrets (owner), reviewed `sign` job PR (maintainer) | Yes | Owner, then maintainer | Tag build signs, verifies and records the manifest; a PR build cannot reach the secrets |
| S3 | Windows 10/11 validation of the **signed** candidate | Matrix ready | `docs/windows-validation-matrix.md`, `scripts/collect_candidate_evidence.ps1` | Execution on the owner's machines | Yes | Owner | All 20 scenarios recorded on both systems |
| S4 | Downloaded file equals the tested file | Script rehearsed in CI (identical copy accepted, planted DLL rejected) | `scripts/verify_release_candidate.ps1` | Run on the real signed candidate | Yes | Owner | Script reports a match |
| S5 | Issue #26 decision | Options written | `docs/issue-26-beta-options.md` | Owner chooses A or B and approves the residual-risk wording | Yes | Owner | Decision recorded; #26 stays open unless its criteria are proven |
| S6 | Human legal review | Technical report ready | `docs/license-obligations-report.md` (questions L1–L6) | Reviewer chosen by the owner | Yes | Owner | Written answers to L1–L6 |
| S7 | Merge the stack | Order #34 → #35 confirmed | `docs/pr-integration-procedure.md` | Review and owner authorization | Yes | Owner | `main` equals the tested tree |
| S8 | Release notes with support scope and residual risk | Draft exists | `docs/beta-release-notes.md` | Final wording after S5 | Yes | Maintainer | Owner approves |

## Proving the signed artifact is the tested one

1. After S3 passes, record the candidate:
   `verify_release_candidate.ps1 -Record -CandidateDir <tested files> -ApprovedManifest approved.json -Version 1.3.0-beta.1 -Commit <sha> -ExpectedCertificateSha256 <pin>`.
   Store `approved.json` outside the candidate folder.
2. Download the files to be published from a different machine or account.
3. Run `verify_release_candidate.ps1 -CandidateDir <download> -ApprovedManifest approved.json -ExpectedCertificateSha256 <pin> -ExpectedSubject <subject>`.
4. Publish only if it reports a match. The comparison covers the installer and
   the ZIP, every file inside the portable payload, and the Authenticode
   status, timestamp and signer pin of the installer, `Rapido.exe` and
   `RapidoNativeHost.exe`.
