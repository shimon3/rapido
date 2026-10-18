# Windows 10 / Windows 11 validation matrix for the signed candidate

Status: **procedures ready, real-machine runs pending owner authorization.**
Nothing in this file has been executed on the owner's computers or virtual
machines. GitHub Actions runs on **Windows Server 2025**. Its results are
regression evidence, **not** a Windows 10 or Windows 11 validation.

Run every test on the **exact signed candidate** recorded by
`scripts/verify_release_candidate.ps1 -Record`. Start every machine run with
`verify_release_candidate.ps1`, so the files under test are proven to be the
approved ones.

## Environments

| ID | OS | Browsers | Notes |
| --- | --- | --- | --- |
| W10 | Windows 10 Pro 22H2 (build 19045), all updates | Chrome Stable, Edge Stable, Firefox Stable | Fresh snapshot before each scenario group |
| W11 | Windows 11 Pro, current GA build, all updates | Chrome Stable, Edge Stable, Firefox Stable | Fresh snapshot before each scenario group |

Record the OS build, browser versions, WebView2 Runtime version and SmartScreen
state with `scripts/collect_candidate_evidence.ps1` before and after each group.

## Scenarios

Legend: **CI** = automated on Windows Server 2025 today; **M** = manual on
W10 and W11; **CI+M** = both.

| # | Scenario | Coverage | Pass criterion |
| --- | --- | --- | --- |
| 1 | Clean install (per-user, no admin) | CI+M | Installer signature Valid with pinned signer; app under `%LOCALAPPDATA%\Programs\Rapido`; no UAC prompt |
| 2 | First launch | CI+M | Main window opens; `%USERPROFILE%\.rapido\rapido.log` has no traceback |
| 3 | WebView2 works | CI+M | UI renders; the CI self-test passes; on M, the UI is interactive |
| 4 | Notification-area icon | M | Icon present; Show, Hide and Quit work; the process ends on Quit |
| 5 | Browser integration install | CI (registration) + M | HKCU NativeMessagingHosts keys for Chrome, Edge and Firefox point to the installed manifests |
| 6 | Native Messaging round trip | CI (protocol, real Firefox) + M (Chrome, Edge, Firefox) | Ping/pong works; a browser download is handed to Rapido |
| 7 | Simple download | M | File complete, size and hash match the source |
| 8 | Concurrent downloads (3+) | M | All complete; the UI stays responsive |
| 9 | Resume after interruption | M | Network cut mid-download, then restored, then resume; final hash matches |
| 10 | Upgrade from the previous version (1.2.x) | M | Settings and history kept; native-host registrations updated; old binaries replaced |
| 11 | Reinstall over the same version | M | No duplicate registrations; app starts |
| 12 | Repair (rerun the installer) | M | Deleted `RapidoNativeHost.exe` restored and signature Valid |
| 13 | Uninstall | CI+M | Program files removed; unrelated processes untouched (CI test exists) |
| 14 | Browser registration cleanup | CI+M | HKCU keys and manifests of **this** install removed; another install's keys kept |
| 15 | User data preserved | M | `%USERPROFILE%\.rapido` and downloaded files are still present after uninstall, unless the user chose otherwise |
| 16 | Coexistence with the portable version | CI+M | Portable still runs after the installed copy is uninstalled (CI test exists) |
| 17 | Authenticode check | M | `Get-AuthenticodeSignature` Valid with timestamp for installer, `Rapido.exe` and `RapidoNativeHost.exe`; signer pin matches |
| 18 | SHA-256 check | M | `verify_release_candidate.ps1` reports a match |
| 19 | SmartScreen behaviour | M | Record the exact prompt (publisher name shown or "unknown"). New certificates may still warn until they build reputation. Record the warning, do not bypass it in documentation |
| 20 | Modified or untrusted file rejected (when the check is enabled) | CI (fixtures) + M | Replacing `RapidoNativeHost.exe` with a differently signed copy is refused where the managed or verification mode applies. Record the behaviour in plain per-user mode as the documented residual risk of issue #26 |

## Order of a manual run (per OS)

1. Restore a clean snapshot. Run `collect_candidate_evidence.ps1 -Phase before`.
2. Run `verify_release_candidate.ps1` on the candidate copied to the machine.
3. Scenarios 1–9 with Chrome, Edge and Firefox.
4. Restore the snapshot with 1.2.x installed, then scenario 10. Then 11 and 12.
5. Scenarios 13–16, then 17–20.
6. Run `collect_candidate_evidence.ps1 -Phase after`. Attach both JSON files and
   a short pass/fail table to `docs/windows-<10|11>-signed-candidate-<date>.md`.

## What CI already proves (Windows Server 2025)

Real-window WebView2 self-test, native protocol ping/pong, per-user install and
uninstall with HKCU registration checks, installed/portable coexistence, real
Firefox native bridge and fallback, Authenticode fixtures, and the signing-order
rehearsal with negative cases. Re-run the workflow on the final candidate
commit.
