# S2/S3 native migration validation

Status: implementation under review; no merge or public release approved.

## API and clients
- Every /api/ route except the non-sensitive ping requires a per-process bearer,
  including GET state/settings/download records and watch mutations.
- Internal desktop calls use ASGI in the same process, without proxy/TCP.
- WebView2 has an exclusive owned listener and direct/no-proxy networking.
  Native request interception adds authorization only from its own bound page
  to its own local API. The token is never inserted into HTML/JS/cookies/URLs.
- Browser hosts no longer use loopback HTTP. They verify the actual named-pipe
  server process before transferring URLs. The server verifies the client SID
  and full executable path before reading the bounded request.
- The native launcher also pins its actual parent chain: a trusted desktop
  process or a supported browser with the exact extension origin/add-on ID.
  Helper one-file bootstrap parents are bounded and process creation order is
  checked to reject reused parent PIDs.
- Native-host RPC authority is limited to public capture, capabilities and the
  two public capture settings; it cannot fetch tokens or issue arbitrary routes.
- Browser cookies/Authorization headers are not supported by this protocol.
  Private/cookie-dependent captures stay in the browser. Referrer queries and
  fragments are discarded. Video extension capture remains disabled.

## Evidence
- PR #17: six real kernel identity tests and Windows CI #108 passed.
- PR #18: Windows CI #109 passed: 90 tests plus seven subtests, including all six
  actual named-pipe tests (not skipped on the ordinary Windows runner).
- The sandbox AppContainer cannot open the ordinary desktop pipe: six real pipe
  tests are explicitly skipped there. The DACL has not been loosened.
- This migration has local API/header/protocol tests; packaged validation is
  required in its own Windows CI before claiming the migration is operational.
  The executable self-test now checks native WebView2 authorization, denial of
  ordinary HTTP clients, actual packaged native capabilities and public capture.

## Still required before release approval
- Real Chrome/Edge/Firefox installs, private sessions, profiles, restart,
  fallback, redirects, fast completed downloads and cancel-failure behavior.
- Browser-specific host registration, installer upgrade/uninstall/portable flow.
- Review the exact assurance boundary: SID/image-path checks are not Authenticode
  publisher verification and do not defend against injected or replaced trusted
  files, process-memory compromise or a fully compromised same-user account.
- Source native hosts intentionally cannot impersonate packaged image identity.
- The old standalone ordinary-browser UI cannot obtain native authorization.
- No merge, tag, release, signing or extension-store publication is authorized.
