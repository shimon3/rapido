# Rapido — MSIX / Microsoft Store feasibility gate (18 October 2026)

**Status: investigation only; NOT Store-ready.** This branch is based on PR #35's work branch `work/release-compliance-gates-20261018`. No change to `main`, no packaging workflow enabled, no signing keys, no release and no Store submission.

## Existing build and constraints

Rapido is a Python/PyInstaller Win32 desktop program running WebView2, FastAPI on loopback, tray and helper processes. The current Inno Setup installer installs `Rapido.exe`, `RapidoNativeHost.exe`, the browser extension, shortcuts, HKCU Run autostart and native-host registrations. The uninstall path explicitly unregisters owned native hosts. Native browser integration is a security boundary: do not replace it with an unauthenticated localhost bridge.

## Compatibility assessment (evidence needed)

| Feature | Status | Required proof |
| --- | --- | --- |
| PyInstaller onedir + packaged full-trust Win32 launch | Plausible, unverified | MSIX Packaging Tool conversion or correctly authored package; launch installed package on Win10/11 |
| Edge WebView2 and tray | Unverified | Real UI, popup, tray and shutdown self-tests under package identity |
| Loopback port 9614 and named pipes | Unverified | Exact OS-peer verification, exclusive socket and fail-closed browser handoff under packaged paths |
| Chrome/Edge/Firefox Native Messaging | **Primary blocker until proven** | Package-aware host registrations (correct bitness, paths and browser registry views), owner checks and browser real integration tests, including uninstall/upgrade |
| Install per user, registry Run, shortcuts | Needs design change | Use package-supported startup task (with user control); never reuse Inno Setup's install hooks inside MSIX |
| `~/.rapido`, downloads, cookies/DPAPI | Needs migration tests | Confirm writable user state, downloaded files location, stable DPAPI identity and no data loss across upgrades and conversion |
| ffmpeg/Deno installation and child processes | Unverified | Helpers downloaded to user-writable paths, subprocess launch, integrity and Store policy review |
| Uninstall, upgrade and coexistence with EXE install | **Blocked until designed** | Side-by-side conflict detection; do not remove existing user data or another installation's browser registrations |
| License, privacy and compliance | Unverified | Preserve THIRD-PARTY-NOTICES; independent legal/security and Store policy review |

## Gate before an actual MSIX build

1. Reserve an app identity in Partner Center; obtain **real** `Identity Name`, `Publisher` and `PublisherDisplayName`. Never substitute an invented legal publisher or signing certificate.
2. Produce a Windows full-trust MSIX proof of concept via Microsoft's MSIX Packaging Tool on an isolated Windows VM, or build a manifest from a validated template with makeappx. A converted Inno installer must not depend on running unsupported custom install/uninstall actions.
3. Ensure all payload files (Rapido.exe, RapidoNativeHost.exe, extension, notices, dependencies and images) are packaged and app executable/visual assets are declared correctly.
4. Use an isolated disposable test identity/environment. For *local* installation only, sign the test MSIX with a locally trusted **development-only** certificate. No private key in GitHub or artifacts. Microsoft Store MSIX submission does not require a CA-trusted certificate; Microsoft signs after acceptance.
5. Run full real-device matrix: Windows 10 22H2 and Windows 11, clean install, app startup, WebView2, clipboard, tray, loopback safeguards, file downloading and MOTW, video helper execution, Chrome/Edge/Firefox native host and fallback, normal/beta installer coexistence, upgrades, uninstallation and data persistence. Record results and hashes.
6. Run Windows App Certification Kit and resolve errors. Verify Store rules for packaged full-trust desktop apps, privacy policy, permissions, dependencies and third-party licensing.
7. Keep any new CI package job **manual and artifact-only**, with least privilege and no release/Store upload. Do not enable until the compatibility gate above is passed.

### Stop conditions

- Any browser can reach protected operations without a verified OS peer.
- A packaged installation overwrites or unregisters another version's native host ownership.
- State/history is lost or silently migrated incorrectly.
- Packaged desktop/tray/native subprocess behavior fails, or Store certification rules are unmet.

## Official Microsoft documentation

- https://learn.microsoft.com/en-us/windows/apps/distribute-through-store/how-to-distribute-your-win32-app-through-microsoft-store
- https://learn.microsoft.com/en-us/windows/apps/publish/faq/get-started-with-the-microsoft-store
- https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/package-version-numbering
- https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options

**Decision: do not buy an OV certificate just for MSIX Store submission at this stage.** If MSIX fails this feasibility gate, EXE/MSI Store listing is an alternative but requires the publisher to sign the installer and PE files with a trusted certificate, and does not get Microsoft Store's automatic package signing.
