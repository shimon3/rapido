# Rapido 1.3.0-beta.2 — public beta readiness dossier (11 November 2026)

**State: NO-GO for public distribution.** This is an evidence index and work
handoff, **not** an authorization to purchase certificates, sign binaries,
merge, publish, create a version tag, or approve licence compliance.

## Candidate and immutable CI evidence

| Item | Verified status |
| --- | --- |
| Integration draft | [PR #51](https://github.com/shimon3/rapido/pull/51), based on `automation/rapido-beta2-20261027`, **not `main`** |
| Tested source commit | `bbe3925a35b380b0a754d1b7eb0733dd4ce94947` |
| Windows Server 2025 CI | [Run #43033951242](https://github.com/shimon3/rapido/actions/runs/43033951242): **success** |
| Automated regression tests | 444 passed, 6 skipped, 2 warnings; 277 subtests passed |
| Disposable Authenticode tests | 15 passed and 39 subtests passed; **not a production signature** |
| PyPI advisory gate | 41/41 verified; human licence review remains required |
| Actual Firefox smoke | 157.0.1 native handoff and browser fallback passed in this run |
| Unpublished artifact | `UNPUBLISHED-Rapido-1.3.0-beta.2-windows`, artifact ID `13863311886`, 80,860,486 bytes, expires **2026-11-25** |
| GitHub artifact-upload digest | `fd71e46335b8bd57bf1c3a078564c8a1a1a41fcbcf4f7b950878ca2bee96c9b8` (not a substitute for the individual installer/ZIP digests) |
| Release job | Skipped by policy; publication gate remains `publishable=false` |
| Current beta branch signing | Unsigned. No approved publisher certificate or verified production signature |

Only the **exact signed candidate** can be approved for public publication. The
unsigned artifact listed above is suitable for controlled review under
`docs/private-beta/README.md` after its own prerequisites pass; it must not
be relabeled as a public release.

## Security decision (issue #26): proposed Option A, awaiting owner sign-off

**Option A** is the repository's recommended first-public-beta path:
authenticode-signed, timestamped executables and installer; independent SHA-256
checks; verified existing native IPC and origin restrictions; published residual
risk statement; manual updates. Do **not** record this as the owner's final
decision until the owner explicitly approves it.

Proposed release-notes wording, pending explicit approval:

> Rapido does not protect against a malicious program already running under
> your Windows account. An Authenticode signature identifies the published
> binary but does not prevent same-user replacement of program files, native
> messaging manifests or HKCU registrations. Only obtain Rapido from the
> official signed release; updates are manual.

Issue [#26](https://github.com/shimon3/rapido/issues/26) remains **open**
under Option A. Choosing the more restrictive Option B adds administrator-owned
installation, HKLM policy, payload coverage and separate verification; it is
not implemented in this integration candidate.

**Owner decision required:** select A or B and approve the precise residual-risk
text. The author of this checklist cannot approve on the owner's behalf.

## Production signing — tasks ready vs not done

Already prepared:
- `docs/authenticode-signing-procedure.md`
- `scripts/rehearse_release_signing.ps1`
- `scripts/verify_release_candidate.ps1`
- `docs/release-signing-and-license-gates.md`

Required actions, in order:

1. Owner obtains *written* confirmation that the intended provider issues
   the desired code-signing type to an individual in Israel and supplies a
   supported CI route, pricing and renewal/revocation details. The historic
   provider comparison is **not a current price quotation**.
2. Owner orders/receives the certificate, approves the exact publisher
   identity and stores the pin and certificate chain separately.
3. Owner creates GitHub environment `release-signing` with a required owner
   reviewer and strict tag-only access. Cloud-signing credentials go only into
   the **environment secrets**; never in source code, logs or artifacts.
4. Maintainer prepares a separate signing workflow PR; configure a protected
   `v*` tag workflow that signs `Rapido.exe` and `RapidoNativeHost.exe`
   **before** building the installer, then signs the installer, rebuilds the
   ZIP, verifies the pinned signer and RFC3161 timestamps, records the manifest,
   and keeps secrets inaccessible to PR/preview jobs.
5. Keep `publishable=false` until the above workflow, trust boundaries,
   negative cases, owner approval and manual OS tests are complete.

### Provider enquiry (draft, not sent)

Subject: Individual code signing certificate — Israel, GitHub Actions, total cost

Hello,

I am preparing a Windows application for distribution under an individual
publisher identity in Israel. Before ordering, could you please confirm in
writing:

1. Whether an individual resident in Israel is eligible for your individual
   code-signing certificate, and the accepted identity/address documentation
   (including Hebrew-language requirements);
2. Whether the certificate works with your protected cloud signing service
   for an unattended GitHub Actions Windows runner, and whether `signtool`,
   CodeSignTool or another officially supported method is required;
3. The exact annual price, any signing-operation subscription, VAT or other
   fees, and the certificate's validity period;
4. Renewal, reissue, suspension and revocation processes, and any signing
   limits or required human approval per operation.

Please do not activate a purchase from this enquiry. Thank you.

## Windows 10 and 11 acceptance (still unperformed for the signed candidate)

**Required:** a clean Windows 10 Pro 22H2 machine/VM and Windows 11 Pro
machine/VM, using the **same exact signed installer and portable archive**.
Use `docs/windows-validation-matrix.md` (20 scenarios per OS) and
`scripts/collect_candidate_evidence.ps1`; include Chrome, Edge and Firefox.
Do not treat Windows Server 2025 Actions as substitute.

- Capture OS and browser versions, WebView2, signature and SmartScreen state;
- test install/no UAC, WebView2, tray, downloads, resume, concurrent transfers;
- test browser native handoff and safe missing-host fallback;
- test upgrade, repair, uninstall, per-user registration cleanup, portable
  coexistence, no unrelated process termination;
- compare installed files and ZIP against the independent signed manifest;
- redact cookies, private URLs, download history and tickets from bug reports.

Use the unsigned `UNPUBLISHED-*` artifact **only** for restricted owner/private
testing with its own private-beta checklist; do not mark signed scenarios
successful from unsigned runs.

## Licence and supply-chain review (not yet approved)

The green pipeline verifies the **current pinned environment**, but is not
legal approval. Review `docs/license-obligations-report.md`, especially L1
through L6, and the exact candidate's `third-party/inventory.json`,
`third-party/payload.json`, original licence/source notices and Rust crate
inventory; verify there is no FFmpeg, Deno, pytest, private key or signing
fixture bundled. Obtain and retain a human written review.

Do not merge PR #50's `certifi 2026.10.23` or `pydantic-core 2.50.2`
until exact official wheel/source verification and Rust notice review complete.
The new offline audit utilities are **review aids**, not approval. Keeping
the previously reviewed pins is permitted pending advisory checks and review.

## Other tracked blockers

- [Issue #52](https://github.com/shimon3/rapido/issues/52): intermittent
  automatic Firefox handoff observed once; CI-only sanitised diagnostics and
  a regression test have landed in the draft PR. Root cause remains unproven.
- [PR #51](https://github.com/shimon3/rapido/pull/51): draft; no merge
  approval and no main branch changes.
- A release must be based on the exact reviewed/signed tree; approving a
  nonmatching earlier CI artifact is insufficient.

## Release authorization (ALL fields required before GO)

- [ ] Owner chooses security Option A or B and signs off residual risk text
- [ ] Certificate issued, publisher identity and signing pin independently verified
- [ ] Protected tag-only signing workflow and negative gates reviewed
- [ ] Installer, native host and desktop app signed; RFC3161 timestamp checked
- [ ] Clean Windows 10 and Windows 11 matrices passed on identical signed candidate
- [ ] Installer, ZIP and all payload SHA-256 values match independent downloads
- [ ] Human licence review L1–L6 and exact payload inventory accepted
- [ ] Firefox #52 reproduction/risk decision documented
- [ ] Reviewed PR integration and exact final source tree approved
- [ ] Owner approves release notes, support scope and public release

**No checkbox in this dossier constitutes an automatic authorization.**
