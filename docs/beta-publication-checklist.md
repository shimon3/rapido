# Rapido 1.3.0-beta.1 publication checklist

Status: **not ready to publish**. This checklist records evidence; it does not
authorize a merge, tag, release, deployment, purchase, or production signature.

## Branch and review gates

- [x] PR #34 contains the Windows stability changes and is the base of PR #35.
- [x] PR #35 contains release, licence, signing-readiness, MSIX, and update gates.
- [ ] Review and approve PR #34 before PR #35.
- [ ] Merge only with the owner's explicit authorization.
- [ ] Re-run the full workflow after the final merge candidate is assembled.
- [ ] Confirm the candidate commit is exactly the commit used to build every
  file proposed for distribution.

## Automated Windows evidence

- [x] CI #237 completed on the GitHub-hosted Windows runner: 278 tests passed,
  5 skipped, 1 warning, and 136 subtests passed.
- [x] Graphical WebView2 self-test, native protocol, installer lifecycle,
  installed/portable coexistence, and real Firefox handoff/fallback passed.
- [x] CI #237 produced an audit-only signing plan for 91 executable payloads.
- [x] The release job was skipped and the artifact was not published.
- [ ] Repeat the full workflow for the final signed candidate.
- [ ] Record Windows 10 and Windows 11 install, upgrade, repair, failed-upgrade
  recovery, rollback, and uninstall evidence for that exact candidate.
- [ ] Verify hashes and Authenticode signatures again after independently
  downloading the candidate.

CI currently runs on Windows Server 2025. Earlier Windows 10 and Windows 11
records remain useful regression evidence, but they are not evidence for a
future signed artifact.

## Browser integration

- [x] Chrome/Edge extension builds and shared behavior/policy tests pass.
- [x] A real Edge bridge was previously validated on an authorized isolated
  Windows 11 profile for the PR #34 artifact.
- [x] The real Firefox 157.0.1 native bridge and host-absent fallback pass in CI.
- [ ] Validate the exact final signed artifact with stable Chrome, Edge, and
  Firefox on Windows 10 and Windows 11.
- [ ] Record Chrome's normal supported extension-installation path. Do not claim
  success from Chrome for Testing when its executable is intentionally outside
  Rapido's production browser allowlist.

## Signing and issue #26

- [x] Disposable Authenticode fixtures cover trusted, unsigned, tampered,
  wrong-signer, held-file, and reparse-path behavior.
- [x] CI inventories hashes and signature state without handling a production
  certificate or secret.
- [ ] Select a publicly trusted provider and have the individual identity
  "Samuel Bentouza" accepted for Israel.
- [ ] Approve the displayed publisher spelling and certificate identity.
- [ ] Sign and timestamp both first-party executables, verify them, build the
  installer, then sign and verify the installer.
- [ ] Define certificate renewal, revocation, incident response, and signer
  rollover.
- [ ] Decide whether the beta remains a per-user distribution with the
  documented same-user limitation or gains an administrator-managed trust
  anchor. Signing alone does not close issue #26.
- [ ] Complete replacement, repair, upgrade, rollback, and uninstall tests with
  the production trust policy.

## Licences and payload

- [x] CI #237 inventoried 41 distributions and verified 41/41 PyPI advisory
  responses.
- [x] CI #237 inspected 155 files and 4 archives.
- [x] The bundle contains Rapido's MIT licence, THIRD-PARTY-NOTICES.md, package
  licence texts, source/replacement information, and payload evidence.
- [x] pystray/LGPLv3, certifi/MPL-2.0, and the proxy_tools metadata discrepancy
  are explicitly visible.
- [ ] A human legal review must approve the exact final inventory, notices,
  source offers/replacement instructions, and compatibility conclusions.

## Updates and publication

- [x] Update checking is read-only and does not silently download or execute an
  installer.
- [x] A direct installer link is accepted only for the exact official GitHub
  version, asset name, HTTPS host, and release path.
- [x] CI artifacts are explicitly marked non-official and non-production-signed.
- [x] The release job has a hard-coded `publishable=false` gate.
- [ ] Add automatic installation only in a later reviewed change after signature,
  hash, publisher, downgrade/replay, interruption, and rollback tests.
- [ ] Prepare final release notes with issue #26 residual risk and exact support
  scope.
- [ ] Obtain explicit owner authorization for merge, tag, release, and public
  distribution.

**Do not publish while any signing, legal, exact-candidate Windows/browser, or
owner-authorization gate above remains open.**
