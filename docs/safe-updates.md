# Rapido updates — staged secure delivery

## Implemented in this PR
- The desktop UI checks the existing GET /api/updates/check around 15 seconds after page load, then every six hours while the UI is visible.
- New official GitHub Releases appear in a translated (FR/EN/HE) notification.
- Buttons: open the existing Help/update dialog, postpone until a later check, ignore this exact version (browser localStorage).
- Offline/network failures are silent. Downloads are never interrupted and **no installer is executed**.

## Why one-click installation is deliberately not enabled yet
Downloading over HTTPS and checking a SHA-256 checksum that is published alongside the installer is not enough to establish the publisher's authenticity if the release account or asset is compromised.

Before enabling a "Install update" button we must:
1. Sign Rapido installers with an approved Windows Authenticode code-signing certificate and protect the signing key outside the repository. Do not place certificates or private keys in GitHub source code.
2. Verify the installer signature **and the expected publisher certificate identity** (not merely that any signature exists). Reject unsigned, expired/revoked when verifiable, wrong publisher, or invalid signatures. Keep updater fail-closed.
3. Pin the release source to `shimon3/rapido`, require an exact installer filename for the version, HTTPS, a size cap, bounded timeouts, safe staging location and no redirects to arbitrary hosts. Do not execute a URL supplied from the browser.
4. Require explicit user confirmation; postpone installation while downloads are active; run the verified installer from a separate updater process after Rapido closes normally. Never silently kill active downloads. Preserve existing settings and recover cleanly if installation fails.
5. Test with signed and tampered fixtures, compromised download links, concurrent downloads, Windows/portable installs, older releases and translations.

Until certificate signing is in place, the notification can direct the user to the official release page for manual installation. We must not claim this PR delivers one-click installation.

## Privacy and defaults
No account, telemetry or new server required. The UI only reads the existing release-check endpoint. Ignored version is stored in local application WebView storage.
