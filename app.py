"""
Rapido - serveur local.
Lance avec : python app.py   puis ouvre http://localhost:9614
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from engine import Manager, IS_WINDOWS

HOST = "127.0.0.1"      # uniquement accessible depuis ton PC
PORT = 9614
BASE = Path(__file__).parent
DATA_DIR = Path(os.environ.get("RAPIDO_DATA", Path.home() / ".rapido"))

manager = Manager(DATA_DIR, PORT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await manager.start()
    yield
    await manager.stop()


app = FastAPI(title="Rapido", lifespan=lifespan)

# Seules l'interface (meme origine) et l'extension Chrome peuvent appeler l'API.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^chrome-extension://.*$",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_json(request: Request, call_next):
    # Empeche un site web quelconque de declencher des telechargements via un
    # formulaire "simple" : toute ecriture doit etre en JSON (=> preflight CORS).
    if request.method in ("POST", "PUT", "DELETE") and request.url.path.startswith("/api/"):
        if "application/json" not in request.headers.get("content-type", ""):
            return JSONResponse({"detail": "Content-Type application/json requis"}, status_code=415)
    return await call_next(request)


# ---------- modeles ----------
class AddRequest(BaseModel):
    url: str
    filename: str | None = None
    connections: int | None = Field(default=None, ge=1, le=32)
    headers: dict[str, str] | None = None
    later: bool = False


class CaptureRequest(BaseModel):
    url: str
    headers: dict[str, str] | None = None
    filename: str | None = None
    open_window: bool = False     # True = le serveur ouvre lui-meme la fenetre de capture


class VideoCaptureRequest(BaseModel):
    page_url: str
    candidates: list[str] = []
    headers: dict[str, str] | None = None
    open_window: bool = False


class ConfirmRequest(BaseModel):
    filename: str | None = None
    folder: str | None = None
    later: bool = False
    description: str = ""
    format_id: str | None = None


class UrlRequest(BaseModel):
    url: str


class IdsRequest(BaseModel):
    ids: list[str] = []
    delete_file: bool = False


class Schedule(BaseModel):
    enabled: bool | None = None
    start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    stop: str | None = Field(default=None, pattern=r"^(\d{2}:\d{2})?$")
    days: list[int] | None = None
    on_complete: str | None = Field(default=None, pattern=r"^(none|shutdown|sleep|exit)$")


class SettingsRequest(BaseModel):
    download_dir: str | None = None
    max_concurrent: int | None = Field(default=None, ge=1, le=10)
    connections: int | None = Field(default=None, ge=1, le=32)
    sort_by_category: bool | None = None
    speed_limit_kbps: int | None = Field(default=None, ge=0)
    show_capture_dialog: bool | None = None
    show_progress_window: bool | None = None
    show_complete_dialog: bool | None = None
    monitor_clipboard: bool | None = None
    capture_exts: list[str] | None = None
    min_capture_kb: int | None = Field(default=None, ge=0)
    ffmpeg_path: str | None = None
    browser_path: str | None = None
    schedule: Schedule | None = None


def get_dl(dl_id: str):
    dl = manager.downloads.get(dl_id)
    if not dl:
        raise HTTPException(404, "Telechargement introuvable")
    return dl


def check_url(u: str):
    if not u.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL http(s) invalide")


# ---------- pages ----------
@app.get("/")
async def index():
    return FileResponse(BASE / "index.html")


@app.get("/w")
async def window_page():
    """Petites fenetres : capture, video, progression / termine."""
    return FileResponse(BASE / "window.html")


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(BASE / "extension" / "icon128.png")


# ---------- etat ----------
@app.get("/api/ping")
async def ping():
    return {"ok": True, "app": "Rapido"}


@app.get("/api/state")
async def state():
    """Tout ce dont l'interface principale a besoin en un appel."""
    items = sorted((d for d in manager.downloads.values() if d.status != "pending"),
                   key=lambda d: d.created, reverse=True)
    return {
        "downloads": [d.to_public() for d in items],
        "queue_running": manager.queue_running,
        "power": manager.power,
        "ffmpeg": bool(manager.ffmpeg()),
    }


@app.get("/api/downloads")
async def list_downloads():
    return (await state())["downloads"]


@app.get("/api/downloads/{dl_id}")
async def one(dl_id: str, watch: bool = False):
    dl = get_dl(dl_id)
    if watch:
        dl.watched = time.time()
    return dl.to_public()


# ---------- ajout / capture ----------
@app.post("/api/downloads")
async def add_download(req: AddRequest):
    urls = [u.strip() for u in req.url.splitlines() if u.strip()]
    if not urls:
        raise HTTPException(400, "Aucune URL")
    for u in urls:
        check_url(u)
    added = [
        manager.add(u, req.filename if len(urls) == 1 else None, req.connections, req.headers, req.later)
        for u in urls
    ]
    return [d.to_public() for d in added]


@app.post("/api/capture")
async def capture(req: CaptureRequest):
    """Appele par l'extension : cree un telechargement 'en attente de confirmation'."""
    check_url(req.url)
    if not manager.settings.get("show_capture_dialog", True):
        dl = manager.add(req.url, req.filename, None, req.headers)
        if manager.settings.get("show_progress_window") and req.open_window:
            manager.open_window(f"/w?view=progress&id={dl.id}", 520, 430)
        return {"id": dl.id, "dialog": False}
    dl = manager.capture(req.url, req.headers, req.filename)
    if req.open_window:
        manager.open_window(f"/w?view=capture&id={dl.id}", 560, 540)
    return {"id": dl.id, "dialog": True}


@app.post("/api/capture-video")
async def capture_video(req: VideoCaptureRequest):
    check_url(req.page_url)
    dl = manager.capture_video(req.page_url, req.candidates, req.headers)
    if req.open_window:
        manager.open_window(f"/w?view=capture&id={dl.id}", 560, 520)
    return {"id": dl.id, "dialog": True}


@app.post("/api/downloads/{dl_id}/confirm")
async def confirm(dl_id: str, req: ConfirmRequest):
    dl = get_dl(dl_id)
    if dl.status != "pending":
        raise HTTPException(409, "Deja confirme")
    if dl.kind == "video":
        if dl.probe != "ready":
            raise HTTPException(409, "Analyse de la video pas terminee")
        if req.format_id:
            try:
                manager.choose_format(dl, req.format_id)
            except ValueError as e:
                raise HTTPException(400, str(e))
        if req.filename:
            ext = Path(dl.filename).suffix
            req.filename = Path(req.filename).stem + ext
    if req.folder:
        try:
            Path(req.folder).mkdir(parents=True, exist_ok=True)
        except Exception:
            raise HTTPException(400, "Dossier invalide")
    manager.confirm(dl_id, req.filename, req.folder, req.later, req.description)
    return dl.to_public()


@app.post("/api/downloads/{dl_id}/cancel-capture")
async def cancel_capture(dl_id: str):
    dl = manager.downloads.get(dl_id)
    if dl and dl.status == "pending":
        await manager.remove(dl_id)
    return {"ok": True}


# ---------- actions ----------
@app.post("/api/downloads/{dl_id}/pause")
async def pause(dl_id: str):
    get_dl(dl_id)
    await manager.pause(dl_id)
    return {"ok": True}


@app.post("/api/downloads/{dl_id}/resume")
async def resume(dl_id: str):
    get_dl(dl_id)
    manager.resume(dl_id)
    return {"ok": True}


@app.post("/api/downloads/{dl_id}/redownload")
async def redownload(dl_id: str):
    get_dl(dl_id)
    await manager._cancel_task(dl_id)
    manager.redownload(dl_id)
    return {"ok": True}


@app.post("/api/downloads/{dl_id}/refresh")
async def refresh_address(dl_id: str, req: UrlRequest):
    get_dl(dl_id)
    check_url(req.url)
    try:
        await manager.refresh_address(dl_id, req.url.strip())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/downloads/{dl_id}/move-to-queue")
async def move_to_queue(dl_id: str):
    dl = get_dl(dl_id)
    if dl.status != "completed":
        if dl.status == "downloading" and not manager.queue_running:
            await manager.pause(dl_id)
        dl.later = True
        if dl.status in ("paused", "error"):
            dl.status, dl.error = "queued", ""
        manager.save(force=True)
    return {"ok": True}


@app.post("/api/downloads/{dl_id}/open-window")
async def open_progress_window(dl_id: str):
    get_dl(dl_id)
    manager.open_window(f"/w?view=progress&id={dl_id}", 520, 430)
    return {"ok": True}


@app.post("/api/downloads/{dl_id}/description")
async def set_description(dl_id: str, req: UrlRequest):
    dl = get_dl(dl_id)
    dl.description = req.url[:200]
    manager.save(force=True)
    return {"ok": True}


@app.post("/api/bulk/{action}")
async def bulk(action: str, req: IdsRequest):
    ids = req.ids or [d.id for d in manager.downloads.values() if d.status != "pending"]
    for i in ids:
        dl = manager.downloads.get(i)
        if not dl:
            continue
        if action == "pause" and dl.status in ("downloading", "queued"):
            await manager.pause(i)
        elif action == "resume" and dl.status in ("paused", "error"):
            manager.resume(i)
        elif action == "delete":
            await manager.remove(i, req.delete_file)
        elif action == "clear-completed" and dl.status == "completed":
            await manager.remove(i)
    return {"ok": True}


@app.delete("/api/downloads/{dl_id}")
async def delete(dl_id: str, delete_file: bool = False):
    get_dl(dl_id)
    await manager.remove(dl_id, delete_file)
    return {"ok": True}


def _reveal(path: Path, select: bool):
    system = platform.system()
    if system == "Windows":
        if select and path.exists():
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            os.startfile(str(path if path.exists() else path.parent))  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.Popen(["open", "-R", str(path)] if select else ["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent if select else path)])


@app.post("/api/downloads/{dl_id}/open")
async def open_file(dl_id: str, folder: bool = False):
    dl = get_dl(dl_id)
    p = Path(dl.path) if dl.path else Path(manager.settings["download_dir"])
    if not p.exists() and not folder:
        raise HTTPException(404, "Fichier pas encore disponible")
    if folder and not p.exists():
        p = p.parent
        p.mkdir(parents=True, exist_ok=True)
        _reveal(p, select=False)
    else:
        _reveal(p, select=folder)
    return {"ok": True}


@app.post("/api/open-folder")
async def open_folder(req: UrlRequest):
    p = Path(req.url or manager.settings["download_dir"])
    p.mkdir(parents=True, exist_ok=True)
    _reveal(p, select=False)
    return {"ok": True}


# ---------- file d'attente / planificateur ----------
@app.post("/api/queue/start")
async def queue_start():
    manager.start_queue()
    return {"ok": True}


@app.post("/api/queue/stop")
async def queue_stop():
    await manager.stop_queue()
    return {"ok": True}


@app.post("/api/power/cancel")
async def power_cancel():
    manager.cancel_power()
    return {"ok": True}


# ---------- reglages ----------
@app.get("/api/settings")
async def get_settings():
    return {**manager.settings, "ffmpeg_found": manager.ffmpeg() or "", "windows": IS_WINDOWS}


@app.put("/api/settings")
async def put_settings(req: SettingsRequest):
    data = req.model_dump(exclude_none=True)
    sched = data.pop("schedule", None)
    if "capture_exts" in data:
        data["capture_exts"] = sorted({e.strip().lower().lstrip(".") for e in data["capture_exts"] if e.strip()})
    manager.settings.update(data)
    if sched:
        manager.settings["schedule"].update(sched)
    Path(manager.settings["download_dir"]).mkdir(parents=True, exist_ok=True)
    manager.save_settings()
    manager.wake()
    return await get_settings()


# ---------- lancement ----------
def run_tray(server):
    """Icone dans la barre des taches (zone de notification)."""
    try:
        import pystray
        from PIL import Image
    except ImportError:
        return None
    import webbrowser

    def open_ui(*_):
        webbrowser.open(f"http://localhost:{PORT}")

    def pause_all(*_):
        import asyncio
        asyncio.run_coroutine_threadsafe(bulk("pause", IdsRequest()), manager.loop)

    def resume_all(*_):
        manager.loop.call_soon_threadsafe(lambda: [manager.resume(d.id) for d in list(manager.downloads.values())
                                                   if d.status in ("paused", "error")])

    def toggle_clip(icon, item):
        manager.settings["monitor_clipboard"] = not manager.settings.get("monitor_clipboard")
        manager.save_settings()

    def quit_app(icon, *_):
        icon.stop()
        server.should_exit = True

    icon = pystray.Icon(
        "Rapido", Image.open(BASE / "extension" / "icon128.png"), "Rapido",
        menu=pystray.Menu(
            pystray.MenuItem("Ouvrir Rapido", open_ui, default=True),
            pystray.MenuItem("Tout reprendre", resume_all),
            pystray.MenuItem("Tout mettre en pause", pause_all),
            pystray.MenuItem("Surveiller le presse-papiers", toggle_clip,
                             checked=lambda i: bool(manager.settings.get("monitor_clipboard"))),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quitter", quit_app),
        ),
    )
    threading.Thread(target=icon.run, daemon=True).start()
    return icon


if __name__ == "__main__":
    import uvicorn

    if sys.stdout is None or sys.stderr is None:   # lance via pythonw (sans console)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        log = open(DATA_DIR / "rapido.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log

    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT, log_level="warning"))
    manager.on_exit = lambda: setattr(server, "should_exit", True)
    tray = run_tray(server) if IS_WINDOWS or os.environ.get("RAPIDO_TRAY") else None
    print(f"\n  Rapido tourne sur http://localhost:{PORT}\n")
    try:
        server.run()
    finally:
        if tray:
            tray.stop()
