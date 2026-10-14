# Rapido

**A download accelerator for Windows**: multi-connection downloads, pause/resume that survives reboots, a scheduler, a video grabber and a Chrome extension that takes over your browser downloads.

Built with **Python (FastAPI + asyncio + httpx)**, a single-file HTML interface, and a Manifest V3 Chrome extension. The interface is in French.

![Main window](docs/main.png)

| Capture dialog | Progress window |
|---|---|
| ![Capture](docs/capture.png) | ![Progress](docs/progress.png) |

## Features

- **Segmented downloading**: each file is split into up to 32 parts fetched in parallel with HTTP `Range` requests, written in place into a pre-allocated `.part` file.
- **Dynamic segmentation**: when a connection finishes early, the largest remaining segment is split in two and a new connection picks up the second half.
- **Robust resume**: per-segment progress is persisted to disk. Pause, network drops, crashes or a reboot all resume where they stopped. Retries use exponential backoff and are not counted as failures when the connection made progress.
- **Video grabber** (yt-dlp runs in a separate process so heavy extraction never freezes the app; sites are queried without your browser cookies first, which are used only if a video requires them): a "Download this video" button appears over videos in Chrome. Streams (HLS `.m3u8`, DASH `.mpd`, direct MP4) are detected by the extension and resolved with [yt-dlp](https://github.com/yt-dlp/yt-dlp), with a choice of quality (1080p, 720p, audio only…).
- **Browser integration**: registered Native Messaging uses a Windows named pipe with explicit ACL and kernel-verified user/executable identities. Cookie-dependent and private-window downloads remain in the browser. Referrer query/fragment data is removed, and missing/refused native capture leaves the original browser request intact. No HTTP fallback or browser-cookie export.
- **Capture → progress → done windows**: a file-info dialog before each download, a live progress window with per-connection details, and a completion dialog with "Open" / "Open folder".
- **Queue & scheduler**: "Download later", start/stop times, days of the week, then shut down, sleep or exit when the queue is finished (with a 60-second cancel window).
- **Clipboard monitoring**: copying a link to a file opens the capture dialog.
- **Global speed limiter**, automatic sorting by category, "refresh download address" for expired links (verified by file size), system tray icon.

## How it works

```
Chrome extension ──Native Messaging──► verified Windows named pipe ──► engine.py
  · intercepts downloads                     · REST API                    · asyncio + httpx segment workers
  · sniffs media requests                    · serves the UI & dialogs     · yt-dlp in a worker thread
  · video overlay button                                                  · scheduler loop, clipboard thread
```

| File | Role |
|---|---|
| `engine.py` | Download engine: probing, segmentation, workers, persistence, yt-dlp, scheduler, clipboard |
| `desktop.py` | Windows app entry point: native windows, tray, single instance, self-test |
| `app.py` | FastAPI app, REST API, tray icon, autostart |
| `index.html` | Main window (toolbar, categories, sortable table, context menu, options) |
| `window.html` | Small dialogs: capture, video quality, progress, completed |
| `extension/` | Chrome extension (Manifest V3) |
| `packaging/` | Icon, Windows version info, Inno Setup installer script |

Every `/api/` route except the non-sensitive `/api/ping` requires a per-process bearer. The desktop exclusively owns the loopback socket and injects authorization from native WebView2 request interception into its own local pages only. The bearer is never put in JavaScript, HTML, cookies, browser storage or a URL. Internal calls use in-process ASGI dispatch. The extension receives no bearer: its native host has only public-capture and public-settings authority through verified Windows IPC.

## Download

Get the latest **`Rapido-Setup-x.y.z.exe`** from the [Releases page](https://github.com/shimon3/rapido/releases/latest) and run it. It installs per user, so no administrator rights are needed, and adds Start-menu and desktop shortcuts, an uninstaller and an optional "start with Windows" setting.

> Windows SmartScreen may show *"Windows protected your PC"* because the app isn't code-signed: click **More info → Run anyway**.

A portable `.zip` is also attached to each release: unzip it and run `Rapido.exe`.

**Requirements:** Windows 10 or 11 (64-bit) with Microsoft Edge WebView2, which ships with up-to-date Windows. For video, Rapido can install two helpers for you in *Options → Outils*: **ffmpeg** (merges video + audio for HD qualities) and **Deno** (the JavaScript runtime yt-dlp needs for every YouTube quality).

### Chrome extension

*Options → Outils → Installer l'extension Chrome…* opens the extension folder and `chrome://extensions`. Turn on **Developer mode**, click **Load unpacked** and select that folder. The icon toggles capture on and off.

### Desktop behaviour

- Rapido is a native Windows app (Edge WebView2 windows via [pywebview](https://pywebview.flowrl.com/)). It has no console and no browser tab.
- Closing the main window keeps Rapido running in the notification area, so downloads continue. Right-click the tray icon → **Quitter Rapido** to exit.
- Launching Rapido a second time brings the existing window to the front.

## Build from source

```bash
pip install -r requirements.txt pyinstaller
python desktop.py            # run the desktop app
python app.py                # protected server only: ordinary browser UI cannot authenticate
```

Windows builds are produced by [GitHub Actions](.github/workflows/windows.yml) on `windows-latest`:

1. PyInstaller builds `Rapido.exe` (one-folder, windowed, with icon and version info).
2. A self-test launches the real exe. It opens a WebView2 window, downloads a file through the engine, checks yt-dlp and opens a popup window.
3. Inno Setup builds the installer, and a portable zip is created.
4. Pushing a `v*` tag publishes a GitHub Release with both files.

## API

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/state` | Downloads, queue state, pending power action |
| POST | `/api/downloads` | Add directly `{url, filename?, connections?, headers?, later?}` |
| POST | `/api/capture` · `/api/capture-video` | Create a pending download (opens the capture dialog) |
| POST | `/api/downloads/{id}/confirm` | Start or queue `{filename?, folder?, later, format_id?}` |
| POST | `/api/downloads/{id}/pause` · `/resume` · `/redownload` · `/refresh` | Control a download |
| POST | `/api/bulk/{pause\|resume\|delete\|clear-completed}` | Bulk actions |
| POST | `/api/queue/start` · `/api/queue/stop` | Queue control |
| GET / PUT | `/api/settings` | Settings, including the schedule |

## Security

Rapido runs a local API that can write files to disk and launch programs, so it is locked down so that only Rapido's own windows and its own Chrome extension can drive it.

| Threat | Protection |
|---|---|
| A website calls the local API (CSRF) | Every write must be `application/json` (strict media-type check), which forces a CORS preflight. CORS only allows Rapido's extension, and any other `Origin` is rejected with 403. Any request or page load that the browser marks as coming from another site (`Sec-Fetch-Site: cross-site` or `same-site`, even from another port on 127.0.0.1) is refused. The popup page only accepts a hexadecimal download id, and bulk actions never default to "everything". |
| DNS rebinding (`evil.com` resolving to 127.0.0.1) | The `Host` header must be `127.0.0.1:9614` or `localhost:9614`. |
| Arbitrary local HTTP client reads state or mutates the API | Every API route except ping requires the process bearer; forged Origin/Host headers do not supply authorization. |
| Another extension or a fake native/loopback server | Browser registration restricts extension IDs. Native IPC verifies the actual Windows SID and executable of the connected peer before transferring URLs; no unauthenticated HTTP fallback. |
| HTML or script injection through file names, video titles or error messages | All remote text is HTML-escaped. A strict Content-Security-Policy only allows Rapido's scripts (SHA-256 hashes), with no `eval`, `connect-src 'self'` and `frame-ancestors 'none'`. |
| Clickjacking | `X-Frame-Options: DENY` and `frame-ancestors 'none'`. |
| Session cookies leaking to other sites | Cookies only go to the site they belong to. For videos they go through a cookie jar scoped to the page's host, deleted right after. HTTP redirects drop them. |
| Session cookies on disk | They are never written in clear: they are encrypted with Windows DPAPI (only your Windows account can read them) and forgotten as soon as the download finishes. |
| Opening a downloaded program or document | Files get the *Mark of the Web* (`Zone.Identifier`, like Chrome/Edge), so SmartScreen and Office Protected View still warn you. |
| Disguised or dangerous file names | `/ \ : * ? " < > \|` and control characters are replaced, right-to-left override characters (`photo\u202Egpj.exe`) are removed, and reserved names (`CON`, `NUL`, `COM1`…) are prefixed. |
| Tampered settings launching another program | `ffmpeg` and browser paths must point to an existing file with the expected name. "Open folder" only opens the download folder. |
| Non-HTTP links (`file://`, `javascript:`) | Only `http(s)` URLs with a host are accepted, including video streams detected by the extension. All inputs have size limits. |
| Build supply chain | GitHub Actions are pinned to commit SHAs, the workflow has read-only permissions by default, and every build runs a self-test on Windows (security checks included) before an installer is published. |

**Not covered:** executable path/SID checks are not Authenticode verification and cannot protect against injection or replacement of trusted executables by a compromised account. The executable is not code-signed yet. Source-mode native hosts deliberately cannot claim packaged executable identity. Real Chrome/Edge/Firefox installation, private-session behavior and upgrade/uninstall still require manual verification before distribution. Video capture from the extension remains disabled; private downloads stay in the browser.

## Limitations

- Servers that don't support `Range` requests fall back to a single connection, and a pause restarts that file from zero (shown as "no resume").
- DRM-protected streams (Netflix, Disney+…) are not supported.
- Signed links that expire may refuse to resume hours later: use *Refresh download address*.
- Shutdown / sleep actions and clipboard monitoring are Windows only.

## Tests

```bash
pip install pytest
# Node.js is also required for the browser behavior tests.
python -m pytest -q tests
```

The regression tests reproduce the issues found by the October 2026 audit (CSRF, deletion of another download's temp file, shifted or compressed ranges, retry loop) plus multi-connection integrity and resume after a hard restart. They run on every Windows build before the executable is built.

## License

MIT. Downloading videos may be restricted by a site's terms of service: use it for content you are allowed to save.

### Chrome, Edge et Firefox : installation de développement

L’installateur Windows enregistre `com.rapido.bridge` pour les trois navigateurs
dans HKCU, avec les vues 32/64 bits. Firefox utilise son propre manifeste
`rapido-native-firefox.json` et l’identifiant `rapido-capture@rapido.local`.
Chrome et Edge utilisent l’identité stable du paquet non empaqueté
`hlpkfnodjoglfdiekijebbppfgkjkbmp`. Cette identité Edge de développement ne
remplace pas un identifiant attribué par Edge Add-ons.

- Chrome : charger le dossier `extension` dans `chrome://extensions`.
- Edge : charger le dossier `extension-edge` dans `edge://extensions`.
- Firefox : dans `about:debugging#/runtime/this-firefox`, charger temporairement
  `extension-firefox/manifest.json`. Firefox supprime ce chargement temporaire
  au redémarrage ; une installation durable nécessite un paquet signé.

La version portable inclut les trois dossiers et le pont compilé. Depuis son
dossier, exécuter `RapidoNativeHost.exe --register-native-hosts` pour enregistrer
le pont, puis `RapidoNativeHost.exe --unregister-native-hosts` avant de déplacer
ou supprimer ce dossier. Un autre chemin déjà enregistré est conservé : retirer
l’ancienne installation avant d’enregistrer la nouvelle.

Les contrôles automatisés couvrent les manifestes, l’identité de développement,
le registre Windows réel et l’installation/désinstallation compilée. Ils ne
remplacent pas les essais manuels dans les trois navigateurs : capture, navigation
privée, hôte absent, redémarrage et installation durable. Aucun paquet n’est publié
sur les boutiques par cette procédure.

### Protection de l’historique Windows (S3)

Chaque fiche de téléchargement est désormais enregistrée dans une enveloppe
DPAPI liée au compte Windows : URL signée, cookies, référents, candidats vidéo,
miniatures, descriptions et messages d’erreur ne sont plus écrits en clair dans
`downloads.json`. Les anciennes fiches lisibles sont migrées au chargement.
La reprise conserve l’URL complète après déchiffrement, sans supprimer la
signature nécessaire au serveur.

Un échec de protection ou une fiche illisible produit un état d’erreur sans URL
à relancer ; aucun champ en clair voisin d’une enveloppe ne sert de repli.
Les anciennes versions de Rapido ne savent pas lire ce nouveau format. Les
copies et sauvegardes d’un ancien historique ne sont pas modifiées.

La marque Windows `Zone.Identifier` conserve `ZoneId=3`, mais ses URL source
et référente ne contiennent plus que l’origine : chemins, identifiants,
paramètres et fragments peuvent contenir des jetons et ne sont plus recopiés
dans ces métadonnées. Les builds de développement hors Windows n’ont pas DPAPI.
