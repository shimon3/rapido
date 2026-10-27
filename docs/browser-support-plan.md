# Browser support plan (Chrome, Edge, Firefox)

Status on 2026-10-27: the shared extension contract, development packages and
native-host registration are covered for Chrome, Edge and Firefox. A real
Firefox 157.0.1 native bridge and download handoff pass in Windows CI. The
exact beta.2 candidate still needs manual end-to-end Chrome, Edge and Firefox
checks on Windows 10 and Windows 11. These are development extensions, not
store-published packages.

## Current extension dependencies (verified in extension/)

- Manifest V3 with a background service worker and the `chrome.*` namespace.
- `downloads.onCreated`, `downloads.onDeterminingFilename`, `downloads.cancel/erase/download`.
- `webRequest.onHeadersReceived` with response headers for media discovery.
- `storage.local` and `storage.session`, `contextMenus`, `action`, `tabs`, `cookies`.
- `runtime.sendNativeMessage("com.rapido.bridge", ...)` for ping and public capture.
- Browser capture mutations use the Native Messaging ticket flow; the
  extension does not receive a loopback API credential and has no HTTP mutation
  fallback.
- Direct public-file video capture is allowed through that same flow. Streams,
  authenticated media and private-session capture remain fail-closed.
- Issue #26 remains open: Native Messaging peer/path checks do not prove the
  integrity of executables or registrations writable by the same Windows user.

## Microsoft Edge (Chromium)

1. CI builds a separate unpacked Edge development directory. An Edge Add-ons
   publication will still require the store-assigned identity and owner approval.
2. The installer lifecycle test covers the Edge-specific HKCU Native Messaging
   registration and exact allowed Chromium origin.
3. Static and JavaScript behavior tests cover popup naming, menus, downloads,
   ticket handoff, cookie/private fail-closed behavior and browser fallback.
4. Real Edge interaction on the exact beta.2 artifact remains a Windows 10/11
   manual gate.

## Mozilla Firefox

1. CI builds a Firefox-specific manifest with a stable Gecko development ID and
   an event-page background model.
2. Contract tests cover the supported API differences, Firefox default-store
   policy and private-download fail-closed behavior.
3. Installer and registration tests use Firefox's `allowed_extensions` and its
   dedicated HKCU registration path.
4. Windows CI installs a checksum- and publisher-verified Firefox 157.0.1
   fixture, then exercises ping, capabilities, prepare/abort, prepare/commit,
   download handoff and fallback with the packaged native host.
5. Manual UX checks and any Mozilla signing/store process remain owner gates.

## Release gates (all browsers)

- Preserve the authenticated/ticketed Native Messaging route and its peer,
  origin and link checks; never restore an HTTP mutation fallback.
- Keep cookies, authenticated URLs and private-session metadata fail-closed.
- Per-browser installation/uninstallation, upgrade, and native-host registration tests on Windows.
- Manual tests of regular/private sessions, redirects, download cancel/fallback, context menus, media sniffing, service-worker restart, multiple profiles, and browser absence.
- No installer distribution or extension-store publication without explicit approval.
