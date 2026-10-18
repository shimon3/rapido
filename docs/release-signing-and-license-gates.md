# Release signing and licence gates

Status: implementation and owner checklist. This document does not contain a
certificate, private key, secret, legal approval, tag, or release authorization.

## What is already enforced

- Pull-request and ordinary build jobs have read-only GitHub contents access.
- A `v*` tag is necessary but no longer sufficient: the release job also
  requires the build output `publishable=true`. That output is deliberately
  hard-coded to `false` until a reviewed production-signing implementation
  changes the workflow.
- Every CI artifact is named `UNPUBLISHED-*`, expires after 14 days, and contains
  `ci-artifact-provenance.json` with `official_release=false` and
  `production_signed=false`.
- Build dependencies are pinned and checked.
- Windows CI exercises Authenticode verification with disposable test
  certificates that are removed after the job.
- The build collects exact third-party license, source, native-payload, and
  provenance evidence.
- The build writes an audit-only `signing-plan.json` containing hashes and
  current Authenticode status for executable payloads. The audit has no signing
  command, certificate, key, secret, or publication permission.
- Rapido and its native host still ship unsigned today. Issue #26 therefore
  remains open.

## Gate A — production signing identity

Before claiming a signed release, the owner must obtain a Windows code-signing
certificate for the approved legal publisher identity. The private key must be
held by a protected signing service, hardware token, or equivalent controlled
facility; it must never be committed, uploaded as a normal artifact, written
into application files, or reused from the disposable CI fixtures.

Record outside the repository:

1. approved publisher/legal identity;
2. certificate chain and SHA-256 certificate identity;
3. key custodians and recovery procedure;
4. timestamp service and offline/revocation policy;
5. renewal overlap and emergency revocation procedure.

A protected GitHub release environment should require manual approval and
limit production signing credentials to explicit version-tag builds. Pull
requests, `main`, previews, and manual test builds must not receive those
credentials. Enabling publication requires a reviewed code change that replaces
the hard-coded `publishable=false`; a repository variable or tag alone must not
bypass this gate.

## Gate B — signing order and verification

For a production candidate:

1. build `Rapido.exe` and `RapidoNativeHost.exe`;
2. sign both files with SHA-256 and an approved RFC 3161 timestamp;
3. verify Windows trust, timestamp, and the exact authorized signer;
4. build the installer from those already signed payloads;
5. sign and verify the installer;
6. recreate the portable ZIP from the verified signed payload;
7. compute and publish SHA-256 hashes;
8. verify downloaded installer and ZIP independently before release approval.

Any missing, invalid, unexpected, or indeterminate required signature must
stop publication. A generic valid signature from another publisher is not
sufficient.

## Gate C — issue #26 trust boundary

Signing alone does not prevent a malicious program already running as the same
Windows user from replacing a per-user or portable installation. A claim of
protection against that attacker additionally requires an independently
protected installation and policy, such as an administrator-managed location
and reviewed Windows application-control policy covering:

- both Rapido executables;
- the PyInstaller runtime and all loaded DLL/Python/native payload;
- approved version floors and signer rollover;
- Chrome/Edge native-host policy and the Firefox trust decision;
- upgrade, repair, rollback, uninstall, reparse-point, and replacement cases.

Unsigned developer and portable builds must remain visibly separate and must
not silently fall back from a managed fail-closed mode. Process injection
remains a documented residual risk.

## Gate D — licence and source review

Every release candidate must ship `THIRD-PARTY-NOTICES.md` plus the generated
`third-party` evidence directory. Reviewers must check:

- all pinned distributions are represented;
- original license and notice texts are present;
- pystray LGPLv3 source/replacement information matches the shipped files;
- certifi MPL-2.0 source information and full license text match the shipped
  files;
- the proxy_tools MIT/BSD metadata discrepancy remains visible with the exact
  upstream BSD text;
- CPython, WebView2 SDK, native libraries, and Rust crate notices match the
  payload;
- no unexpected FFmpeg, Deno, test framework, private key, or signing fixture
  is present.

The technical evidence can support professional legal review; it cannot replace
one. Do not mark licence compliance complete solely because CI is green.

## Acceptance evidence still required

- a certificate-backed, non-publishing signing rehearsal on a disposable
  Windows runner;
- negative tests for unsigned, tampered, wrong-publisher, expired/revoked or
  indeterminate candidates;
- Windows 10 and Windows 11 install, upgrade, repair, rollback, and uninstall
  evidence for the exact signed artifact;
- an independently downloaded artifact whose hashes and signatures match;
- owner approval of the publisher identity, release notes, remaining risks,
  and final licence review.

Until those items exist, keep #26 open and do not describe Rapido as protected
against a compromised Windows account.

The operational publication checklist is in `docs/beta-publication-checklist.md`.
The current supplier comparison for Samuel Bentouza in Israel is in
`docs/authenticode-options-israel.md`.
