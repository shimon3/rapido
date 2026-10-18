# Issue #26 — security options for the first Windows beta

Status date: 2026-10-18. Decision owner: Samuel Bentouza. Issue #26 stays
**open** under both options until its own acceptance criteria are proven.

Detailed analysis already in the repository:
`docs/windows-executable-integrity-threat-model.md` and
`docs/windows-managed-integrity-contract.md`. This page turns them into a
release decision.

## What each mechanism does and does not prove

| Mechanism | Proves | Does **not** prove |
| --- | --- | --- |
| Authenticode signature (identity) | The file was signed by the pinned publisher and has not changed since signing | That the copy actually running is the signed one; protection against a same-user program that replaces files, edits HKCU or injects code |
| SHA-256 manifest (integrity) | A downloaded file is byte-identical to the approved one | Anything once the manifest sits next to a writable executable: the attacker can rewrite both |
| SID, process path, parent and pipe checks (current IPC) | The peer is a process of the same user at the expected path | That the binary at that path is genuine |
| Administrator-owned folder + HKLM registration + browser policy (Option B) | A standard-user program cannot modify the installation or redirect the browser's host | Protection against an administrator, kernel malware, or injection into an already authorized process |

## Attack surface in the current per-user install

| Surface | Writable by the same user? | Effect |
| --- | --- | --- |
| `%LOCALAPPDATA%\Programs\Rapido\Rapido.exe`, `RapidoNativeHost.exe`, DLLs, PYZ | Yes | Replacement runs attacker code when Rapido or the browser starts it |
| Native Messaging manifests next to the install | Yes | The `path` can point to another executable |
| `HKCU\Software\{Google\Chrome,Microsoft\Edge,Mozilla}\NativeMessagingHosts` | Yes | The browser can be pointed at another host |
| Install path choice, junctions, reparse points | Yes | Partially mitigated by the existing link guards; not race-free |
| Upgrade and repair | Runs as the user | A tampered install can tamper with the upgrade too |
| Portable copy | Yes, by definition | Same as above |

Conclusion: in the per-user model, any program already running as that user
can take over Rapido. That program can usually also read browser data directly,
so Rapido adds limited extra exposure. This residual risk must be **stated**,
not hidden.

## Option A — beta with documented residual risk (recommended for the first beta)

Minimum protections, all required:

1. Both executables and the installer signed and timestamped by the approved
   identity. Verified with the pin through `docs/authenticode-signing-procedure.md`.
2. Published SHA-256 hashes, with `verify_release_candidate.ps1` passing on an
   independent download.
3. Existing IPC identity checks, origin pinning, link guards, fail-closed
   capture, and no HTTP fallback kept unchanged. CI is green on the final
   candidate commit.
4. Installer takes executables only from the verified payload (done
   2026-10-18). No global process termination (existing test).
5. Release notes, README and the in-app About text state plainly: "Rapido does
   not protect against a program already running under your Windows account.
   The signature proves who published the download, not that your installed
   copy cannot be replaced."
6. Updates stay manual (link to the official release). No automatic
   download-and-run.

Limitations accepted under A: same-user file replacement, HKCU redirection,
manifest editing, injection, and portable copies without integrity guarantees.

Acceptance criteria for publishing under A (not for closing #26):

- [ ] Items 1–6 verified on the exact candidate. Evidence linked in
      `docs/beta-publication-checklist.md`.
- [ ] Windows 10 and 11 scenario 20 of `docs/windows-validation-matrix.md`
      records the per-user behaviour honestly.
- [ ] Owner signs off this residual-risk wording.

Cost: no new code beyond what this branch already contains. About 0.5 day of
wording and review, plus signing and validation time shared with every option.

## Option B — beta with reinforced protection

Adds an **administrator-managed installation profile**, next to the per-user one:

1. Machine-wide install under `%ProgramFiles%\Rapido` (installer with
   `PrivilegesRequired=admin`), with ACLs checked: Users have read and execute only.
2. HKLM native-host registrations, plus mandatory browser policy
   `NativeMessagingUserLevelHosts=false` for Chrome and Edge. Firefox is
   excluded from managed capture until an equivalent mechanism is proven.
3. Runtime admission: before sending any URL or ticket, verify the peer
   executable with `windows_signature.py` against a pin stored in an
   admin-protected location (HKLM or `%ProgramFiles%`). Fail closed with no
   downgrade.
4. Payload coverage: verify the PyInstaller archive and DLLs, for example a
   signed catalog or an App Control for Business policy. Signing the two
   bootloaders alone does not cover them.
5. Lifecycle: upgrade, repair, rollback, version floor and signer rollover,
   performed only by an administrator.

Tests to add (disposable Windows CI and VM, with policy setup and teardown):
every row of the acceptance table in `docs/windows-managed-integrity-contract.md`.
That includes HKCU override ignored under policy, standard-user write denied,
wrong signer refused, a tampered DLL refused, and upgrade/rollback.

Estimated cost: **8–15 developer days** (installer profile 2–3, admission
wiring 2–3, payload coverage and App Control research 2–4, lifecycle 1–2, CI
and VM matrix 2–3). It also needs the production certificate first, and admin
rights on each user's PC. Most beta testers would not use this profile.

## Recommendation

Publish the first beta under **Option A**, once its criteria are met. Keep #26
open, with Option B as its implementation path. Never describe the signature as
protection against local attacks.

**Owner decision needed:** A or B for the first beta, and approval of the
residual-risk wording in A.5.
