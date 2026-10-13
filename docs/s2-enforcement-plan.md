# S2 implementation gate: authenticated native transport

## Confirmed on Windows
The Chrome extension can contact the registered native host (ping/pong). A public test file was captured and downloaded end to end.

## Current state (NOT S2-secure)
The extension calls the native host, which POSTs to the legacy unauthenticated `/api/capture` route. A separate `/api/native/capture` route has an ephemeral bearer token and rejects browser-originated requests, but the native host does not yet receive the token. Header checks are defense-in-depth only: a local non-browser process can forge or omit Origin and Sec-Fetch-Site.

`tests/test_s2_route_inventory.py` inventories the legacy API mutations. They remain unprotected. Do not claim S2 has been fixed.

## Next implementation design and acceptance gates

1. Use a **Windows-restricted local IPC channel** between Rapido and the packaged native host. Protect it with a restrictive security descriptor for the intended interactive Windows user and verify client/server identity to the extent possible. Do not publish secrets in web endpoints, HTML, Chrome storage, logs, command lines or broadly readable files. Same-user compromise is explicitly outside the assurance of a user-SID-only ACL.
2. Tie a short-lived, single-purpose authorization to the local Rapido process and deliver it through the protected IPC mechanism. Never expose the process bearer to JavaScript in WebView or the browser extension.
3. Verify the host/engine handshake before enabling `capture_public`; reject when Rapido is absent, IPC authorization fails, the protocol version is unsupported, or capabilities are missing. For public download interception, fail closed and let Chrome handle the download.
4. Migrate desktop/WebView mutations and internal subprocess flows carefully. Distinguish legitimate trusted desktop calls, browser dialogs and native host calls. Do **not** blanket-require the token while the WebView and auxiliary windows rely on ordinary HTTP.
5. Protect the entire legacy mutation inventory, eliminate unauthenticated aliases and prove that an arbitrary local HTTP client without trusted IPC credentials cannot mutate state. Test malicious-looking spoofed Origin and host headers.
6. Keep authenticated/private-session downloads in Chrome until there is a separately reviewed workflow. No cookies may cross the unauthenticated loopback port.
7. Exercise negative cases and real Windows tests (startup, multiple windows, restart, pause/resume, video, extension disabled, portable install, update/rollback).

## Release gate
Do not merge PR #10 as S2 completion or publish a signed/unsigned update on its own. Its endpoints and route inventory are preparatory.
