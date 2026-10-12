# Rapido

**A self-hosted download accelerator for Windows**: multi-connection downloads, pause/resume that survives reboots, a scheduler, a video grabber and a Chrome extension that takes over your browser downloads.

Built with **Python (FastAPI + asyncio + httpx)**, a single-file HTML interface, and a Manifest V3 Chrome extension. The interface is in French.

![Main window](docs/main.png)

| Capture dialog | Progress window |
|---|---|
| ![Capture](docs/capture.png) | ![Progress](docs/progress.png) |

## Features

- **Segmented downloading**: each file is split into up to 32 parts fetched in parallel with HTTP `Range` requests, written in place into a pre-allocated `.part` file.
- **Dynamic segmentation**: when a connection finishes early, the largest remaining segment is split in two and a new connection picks up the second half.
- **Robust resume**: per-segment progress is persisted to disk. Pause, network drops, crashes or a reboot all resume where they stopped. Retries use exponential backoff and are not counted as failures when the connection made progress.
- **Video grabber**: a "Download this video" button appears over videos in Chrome. Streams (HLS `.m3u8`, DASH `.mpd`, direct MP4) are detected by the extension and resolved with [yt-dlp](https://github.com/yt-dlp/yt-dlp), with a choice of quality (1080p, 720p, audio only…).
- **Browser integration**: the extension intercepts downloads matching your file types, forwards cookies and referrer (so logged-in downloads work), and falls back to Chrome if Rapido isn't running. Right-click menu included.
- **Capture → progress → done windows**: a file-info dialog before each download, a live progress window with per-connection details, and a completion dialog with "Open" / "Open folder".
- **Queue & scheduler**: "Download later", start/stop times, days of the week, then shut down, sleep or exit when the queue is finished (with a 60-second cancel window).
- **Clipboard monitoring**: copying a link to a file opens the capture dialog.
- **Global speed limiter**, automatic sorting by category, "refresh download address" for expired links (verified by file size), system tray icon.

## How it works

```
Chrome extension ──(JSON over localhost)──► FastAPI (127.0.0.1:9614) ──► engine.py
  · intercepts downloads                     · REST API                    · asyncio + httpx segment workers
  · sniffs media requests                    · serves the UI & dialogs     · yt-dlp in a worker thread
  · video overlay button                                                  · scheduler loop, clipboard thread
```

| File | Role |
|---|---|
| `engine.py` | Download engine: probing, segmentation, workers, persistence, yt-dlp, scheduler, clipboard |
| `app.py` | FastAPI app, REST API, tray icon |
| `index.html` | Main window (toolbar, categories, sortable table, context menu, options) |
| `window.html` | Small dialogs: capture, video quality, progress, completed |
| `extension/` | Chrome extension (Manifest V3) |

The API only listens on `127.0.0.1`, accepts cross-origin calls only from Chrome extensions, and requires `application/json` on every write, so a random website can't trigger downloads through a simple form post.

## Install (Windows)

1. Install **Python 3.10+** (tick "Add Python to PATH").
2. Optional, for HD video (merging video + audio): `winget install ffmpeg`
3. Double-click **`demarrer.bat`**. The first run creates a virtual environment, installs the dependencies and opens <http://localhost:9614>.

**Start with Windows:** `Win + R` → `shell:startup` → add a shortcut to `demarrer-silencieux.vbs` (runs in the background, logs in `%USERPROFILE%\.rapido\rapido.log`).

### Chrome extension

1. Open `chrome://extensions` and enable **Developer mode**.
2. **Load unpacked** → select the `extension` folder.
3. Pin the Rapido icon. Clicking it toggles capture on/off.

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

## Limitations

- Servers that don't support `Range` requests fall back to a single connection, and a pause restarts that file from zero (shown as "no resume").
- DRM-protected streams (Netflix, Disney+…) are not supported.
- Signed links that expire may refuse to resume hours later: use *Refresh download address*.
- Shutdown / sleep actions and clipboard monitoring are Windows only.

## License

MIT. Downloading videos may be restricted by a site's terms of service: use it for content you are allowed to save.
