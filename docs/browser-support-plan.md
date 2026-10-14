# Browser support plan (Chrome, Edge, Firefox)

Status: **Chrome tested only**. Edge and Firefox are **not supported or validated yet**. This document is a plan, not an installer or a compatibility claim.

## Current extension dependencies (verified in extension/)

- Manifest V3 with a background service worker and the `chrome.*` namespace.
- `downloads.onCreated`, `downloads.onDeterminingFilename`, `downloads.cancel/erase/download`.
- `webRequest.onHeadersReceived` with response headers for media discovery.
- `storage.local` and `storage.session`, `contextMenus`, `action`, `tabs`, `cookies`.
- `runtime.sendNativeMessage("com.rapido.bridge", ...)` for ping and public capture.
- Current public capture still reaches an unauthenticated localhost mutation endpoint. S2 security is **not** complete; browser expansion must not ship this path as secure.
- Video capture is deliberately disabled until S3 is resolved.

## Microsoft Edge (Chromium)

1. Use a separate Edge extension package/ID and verify MV3 APIs on supported Edge versions. Do not assume a Chrome extension ID is the Edge ID.
2. Register the native messaging host in the Edge-specific Windows registry location, with an explicit allowed extension origin. Chrome registration alone does not register Edge.
3. Verify popup, menus, downloads, session-cookie fail-closed policy, media detection, service-worker restart and fallback to browser download.
4. Do not distribute until authenticated S2 transport is integrated and Windows integration tests pass.

## Mozilla Firefox

1. Create a Firefox-specific manifest with a stable Gecko extension ID and supported background model. Validate MV3 background/event behavior and permissions against the targeted Firefox release; do not simply copy the Chrome service-worker manifest.
2. Use the supported WebExtensions namespace and test callback/promise differences. Verify `storage.session`, downloads, response-header observation and popup behavior rather than assuming API parity.
3. Native Messaging on Windows needs Firefox-specific registration and `allowed_extensions` (not Chromium `allowed_origins`); ensure the host name and executable path are installed for Firefox.
4. Test fallback behavior when native host is absent, private downloads remain in Firefox, and video capture stays disabled until S3 approval.
5. Package/sign via Mozilla's required distribution process only after security review and user approval.

## Release gates (all browsers)

- Complete authenticated Windows IPC, real client identity checks, and protected mutation routes (S2).
- No cookies or private-session metadata sent through legacy loopback (S3).
- Per-browser installation/uninstallation, upgrade, and native-host registration tests on Windows.
- Manual tests of regular/private sessions, redirects, download cancel/fallback, context menus, media sniffing, service-worker restart, multiple profiles, and browser absence.
- No merge, installer distribution, or extension-store publication without explicit approval.
