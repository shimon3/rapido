# Windows 10 VM verification — 2026-10-18

## Scope

This report records a real Windows validation of the Rapido build from commit
`f62c5c1310f187666b79fb5c0da77f5eeef8faf9` on draft PR #34. The tested files
came from non-publishing CI run #218, artifact `12127266279`.

The work was performed on the authorized dedicated machine
`DESKTOP-F2ALUG9` through Remote Desktop Commander. No merge, tag, release,
publication, or change to `main` was made.

## Environment

- Windows 10 Pro 22H2, build 19045, running in VMware.
- Approximately 2 GB RAM; memory pressure was high during browser automation.
- Microsoft Edge / WebView2: 155.0.4283.45.
- Google Chrome: 155.0.8059.80.
- Mozilla Firefox: 158.0, installed under
  `C:\Program Files (x86)\Mozilla Firefox\firefox.exe`.
- Firefox signature: valid, signed by Mozilla Corporation.

Windows 11 was not available and is not covered by this report.

## Artifact identity

| File | SHA-256 | Authenticode |
| --- | --- | --- |
| `Rapido-Setup-1.3.0-beta.1.exe` | `E4B09F9EAC90A490FA57D3D6300CE83541FC1B6E8C74F215C3769CFFA4D4BAF9` | Not signed |
| `Rapido-Portable-1.3.0-beta.1.zip` | `E750B31390946712E01AF44083334808D010196FBE3081D64C5D46D1FC635E38` | N/A (ZIP) |
| installed/portable `Rapido.exe` | `CE6A7C5C58663FFB92F75EB8EF2EC49766CA3FB978B2EB36C81CFACF740801F5` | Not signed |
| `RapidoNativeHost.exe` | `CF9802D6A01D0A8E8C2E1BAD9B756B304B77ABA67FED47D2B6B3EA992427ADC6` | Not signed |

The unsigned state is expected for this non-publishing CI artifact, but it is a
real distribution and SmartScreen limitation. This validation is not a signing
or trust-boundary approval.

## Graphical self-test

The WebView2 graphical self-test passed in all three tested lifecycle states.
All reported checks were true, including download, yt-dlp, popup,
confirmations, CSP, DPAPI, MOTW, authentication, native pipe, capture, and
handoff checks.

| State | Result | WebView2 load time |
| --- | --- | --- |
| Portable, cold start | PASS (`ok: true`) | 35.02 s |
| Installed application | PASS (`ok: true`) | 4.23 s |
| Portable after uninstall | PASS (`ok: true`) | 4.00 s |

The cold-start delay is recorded as observed; it was not diagnosed as a product
failure.

## Installation, upgrade, uninstall, and recovery

- The previous installation was backed up before replacement.
- Silent upgrade to the PR #34 artifact returned success and installed the
  exact executable hashes listed above.
- Chrome, Edge, and Firefox native-messaging registrations pointed to the
  installed PR #34 native host.
- Silent uninstall returned exit code 0, removed the installation directory,
  and removed the native-messaging registrations.
- The portable build retained the same hashes and passed its graphical
  self-test after uninstall.
- Silent reinstall returned exit code 0. The PR #34 build was left installed in
  the standard per-user location and running in tray mode.
- The local API `/api/ping` identified the running service as Rapido after
  reinstall.

The pre-existing user download-history file was never opened or inspected. It
was hashed before the upgrade, after the upgrade, after uninstall, and after
reinstall. Its SHA-256 remained:

`D9F27E628069B1BCE9C83E98209720720E0A53609EA37B18E45C840BBA9CB6BB`

Recovery material retained on the VM:

- Backup:
  `C:\Users\samue\AppData\Local\Temp\Rapido-PR34-Audit-f62c5c1\pre-pr34-install-backup.zip`
- Backup SHA-256:
  `F797D5CA3CA88054FB8D3873CC08306BDDD536AC13AE4EF521DD180493304FBF`
- Test root:
  `C:\Users\samue\AppData\Local\Temp\Rapido-PR34-Audit-f62c5c1`

## Firefox native bridge

The Firefox installation was found at its 32-bit program path; it was not
missing. The native-host registration allowed extension ID
`rapido-capture@rapido.local` and pointed to the PR #34 native host.

An isolated Firefox profile was used. Selenium 4.51.0 and GeckoDriver 0.37.1
temporarily loaded a precompressed Rapido XPI, then exercised the real native
messaging bridge. The successful run completed in 16.24 seconds and returned:

```json
{
  "browserVersion": "158.0",
  "result": {
    "capabilityProtocol": 1,
    "capabilityType": "capabilities",
    "features": [
      "ping",
      "capture_public",
      "settings_public",
      "capture_handoff"
    ],
    "ok": true,
    "pingProtocol": 1,
    "pingType": "pong"
  },
  "temporaryAddonId": "rapido-capture@rapido.local"
}
```

An earlier directory-based temporary-addon attempt timed out after 120 seconds
before native messaging. It is recorded as an inconclusive attempt, not a bridge
failure. The successful retry used the XPI and reduced Firefox background and
content-process activity.

No persistent Rapido add-on was added to the discovered normal Firefox
profiles. After automation cleanup left no Firefox process, Firefox was restored
with its previously observed `-os-autostart` argument. Rapido remained running.

## Chrome and Edge boundary

Normal Chrome and Edge profiles referenced unpacked Rapido extension paths in
their secure preferences. Those profiles were not modified.

Google Chrome 155 rejected the isolated development-loading route with
`ERR_BLOCKED_BY_CLIENT` and reported that `--disable-extensions-except` is not
allowed. Copying the normal profile's preferences into an isolated profile did
not bypass that restriction: `chrome://extensions-internals` contained only
Chrome component extensions, not Rapido. Chrome's native bridge was therefore
not exercised, and this is not recorded as a Rapido compatibility failure.

Microsoft Edge 155 accepted the installed `extension-edge` directory in a new
isolated profile. Its Rapido service worker loaded under extension ID
`hlpkfnodjoglfdiekijebbppfgkjkbmp` and called the registered
`com.rapido.bridge` host directly. The real installed host returned:

```json
{
  "ping": {"type": "pong", "protocol": 1},
  "capabilities": {
    "type": "capabilities",
    "protocol": 1,
    "features": [
      "ping",
      "capture_public",
      "settings_public",
      "capture_handoff"
    ]
  }
}
```

A separate read-only `settings_public` request returned the configured public
capture-extension list and `min_capture_kb: 512`. No download or capture was
started. The download-history SHA-256 remained
`D9F27E628069B1BCE9C83E98209720720E0A53609EA37B18E45C840BBA9CB6BB`, and
Rapido remained running.

Disposable Chrome and Edge profiles were removed after confirming that no
process referenced their exact paths. Normal profiles were not deleted or
modified.

## Licences and issue #26 security boundary

CI #218 passed the repository's licence inventory and packaged-evidence checks:
41 distributions, 154 files in four archives, and five WebView2 DLL identities
were reported. This is packaging evidence, not a legal opinion.

Issue #26 remains open. This test does not establish a trusted publisher or an
independently protected trust anchor. The per-user installation, HKCU native
registrations, and other same-user writable state remain inside the same-user
tampering boundary. The unsigned binaries also prevent a trusted-publisher
claim.

## Remaining validation gaps

- Repeat the lifecycle and graphical tests on Windows 11.
- Perform manual SmartScreen and Microsoft Defender checks on appropriately
  signed release candidates when signing is available.
- Exercise physical keyboard paths that browser automation cannot represent
  reliably.
- Complete a real Chrome native-bridge check through an installation route
  Chrome accepts. Edge ping, capabilities, and public settings are now proven,
  but an actual Chromium browser-driven capture/handoff was intentionally not
  started during this diagnostic.
- Resolve or explicitly accept the trust-boundary limitations tracked by issue
  #26 before making security claims.

