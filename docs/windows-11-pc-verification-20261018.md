# Windows 11 PC verification — 2026-10-18

## Scope and authorization

This report records a real Windows 11 validation of the Rapido build from draft
PR #34, including commit `8a7877fbbf493d9062305c87431c309c3baa600b` and its
non-publishing CI run #221. The tested archive was artifact `12129975748` with
the CI-reported SHA-256
`e96bfedf6b7a2d0e6da018ba44f9cb3864df3963911b909078ac52f505ad6a16`.

The owner explicitly authorized testing on personal device `DESKTOP-O535E49`,
with test material isolated under `C:\Users\samue\Downloads\testrapido`.
Install, upgrade, uninstall, reinstall, and the exact cleanup of empty Rapido
installer remnants were separately authorized. No normal browser profile was
read or modified. No merge, tag, release, publication, or change to `main` was
made.

## Environment

- Windows 11 Home 64-bit, version 10.0.26200, build 26200.
- Google Chrome 155.0.8059.84.
- Mozilla Firefox 157.0.1.
- Microsoft Edge / WebView2 155.0.4283.45.

## CI and artifact identity

CI #221 completed successfully: 268 tests passed, five skipped, one warning,
and 136 subtests. The release job was skipped. Authenticode fixtures passed 15
tests and 39 subtests. The licence evidence covered 41 distributions, and the
PyPI evidence gate reported 41/41.

The downloaded artifact hash matched CI exactly. Important inner hashes were:

| File | SHA-256 | Authenticode |
| --- | --- | --- |
| `Rapido-Setup-1.3.0-beta.1.exe` | `CA467C637170C6C120342B978BC658EDD8C8E03C08078EE394CCC9F9E790B063` | Not signed |
| `Rapido-1.3.0-beta.1-portable.zip` | `F48B1591899F6B89032E5FE11B22D80D6F94D1EC8AFFFB5A0FC0184255603BEF` | N/A (ZIP) |
| installed/portable `Rapido.exe` | `08682D6538413C0499E21B137D20CFD13B4D6764D20413FF5926C4E773E13D36` | Not signed |
| `RapidoNativeHost.exe` | `B09AF97C87FA17495E9DAA6BD65E6FE5F8946C4337BD26ACAF76EAD2712B2576` | Not signed |

The unsigned state is an actual distribution and SmartScreen limitation, not a
test-only cosmetic difference. It remains part of issue #26.

## Graphical self-test

The first CI #220 portable build exposed a transient Windows loopback failure:
the first run failed with `WinError 10053` while checking an unauthenticated
request, then two retries passed. PR #34 now retries transient loopback transport
errors but still requires an actual HTTP 403. Ten focused regression tests passed
locally, with one skipped.

The corrected CI #221 artifact passed all graphical self-test checks in four
runs. Every reported field was true, including the WebView2 window, download,
yt-dlp, popup, confirmations, CSP, DPAPI, MOTW, trusted WebView transport,
unauthenticated API refusal, native pipe, capture, and handoff.

| State | Result | Total time | WebView2 loaded |
| --- | --- | ---: | ---: |
| Portable, run 1 | PASS | 40.27 s | 1.93 s |
| Portable, run 2 | PASS | 22.56 s | 1.06 s |
| Installed after upgrade | PASS | 24.09 s | 1.71 s |
| Portable after uninstall | PASS | 21.28 s | 1.27 s |
| Installed after reinstall | PASS | 25.83 s | 1.88 s |

## Installation, uninstall, and recovery

- The previous `1.2.2` installation was backed up before replacement. The ZIP
  SHA-256 is
  `63F490B4C79DCFEA409F86873213495DF69A3C500C7B38C9EC417EE622C353E3`.
- Silent upgrade returned exit code 0 and installed `1.3.0-beta.1`. Installed
  executable hashes matched the portable artifact.
- Chrome, Edge, and Firefox registrations in both registry views pointed to
  owned manifests beside the installed native host.
- Silent uninstall returned exit code 0. It removed all files and all native
  registration values, but left an empty installation directory and empty Edge
  and Firefox leaf keys. The empty objects contained no values, subkeys, or
  reparse point. With the owner's explicit approval, only those exact empty
  remnants were removed and their absence was verified in both registry views.
- The portable post-uninstall self-test passed before reinstall.
- Silent reinstall used the same hash-verified installer, returned exit code 0,
  and restored all six browser registrations with valid owned manifests.
- The pre-existing history file was never opened. Its size and SHA-256 were
  checked before and after the lifecycle; the hash remained
  `1AFF41F745992AD12FFF1FFB4FE93C69A9ABAE0B53DE3F0CBA8F6EAD66CE317F`.

The exact CI #221 beta remains installed. No Rapido test process was left
running after the final browser checks. Test profiles, logs, the package, and
the backup remain under `Downloads\testrapido`; none were deleted.

## Firefox 157 real bridge and fallback

The repository's real Firefox scenario ran in a fresh isolated profile using
Selenium 4.51.0. It returned:

```json
{
  "browser_version": "157.0.1",
  "ok": true,
  "verified_native": true,
  "automatic_handoff": true,
  "host_absent_keeps_browser_download": true
}
```

The scenario proved the real native bridge, one automatic handoff to Rapido,
and fail-closed fallback to Firefox after deliberate host unregistration. The
installed host registration was restored afterward with exit code 0.

## Edge 155 real bridge

An isolated Edge profile loaded the installed `extension-edge` directory under
extension ID `hlpkfnodjoglfdiekijebbppfgkjkbmp`. With Rapido running on isolated
data, the browser-launched native host returned `pong`, protocol 1, and all four
public capabilities: `ping`, `capture_public`, `settings_public`, and
`capture_handoff`. A read-only `settings_public` call returned the configured
capture extensions and `min_capture_kb: 512`. No download was initiated.

## Chrome 155 result and automation boundary

No real Chrome bridge success is claimed on this PC.

Chrome 155 did not load Rapido through `--load-extension`. This matches the
[Chromium Extensions announcement](https://groups.google.com/a/chromium.org/g/chromium-extensions/c/1-g8EFx2BBY/m/S0ET5wPjCAAJ)
that official Chrome builds remove that flag starting with Chrome 137 and direct
developers to Chrome for Testing or a manual `chrome://extensions` load.

Chrome for Testing 155.0.8059.84 loaded the extension and reached the native
host, but the host returned only public `ping`; capabilities fell back to
`["ping"]` and settings returned `rapido_unavailable`. This is the expected
launcher allowlist: a browser executable under the disposable test cache is not
one of Rapido's approved installed Chrome/Edge/Firefox paths.

Several fresh branded-Chrome profiles reached `chrome://extensions`, enabled
the real Developer mode control, and exposed the real Load unpacked control.
The remote session could not complete Windows' directory-picker gesture, so the
Rapido service worker never appeared. Normal Chrome profiles were not read,
copied, or modified. A one-time owner interaction with Load unpacked remains
necessary for a current real-Chrome bridge test on this device.

The only Chrome enterprise policy found was
`ExtensionManifestV2Availability=2`; it marks Chrome as managed but does not
block Rapido's Manifest V3 extension.

## Licences and issue #26

CI #221 passed the repository's licence inventory and packaged-evidence gates
for 41 distributions. This is reproducible packaging evidence, not legal
advice.

Issue #26 remains open. The test proves that a copied Chrome for Testing binary
outside the approved path cannot use privileged native functions, but it does
not provide an independently protected trust anchor. The per-user installation,
HKCU registrations, and same-user writable state remain inside the documented
same-user tampering boundary. Unsigned executables also prevent a trusted
publisher claim.

## Remaining work

- Complete one owner-assisted Load unpacked action in the isolated Chrome 155
  profile, then run the prepared native ping/capabilities/settings probe.
- Perform manual SmartScreen and Microsoft Defender checks on a properly signed
  release candidate when signing is available.
- Obtain legal confirmation for the remaining third-party redistribution and
  LGPL relinking questions already tracked by the project.
- Keep issue #26 open until the trust-anchor and same-user boundary decisions
  are implemented or explicitly accepted for release.

