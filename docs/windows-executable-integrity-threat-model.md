# Windows executable integrity — threat model and decision gate (#26)

Status: design review only. **No executable attestation is implemented by this document.**
Applies to Rapido.exe, RapidoNativeHost.exe, launcher manifests and HKCU native-messaging entries on Windows.

## Boundaries and attacker capabilities

| Attacker / deployment | What existing checks establish | What remains unprotected |
| --- | --- | --- |
| Different Windows user, no elevation | Kernel-observed SID, process image path, pinned process handle and pipe peer identity reject many cross-user and unrelated-image peers. | Windows configuration mistakes, elevated compromise. |
| Same logged-on user, per-user Inno install | Parent image paths, exact browser origin, manifest ownership and direct symlink checks reject several accidental or simple impersonation paths. | Attacker may replace files in user-writable install, modify HKCU registration, replace adjacent manifests, alter user-writable policy, or inject into trusted processes. |
| Same logged-on user, portable unpacked directory | Same runtime identity checks, when invoked. | All portable files and any colocated hashes/signatures lists may be writable by the attacker. Portable execution does not provide a privileged local integrity anchor. |
| Elevated/admin attacker | No general protection claimed. | Administrator can modify installation, registry or running processes. |
| Developer / unsigned CI binaries | Can test behavior and reject obvious malformed inputs. | No verified publisher identity unless a deliberately configured trusted signing policy exists. Do not silently call unsigned test artifacts trusted production releases. |

**Non-goals:** DPAPI, SID/path matching, hashes placed beside the EXE, and direct symlink checks alone do not authenticate a publisher. Authenticating disk image does not prevent process injection, nor protect the process throughout its lifetime.

## Proposed trust policy — not yet approved or implemented

1. Decide a managed installation mode with **independently administered** policy and protected paths/ACLs. A per-user writable policy is not independent of a same-user attacker.
2. For production managed mode, verify signer/certificate chain and expected publisher identity for **both** desktop EXE and native host using Windows trust APIs with an explicit, securely managed trust anchor. Define certificate renewal/revocation handling and offline behavior before implementation. A valid signature alone does not prove an authorized Rapido publisher.
3. Tie manifest and native-host registry entries to the selected installation using checked canonical paths and filesystem handles. Treat reparse-point/junction chains, link swaps and registry races as review items; lexical comparisons are insufficient for all cases.
4. Fail closed if a mode **requires** verified integrity and verification is unavailable or fails. Unsigned developer/CI builds must use an explicitly separate, visibly untrusted mode; do not weaken production rules automatically.
5. Define upgrade/rollback/recovery ownership behavior and avoid deleting registrations belonging to another installation. Preserve current authenticated named-pipe checks; do not add insecure HTTP fallback.
6. If portable/per-user installs remain supported, **document inability to defend against an attacker with equivalent user permissions**, rather than implying Authenticode alone solves it.

## Required Windows CI matrix before claiming #26 fixed

- Baseline signed managed install with explicitly selected publisher policy (requires a safe CI signing/test policy).
- Replaced Rapido.exe and RapidoNativeHost.exe: refuse launch/IPC authorization without leaking secrets or performing browser capture.
- Replaced Firefox/Chromium manifest and HKCU native host registration: reject incorrect ownership, symlink/junction and moved-install targets.
- Legitimate installer upgrade, repair, uninstall and portable coexistence: no foreign registration/autostart deletion.
- Missing certificate, wrong trusted publisher, expired/revoked cert, signature tampering, unavailable revocation policy: expected fail-closed behavior precisely defined.
- Process injection: document residual risk; test only if a safe contained fixture is available. Never claim signature verification prevents it.
- Run on Windows GitHub Actions with isolated fixture registrations only; never on the user's PC.

## Release gate

Do **not** mark issue #26 resolved or release as protected against same-user compromise until a reviewer approves an enforceable trust anchor, production/unsigned-mode policy and end-to-end Windows tests. Existing draft PRs #17–29 remain independently reviewable; do not merge them without explicit approval.
