# Managed executable integrity contract — issue #26

Status: **proposed design for review, not implemented or validated**. Current per-user and portable builds retain the limitations in [the threat model](windows-executable-integrity-threat-model.md). This document does not approve deployment, acquire a certificate, modify Windows policies, or close #26.

Implementation preparation: `windows_signature.py` now contains a standalone
held-file Authenticode primitive with an explicit SHA-256 leaf-certificate pin
collection. **It is not connected to runtime admission and does not implement
this managed profile.** It uses cached chain-revocation checks excluding the
root and refuses any nonzero trust status; it cannot establish revocation
freshness or independently protect the caller's pin policy. It reads the signer
from the successful verification state, closes that state on success/failure,
and retains a read-only shared file handle through caller use. It does not bind
that file to a running process or make a later pathname-based launch atomic.

`scripts/test_windows_signature.ps1` creates disposable, locally trusted CI
certificates and harmless signed PE fixtures only on GitHub-hosted Windows.
Its finally block removes those exact certificate entries, keys and fixture
files; no private key is exported and no fixture executable is launched.
These fixtures exercise signature/pin/replacement behavior, not deployment
enforcement, production signer identity, real revocation infrastructure or
timestamped certificate renewal. The full admission matrix below remains open.

## Decision to review

For the same-user on-disk replacement scenario, propose a separate, administrator-managed installation profile. Its authority must come from enforced OS/browser policy and administrator-protected files and configuration. A self-check inside a replaceable host cannot establish the initial trust boundary.

Do not advertise managed protection for the existing LocalAppData/HKCU installer. Do not introduce a service that processes download commands as SYSTEM: downloads and the current IPC remain in the user's context. Administrator operations are limited to installation, policy and authorized maintenance.

The threat is a standard-user attacker able to modify that user's files and HKCU. Administrator compromise and injection into an already authorized process remain outside the proposed guarantee. This profile is not a general isolation boundary between all programs sharing the account.

## Admission contract (all conditions required)

| Condition | Required evidence before a protected capture is permitted |
| --- | --- |
| Administrator-owned installation | Effective ACLs prevent the standard user from modifying the installation, manifests, configuration and ancestor paths; ownership alone is insufficient. Reject unexpected reparse points. |
| Enforced code policy | OS policy prevents unapproved code from executing in the relevant launch/loading paths. Audit-only policy is insufficient. No allow rule based solely on a user-writable path. |
| Authorized Rapido signer | An independently deployed policy identifies the authorized signer and approved product/files/version floor. A valid signature from an arbitrary publisher is insufficient. No runtime trust-on-first-use. |
| Complete executable content | Include both EXEs and the PyInstaller runtime, DLLs, Python/package payload and extraction/loading paths. Signing two bootloaders alone is insufficient evidence for interpreted or extracted code. |
| Protected host selection | The browser must select the protected system registration before any download URL/ticket is sent. Block user-level overrides through independently administered effective browser policy, or exclude that browser/profile from managed capture. |
| Existing IPC identity | Keep SID, full process image path, pinned process handles, creation-order checks, pipe ACLs and exact extension identities. Integrity checks supplement these checks. |
| Defined trust failure | Missing/invalid/indeterminate required verification denies managed capture before prepare, browser cancellation or payload transfer. No fallback to HTTP, portable or unsigned mode. |

These are requirements, not assertions that App Control or Authenticode automatically supplies every row. A concrete supported implementation must prove each row in Windows CI and review.

## Browser admission

Edge documents HKCU-first discovery and Chromium/Chrome fallback locations [1]. A protected HKLM key alone therefore does not establish the selected host. Edge's mandatory `NativeMessagingUserLevelHosts` policy can disable user-level hosts [2]; the document also lists profile applicability restrictions. Require evidence of the effective policy for each supported profile, not merely the presence of a registry value.

Chrome documents a corresponding user-level-host policy in Chromium's primary policy definition [3]. Validate the selected supported Chrome version and effective policy with a deliberately conflicting HKCU fixture. Cover all registry views and fallback locations actually consulted by that browser.

Firefox remains **unadmitted to the proposed managed profile** until an equivalent enforceable selection mechanism is identified and tested. Mozilla documents the native host manifest/registration mechanism [4]; this review has not established an equivalent user-host-disable policy. This is an evidence gap, not a claim that such a mechanism is impossible. Existing Firefox development capture is not changed by this document.

Browser/extension files and the effective extension identity also belong to the threat review. A developer-loaded extension in a user-writable directory cannot be presented as a protected managed client. Production store identity and policy-controlled installation must be resolved separately; current development IDs are not proof of those conditions.

## Signing and verification behavior to implement

Windows trust verification and publisher authorization are separate decisions. `WinVerifyTrust` returns zero for success; other return values are failures and must not be treated as HRESULT success [5]. An eventual wrapper must release its verification state, reject exceptions, and authorize against protected publisher policy.

Proposed managed defaults: require a valid trust result and explicit publisher/product/version authorization; deny revoked or indeterminate required revocation results. Define timestamp/expiration semantics using a reviewed Windows trust configuration and fixtures before implementation. Do not equate an expired leaf certificate with an invalid timestamped signature without those checks.

Signer rollover requires an administrator-authorized overlap policy installed before the new build. Removal of an old signer or vulnerable version requires a policy update and tests. A version floor stored in HKCU or next to writable EXEs is not authoritative. No signing key or production certificate is present or assumed by this design.

Microsoft describes signature-based rules and signed catalogs for packaged files [6]. The precise rule scope, interpreted-code handling, one-file extraction behavior, revocation behavior and Windows feature availability still require a selected deployment implementation. Do not supply a broad allow rule or claim that a signed catalog prevents arbitrary process injection.

## Lifecycle requirements

1. Install: administrator stages and validates the complete payload in a protected directory. Verify ACLs and effective policy before exposing managed registration. Preserve foreign registrations; report conflicts instead of taking ownership.
2. Upgrade: validate the new payload and policy compatibility before switching registration. Stop only processes proven to belong to this installation; preserve foreign same-name processes. Test interrupted upgrade and restart.
3. Rollback: permit only administrator-authorized versions meeting the protected version floor. A rejected downgrade leaves the last authorized installation intact. Recovery cannot silently disable verification.
4. Repair/move: require authorized maintenance and revalidation of paths, ACLs, dependencies and browser policy. Reject link swaps or ambiguous ownership. Document non-race-free checks until a handle-based implementation proves otherwise.
5. Uninstall: remove only this installation's registrations/autostart entries. Do not remove a shared enterprise browser/code policy automatically or enable user-level hosts as cleanup.

## Windows acceptance evidence

Use disposable Windows GitHub Actions environments and isolated fixture registrations only. Do not alter the user's PC or broadly change a shared runner's execution policy. Tests needing enforcement/reboot belong on a disposable Windows VM with explicit policy setup and teardown; do not represent mocked unit tests as OS enforcement evidence. CI test signing must be isolated from production signing and must never ship as production trust.

| Fixture/action | Required observable outcome |
| --- | --- |
| Authorized signed complete install | Legitimate host selection and prepare/cancel/commit succeed once; current IPC remains enforced. |
| Replace either EXE with harmless wrong/unsigned fixture | Unapproved execution or managed authorization is refused; URL/ticket never reaches the fixture and no capture starts. |
| Tamper a bundled DLL/Python payload or extraction target | Refuse unapproved code loading/execution; measure this independently of EXE signature success. |
| Substitute a valid signature from a different publisher | Refuse managed admission even if generic trust verification succeeds. |
| Change HKCU host entry/manifest, including Edge fallbacks | Browser ignores the user host under effective policy; fixture receives zero sensitive payload. Test before Rapido host code executes. |
| Change protected system manifest or installation contents as standard user | OS denies modification. Separately simulate authorized bad configuration and assert capture refusal. |
| Remove required policy or use an unsupported browser/profile | Managed capture disabled; original browser download preserved. No implicit downgrade. |
| Missing/invalid/revoked signer, indeterminate verification | Deny according to the defined trust configuration, with sanitized failure reasons. |
| Certificate renewal and valid timestamped older build | Accept/reject according to protected signer/version policy; no hard-coded expiration shortcut. |
| Reparse/link swap, moved install, failed upgrade/repair, downgrade | Refuse ambiguity or preserve the last authorized state; no foreign registration deletion. |
| Legitimate upgrade, uninstall, installed/portable coexistence | Supported transition works; no broad process kill, foreign state destruction or shared-policy removal. |
| Injected authorized process | Remains a documented residual risk; no claim of protection from disk-signature checks. |

For each row record OS/browser version, effective policy, signer fixture identity, payload/build identity, event/decision logs and negative side effects checked. Use synthetic URLs/tickets and avoid real secrets. A green existing build only validates existing behavior; it does not validate this contract.

## Implementation sequence and gates

1. Review this contract against the threat model; select supported OS/browser profiles and independently protected enforcement mechanisms.
2. Establish signer lifecycle and safe CI fixtures; resolve PyInstaller/dependency coverage and browser selection. Keep #26 open while any admission row lacks evidence.
3. Implement small fail-closed verification and deployment components on a dependent branch; run focused tests before existing security regression suites.
4. Run the enforcement/lifecycle matrix on disposable Windows infrastructure, then obtain review. Merge and publication still require explicit user authorization.

No runtime work should substitute path checks, DPAPI, self-attestation, an environment variable or adjacent hash manifests for the independent anchor required by this issue.

## Primary sources checked 2026-10-15

1. [Microsoft Edge native messaging — discovery order and fallbacks](https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging)
2. [Microsoft Edge NativeMessagingUserLevelHosts — mandatory policy and applicability](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/nativemessaginguserlevelhosts)
3. [Chromium primary NativeMessagingUserLevelHosts policy definition](https://chromium.googlesource.com/chromium/src/+/764c23680e893ba168c161a62ca91ade8385867a/components/policy/resources/templates/policy_definitions/NativeMessaging/NativeMessagingUserLevelHosts.yaml) (immutable source revision; deployed browser support still requires verification)
4. [Mozilla native messaging](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Native_messaging)
5. [Microsoft WinVerifyTrust](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/nf-wintrust-winverifytrust)
6. [Microsoft code signing and App Control](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/deployment/use-code-signing-for-better-control-and-protection)
7. [WINTRUST_DATA flags and verification state lifecycle](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/ns-wintrust-wintrust_data)
8. [WINTRUST_FILE_INFO file handle](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/ns-wintrust-wintrust_file_info)
9. [Provider data from verification state](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/nf-wintrust-wthelperprovdatafromstatedata), [signer](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/nf-wintrust-wthelpergetprovsignerfromchain), [certificate](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/nf-wintrust-wthelpergetprovcertfromchain), [certificate layout](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/ns-wintrust-crypt_provider_cert), [CERT_CONTEXT](https://learn.microsoft.com/en-us/windows/win32/api/wincrypt/ns-wincrypt-cert_context)
10. [CreateFileW sharing lifetime](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
11. [New-SelfSignedCertificate (test certificates)](https://learn.microsoft.com/en-us/powershell/module/pki/new-selfsignedcertificate?view=windowsserver2025-ps), [Set-AuthenticodeSignature](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/set-authenticodesignature?view=powershell-5.1)
