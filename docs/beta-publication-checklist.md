# Rapido 1.3.0-beta.2 — remaining publication tasks

Status snapshot: 2026-11-12. This checklist lists **only the work still to do**.
Completed items are recorded in the CI evidence and in the documents linked
below. It does not authorize a merge, tag, release, deployment, purchase or
production signature. **Do not publish** while a blocking task of the target
track is open.

- Track P (**private beta**, unsigned, 2 to 5 named testers):
  `docs/private-beta/README.md`.
- Track S (**public beta**, signed): this checklist plus
  `docs/authenticode-signing-procedure.md`.

Latest verified CI: [Windows run #43156904123](https://github.com/shimon3/rapido/actions/runs/43156904123)
on exact PR head `5794146456a4a49eb0378f3df72cfe3e994f6853` and CI merge
candidate `4b8b927c8c01fe94067c6b3756697a6ca28bfd0f`: success. Tests: 456
passed, 6 skipped, 2 warnings and 280 subtests passed. Signing rehearsal
(15 tests, 39 subtests), 41/41 advisory responses, installation lifecycle,
Firefox 157.0.1 handoff/fallback, portable ZIP, SHA-256 and artifact upload
passed; the release job was skipped.

Unpublished artifact `13916850742` expires 2026-11-26 04:52 UTC. Its GitHub
archive digest is `sha256:8b5024217b89e5b9f547166f82e62f0063efb212d224ec23bc9b93d467e25055`.
The original Actions summary gives installer SHA-256
`6407a94a1510e959bb9e6854bf955a31126ec1ec7b014db918212147148f6e8a` and
portable ZIP SHA-256
`2e401b9c5904f1ca9fb77fa164d0897777b3850fdf332de08efcf7c8cf9ec8b3`.
The archive has not yet been downloaded and compared against those values.

**Public beta verdict: NO-GO.** No approved production certificate/signature,
no owner-signed issue #26 decision, no exact signed-candidate Windows 10/11
manual matrix, no human licence clearance, and no review/merge authorization.
Draft [PR #51](https://github.com/shimon3/rapido/pull/51) contains the
integration work. [Firefox #52](https://github.com/shimon3/rapido/issues/52)
remains under investigation despite passing the latest run.

See the current executable handoff dossier:
[`docs/beta2-public-release-readiness-2026-11-11.md`](beta2-public-release-readiness-2026-11-11.md).
The table below may mention older evidence as **history** only; no earlier
artifact can substitute for the exact final build.


## Track P — private unsigned beta

| ID | Task and objective | Real state | Evidence | Missing | Blocking | Next owner | Validation criterion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | Freeze the candidate: one commit, one green run, one artifact | Candidate PR head `5794146`, run `43156904123`, unpublished artifact `13916850742` | [Exact-head run](https://github.com/shimon3/rapido/actions/runs/43156904123), individual SHA-256 values in this checklist and `SHA256SUMS.txt` in artifact | Owner downloads and archives the artifact before **2026-11-26**, compares installer/ZIP bytes to the two original Actions-summary hashes above, and freezes exact file set | Yes | Owner | Archived candidate bytes match independently recorded run-summary hashes |
| P2 | Clean Windows 10 validation of that exact artifact | Earlier artifacts passed on a Windows 10 VM (CI #218, `docs/windows-10-vm-verification-20261018.md`) | Earlier report only | Run `docs/private-beta/checklist-windows.md` on the frozen artifact | Yes | Owner (machine access) | Checklist sections A–F meet the "validated for sending" rule |
| P3 | Clean Windows 11 validation of that exact artifact | Earlier artifacts passed on Windows 11 (CI #221, `docs/windows-11-pc-verification-20261018.md`) | Earlier report only | Same as P2 on Windows 11 | Yes | Owner | Same as P2 |
| P4 | Chrome, Edge and Firefox work end to end on both systems | Firefox 157.0.1 automated native handoff and fallback passed in run #43156904123; issue #52 still open | [Exact-head CI](https://github.com/shimon3/rapido/actions/runs/43156904123), `docs/browser-support-plan.md` | Exact beta.2 manual rows D1–D3 on W10/W11 | Yes | Owner | All three are recorded; failures are either fixed or declared unsupported |
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
| S7 | Integrate the tested beta | PR #38 targets `public/1.3.0-beta.2`; draft PR #51 targets the automation branch, not `main` | PRs #38 and #51; issue #37 | Review beta branch ancestry and changes, obtain owner approval, then separately authorize the exact reviewed integration into `main` | Yes | Owner | The integrated tree exactly corresponds to the independently tested/signed source commit |
| S8 | Release notes with support scope and residual risk | Draft exists | `docs/beta-release-notes.md` | Final wording after S5 | Yes | Maintainer | Owner approves |

## Proving the signed artifact is the tested one

1. After S3 passes, record the candidate:
   `verify_release_candidate.ps1 -Record -CandidateDir <tested files> -ApprovedManifest approved.json -Version 1.3.0-beta.2 -Commit <sha> -ExpectedCertificateSha256 <pin>`.
   Store `approved.json` outside the candidate folder.
2. Download the files to be published from a different machine or account.
3. Run `verify_release_candidate.ps1 -CandidateDir <download> -ApprovedManifest approved.json -ExpectedCertificateSha256 <pin> -ExpectedSubject <subject>`.
4. Publish only if it reports a match. The comparison covers the installer and
   the ZIP, every file inside the portable payload, and the Authenticode
   status, timestamp and signer pin of the installer, `Rapido.exe` and
   `RapidoNativeHost.exe`.
