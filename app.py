"""
Rapido - serveur local (API + interface).

  * Application Windows : lance desktop.py (ou Rapido.exe), qui demarre ce serveur
    en arriere-plan et l'affiche dans une vraie fenetre.
  * Mode developpement : python app.py   puis ouvre http://localhost:9614
"""

from __future__ import annotations

import asyncio
import json
import re
import urllib.request
import os
import platform
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from typing import Annotated

from pydantic import BaseModel, Field

from engine import (Manager, IS_WINDOWS, VERSION, FROZEN, RES_DIR, EXE_DIR,
                    CREATE_NEW_CONSOLE)

HOST = "127.0.0.1"      # uniquement accessible depuis ton PC
PORT = 9614
BASE = RES_DIR
DATA_DIR = Path(os.environ.get("RAPIDO_DATA", Path.home() / ".rapido"))

manager = Manager(DATA_DIR, PORT)

# Rempli par desktop.py quand Rapido tourne comme application Windows
UI = {"desktop": False, "show_main": None, "window_action": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await manager.start()
    yield
    await manager.stop()


app = FastAPI(title="Rapido", lifespan=lifespan)

# S2: all API data and mutations require this process-local authorization.
# Native WebView2 request interception and in-process dispatch supply it; never HTML.
from local_auth import LocalAuth
_LOCAL_AUTH = LocalAuth()


# ---------- securite de l'API locale ----------
# L'API peut ecrire des fichiers sur le disque : seuls l'interface de Rapido et SA propre
# extension Chrome doivent pouvoir l'utiliser, jamais un site web ouvert dans le navigateur.
#
#  1. Host verifie        -> bloque le "DNS rebinding" (site.com qui pointe vers 127.0.0.1)
#  2. Origin verifie      -> bloque les autres sites et les autres extensions
#  3. JSON obligatoire    -> un formulaire HTML ou un fetch "simple" ne peut pas ecrire
#  4. CORS limite a l'extension Rapido (identifiant fixe grace a la cle du manifest)
EXTENSION_ID = "hlpkfnodjoglfdiekijebbppfgkjkbmp"
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
EXTENSION_ORIGIN = f"chrome-extension://{EXTENSION_ID}"
ALLOWED_ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}", EXTENSION_ORIGIN}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"chrome-extension://{EXTENSION_ID}"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


def _deny(status: int, detail: str):
    return JSONResponse({"detail": detail}, status_code=status, headers=SECURITY_HEADERS)


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.headers.get("host", "").lower() not in ALLOWED_HOSTS:
        return _deny(403, "Hote non autorise")
    origin = request.headers.get("origin")
    if origin is not None and origin not in ALLOWED_ORIGINS:
        return _deny(403, "Origine non autorisee")
    # Une page ou une requete declenchee par un AUTRE site (meme sur 127.0.0.1 avec un autre
    # port) est refusee : le navigateur l'annonce dans Sec-Fetch-Site. Seuls passent l'interface
    # de Rapido elle-meme (same-origin), une adresse tapee / une fenetre ouverte par Rapido (none),
    # l'extension Rapido, et les programmes sans navigateur (pas d'en-tete).
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site and fetch_site not in ("same-origin", "none") and origin != EXTENSION_ORIGIN:
        return _deny(403, "Requete venant d'un autre site refusee")
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        ctype = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if ctype != "application/json":
            return _deny(415, "Content-Type application/json requis")
    if (request.url.path.startswith("/api/") and request.url.path != "/api/ping" and
            not _LOCAL_AUTH.header_is_authorized(request.headers.get("authorization"))):
        return _deny(403, "Authentification native requise : utilise l'application Rapido")
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def _html_page(name: str):
    """Sert une page avec une Content-Security-Policy stricte : seuls les scripts de
    Rapido (identifies par leur empreinte SHA-256) peuvent s'executer, et la page ne
    peut contacter que Rapido. Une injection HTML ne pourrait donc ni executer de
    code, ni envoyer de donnees ailleurs."""
    import base64
    import hashlib
    import re
    from fastapi.responses import HTMLResponse
    html = (BASE / name).read_text("utf-8")
    hashes = " ".join(
        "'sha256-" + base64.b64encode(hashlib.sha256(js.encode("utf-8")).digest()).decode() + "'"
        for js in re.findall(r"<script>(.*?)</script>", html, re.S)
    )
    csp = ("default-src 'none'; "
           f"script-src {hashes}; "
           "style-src 'self' 'unsafe-inline'; "
           "img-src 'self' data: https: http:; "
           "connect-src 'self'; "
           "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
    return lambda: HTMLResponse(html, headers={"Content-Security-Policy": csp, "Cache-Control": "no-store"})


_INDEX = _html_page("index.html")
_WINDOW = _html_page("window.html")


# ---------- modeles (avec limites de taille : rien d'enorme ne rentre) ----------
Url = Annotated[str, Field(min_length=8, max_length=8192)]
Headers = Annotated[dict[str, Annotated[str, Field(max_length=16384)]], Field(max_length=10)]
Name = Annotated[str, Field(max_length=255)]
PathStr = Annotated[str, Field(max_length=1024)]


class AddRequest(BaseModel):
    url: Annotated[str, Field(min_length=8, max_length=200_000)]   # plusieurs liens, un par ligne
    filename: Name | None = None
    connections: int | None = Field(default=None, ge=1, le=32)
    headers: Headers | None = None
    later: bool = False


class CaptureRequest(BaseModel):
    url: Url
    headers: Headers | None = None
    filename: Name | None = None
    open_window: bool = False     # True = le serveur ouvre lui-meme la fenetre de capture


class VideoCaptureRequest(BaseModel):
    page_url: Url
    candidates: Annotated[list[Url], Field(max_length=15)] = []
    headers: Headers | None = None
    open_window: bool = False


class ConfirmRequest(BaseModel):
    filename: Name | None = None
    folder: PathStr | None = None
    later: bool = False
    description: Annotated[str, Field(max_length=200)] = ""
    format_id: Annotated[str, Field(max_length=20)] | None = None


class WindowRequest(BaseModel):
    view: str = Field(pattern=r"^(capture|progress)$")
    id: str = Field(pattern=r"^[0-9a-f]{6,32}$")
    width: int = Field(default=540, ge=300, le=1200)
    height: int = Field(default=460, ge=200, le=1000)


class WindowActionRequest(BaseModel):
    token: str = Field(pattern=r"^[0-9a-f]{16,64}$")     # identifiant secret de la fenetre
    action: str = Field(pattern=r"^(close|resize)$")
    width: int = Field(default=520, ge=300, le=1200)
    height: int = Field(default=460, ge=200, le=1000)


class UrlRequest(BaseModel):
    url: Annotated[str, Field(max_length=8192)]


class IdsRequest(BaseModel):
    ids: Annotated[list[Annotated[str, Field(max_length=32)]], Field(max_length=10_000)] = []
    all: bool = False          # agir sur toute la liste : doit etre demande explicitement
    delete_file: bool = False


class Schedule(BaseModel):
    enabled: bool | None = None
    start: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    stop: str | None = Field(default=None, pattern=r"^(([01]\d|2[0-3]):[0-5]\d)?$")
    days: Annotated[list[Annotated[int, Field(ge=0, le=6)]], Field(max_length=7)] | None = None
    on_complete: str | None = Field(default=None, pattern=r"^(none|shutdown|sleep|exit)$")


class SettingsRequest(BaseModel):
    download_dir: PathStr | None = None
    max_concurrent: int | None = Field(default=None, ge=1, le=10)
    connections: int | None = Field(default=None, ge=1, le=32)
    sort_by_category: bool | None = None
    speed_limit_kbps: int | None = Field(default=None, ge=0, le=10_000_000)
    show_capture_dialog: bool | None = None
    show_progress_window: bool | None = None
    show_complete_dialog: bool | None = None
    monitor_clipboard: bool | None = None
    capture_exts: Annotated[list[Annotated[str, Field(max_length=10)]], Field(max_length=200)] | None = None
    min_capture_kb: int | None = Field(default=None, ge=0, le=10_000_000)
    ffmpeg_path: PathStr | None = None
    browser_path: PathStr | None = None
    schedule: Schedule | None = None
    autostart: bool | None = None


# Rapido lance ces programmes : on n'accepte que de vrais ffmpeg / navigateurs existants
FFMPEG_NAMES = {"ffmpeg", "ffmpeg.exe"}
BROWSER_NAMES = {"chrome.exe", "msedge.exe", "brave.exe", "chromium.exe", "vivaldi.exe",
                 "chrome", "chromium", "chromium-browser", "google-chrome", "microsoft-edge", "brave-browser"}


def check_program(path: str, names: set[str], label: str) -> str:
    if not path:
        return ""
    p = Path(path).expanduser()
    if not p.is_absolute() or not p.is_file() or p.name.lower() not in names:
        raise HTTPException(400, f"{label} : indique le chemin complet d'un fichier existant "
                                 f"({', '.join(sorted(n for n in names if n.endswith('.exe') or not IS_WINDOWS))})")
    return str(p)


def check_folder(path: str, label: str) -> str:
    p = Path(path).expanduser()
    if not p.is_absolute():
        raise HTTPException(400, f"{label} : indique un chemin complet (ex. C:\\Users\\toi\\Downloads)")
    if p.exists() and not p.is_dir():
        raise HTTPException(400, f"{label} : ce chemin est un fichier, pas un dossier")
    return str(p)


def get_dl(dl_id: str):
    dl = manager.downloads.get(dl_id)
    if not dl:
        raise HTTPException(404, "Telechargement introuvable")
    return dl


def check_url(u: str):
    from urllib.parse import urlsplit
    try:
        parts = urlsplit(u)
    except ValueError:
        raise HTTPException(400, "URL invalide")
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise HTTPException(400, "URL http(s) invalide")


# ---------- pages ----------
@app.get("/")
async def index():
    return _INDEX()


@app.get("/w")
async def window_page():
    """Petites fenetres : capture, video, progression / termine."""
    return _WINDOW()


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




def native_dispatch(role: str, data: dict):
    """Called only after the named-pipe transport verifies the actual OS peer.

    Native host authority is deliberately smaller than the desktop API:
    no arbitrary routes, headers, file operations or bearer retrieval.
    """
    from native_protocol import public_capture
    kind = data.get("type")
    if role == "desktop" and data == {"type":"show"}:
        if UI["show_main"]:
            UI["show_main"]()
        return {"ok": bool(UI["desktop"])}
    if role != "native":
        raise ValueError("Unknown native role")
    if data == {"type":"capabilities"}:
        return {"type":"capabilities", "protocol":1,
                "features":["ping","capture_public","settings_public","capture_handoff"]}
    if data == {"type":"settings_public"}:
        return {"type":"settings_public",
                "capture_exts": list(manager.settings.get("capture_exts", [])),
                "min_capture_kb": manager.settings.get("min_capture_kb", 512)}
    if kind in ("capture_prepare","capture_commit","capture_abort"):
        from native_handoff import dispatch
        return asyncio.run_coroutine_threadsafe(dispatch(manager,data), manager.loop).result(timeout=4)
    if kind != "capture_public":
        raise ValueError("Unsupported native request")
    value = public_capture(data)
    headers = {"Referer":value["referrer"]} if value["referrer"] else {}
    request = CaptureRequest(url=value["url"], filename=value["filename"],
                             headers=headers, open_window=True)
    result = asyncio.run_coroutine_threadsafe(capture(request), manager.loop).result(timeout=4)
    return {"type":"capture_result","ok": isinstance(result,dict) and isinstance(result.get("id"),str)}


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


@app.post("/api/native/capture")
async def capture_native(req: CaptureRequest, request: Request):
    """Authenticated native-only entrypoint; legacy routes are guarded too."""
    # Native-only entrypoint: reject browser-originated requests even when a token is supplied.
    # These headers alone are not an authentication mechanism; the bearer secret is required.
    if (request.headers.get("origin") is not None or
            request.headers.get("sec-fetch-site") is not None):
        raise HTTPException(status_code=403, detail="Route reservee au transport natif")
    if not _LOCAL_AUTH.header_is_authorized(request.headers.get("authorization")):
        raise HTTPException(status_code=403, detail="Autorisation native requise")
    return await capture(req)


@app.post("/api/capture")
async def capture(req: CaptureRequest):
    """Appele par l'extension : cree un telechargement 'en attente de confirmation'."""
    check_url(req.url)
    if not manager.settings.get("show_capture_dialog", True):
        dl = manager.add(req.url, req.filename, None, req.headers)
        if manager.settings.get("show_progress_window") and req.open_window:
            manager.open_window(f"/w?view=progress&id={dl.id}", 520, 480)
        return {"id": dl.id, "dialog": False}
    dl = manager.capture(req.url, req.headers, req.filename)
    if req.open_window:
        manager.open_window(f"/w?view=capture&id={dl.id}", 560, 580)
    return {"id": dl.id, "dialog": True}


@app.post("/api/capture-video")
async def capture_video(req: VideoCaptureRequest):
    check_url(req.page_url)
    candidates = []
    for c in req.candidates:          # flux detectes par l'extension : http(s) uniquement
        try:
            check_url(c)
            candidates.append(c)
        except HTTPException:
            pass
    dl = manager.capture_video(req.page_url, candidates, req.headers)
    if req.open_window:
        manager.open_window(f"/w?view=capture&id={dl.id}", 560, 620)
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
        req.folder = check_folder(req.folder, "Dossier")
        try:
            Path(req.folder).mkdir(parents=True, exist_ok=True)
        except OSError:
            raise HTTPException(400, "Impossible de creer ce dossier")
    manager.confirm(dl_id, req.filename, req.folder, req.later, req.description)
    return dl.to_public()


@app.post("/api/downloads/{dl_id}/cancel-capture")
async def cancel_capture(dl_id: str):
    dl = manager.downloads.get(dl_id)
    if dl and dl.status == "pending":
        await manager.remove(dl_id)
    return {"ok": True}


# ---------- actions ----------
@app.post("/api/downloads/{dl_id}/recover-handoff")
async def recover_handoff(dl_id: str):
    from native_handoff import activate
    dl = get_dl(dl_id)
    if dl.status != "handoff":
        raise HTTPException(409, "Ce transfert est deja traite")
    return activate(manager, dl)


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
    manager.open_window(f"/w?view=progress&id={dl_id}", 520, 480)
    return {"ok": True}


@app.post("/api/downloads/{dl_id}/description")
async def set_description(dl_id: str, req: UrlRequest):
    dl = get_dl(dl_id)
    dl.description = req.url[:200]
    manager.save(force=True)
    return {"ok": True}


@app.post("/api/bulk/{action}")
async def bulk(action: str, req: IdsRequest):
    if req.all:
        if action == "delete":
            raise HTTPException(400, "Suppression de toute la liste refusee : indique les elements")
        ids = [d.id for d in manager.downloads.values() if d.status != "pending"]
    else:
        ids = req.ids          # liste vide = rien (jamais « tout » par defaut)
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
    """Ouvre un fichier ou un dossier avec Windows. Si l'utilisateur annule (par exemple la
    demande d'autorisation de Windows pour un programme), ce n'est pas une erreur."""
    system = platform.system()
    try:
        if system == "Windows":
            if select and path.exists():
                subprocess.Popen(["explorer", "/select,", str(path)])
            else:
                os.startfile(str(path if path.exists() else path.parent))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", "-R", str(path)] if select else ["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent if select else path)])
    except OSError as e:
        if getattr(e, "winerror", None) == 1223:      # ERROR_CANCELLED : annule par l'utilisateur
            return
        raise HTTPException(400, f"Impossible d'ouvrir : {e.strerror or e}")


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
    # n'ouvre QUE le dossier de telechargement (jamais un chemin fourni par la requete,
    # qui pourrait designer un programme a executer)
    p = Path(manager.settings["download_dir"])
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
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_command() -> str:
    if FROZEN:
        return f'"{sys.executable}" --tray'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pyw if pyw.exists() else sys.executable}" "{Path(__file__).with_name("desktop.py")}" --tray'


def get_autostart() -> bool:
    if not IS_WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, "Rapido")
            return True
    except OSError:
        return False


def set_autostart(on: bool):
    if not IS_WINDOWS:
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
        if on:
            winreg.SetValueEx(k, "Rapido", 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, "Rapido")
            except OSError:
                pass


def extension_dir() -> Path:
    p = EXE_DIR / "extension"
    return p if p.exists() else RES_DIR / "extension"


@app.get("/api/settings")
async def get_settings():
    return {**manager.settings, "ffmpeg_found": manager.ffmpeg() or "", "deno_found": manager.deno() or "",
            "windows": IS_WINDOWS,
            "desktop": UI["desktop"], "autostart": get_autostart(), "version": VERSION,
            "extension_dir": str(extension_dir())}


def _latest_rapido_release():
    """Read only the official Rapido GitHub release metadata."""
    request = urllib.request.Request(
        "https://api.github.com/repos/shimon3/rapido/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Rapido-update-check"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        payload = json.load(response)
    tag = str(payload.get("tag_name", ""))
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag)
    if not match:
        raise ValueError("Version distante non reconnue")
    version = ".".join(match.groups())
    installer = next((asset.get("browser_download_url") for asset in payload.get("assets", [])
                      if re.fullmatch(r"Rapido-Setup-\d+\.\d+\.\d+\.exe",
                                      asset.get("name", ""))), None)
    release_url = f"https://github.com/shimon3/rapido/releases/tag/{tag}"
    return version, installer or release_url


@app.get("/api/updates/check")
async def check_updates():
    """Compare semantic numeric versions without installing or interrupting downloads."""
    try:
        latest, url = await asyncio.to_thread(_latest_rapido_release)
    except Exception:
        raise HTTPException(status_code=502, detail="Impossible de vérifier les mises à jour GitHub")
    def numbers(value: str):
        match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
        return tuple(map(int, match.groups())) if match else None
    current = numbers(VERSION)
    remote = numbers(latest)
    if current is None or remote is None:
        raise HTTPException(status_code=502, detail="Format de version inconnu")
    return {"current": VERSION, "latest": latest, "update_available": remote > current, "url": url}


@app.put("/api/settings")
async def put_settings(req: SettingsRequest):
    data = req.model_dump(exclude_none=True)
    sched = data.pop("schedule", None)
    autostart = data.pop("autostart", None)
    if "download_dir" in data:
        data["download_dir"] = check_folder(data["download_dir"], "Dossier de telechargement")
    if "ffmpeg_path" in data:
        data["ffmpeg_path"] = check_program(data["ffmpeg_path"], FFMPEG_NAMES, "ffmpeg")
    if "browser_path" in data:
        data["browser_path"] = check_program(data["browser_path"], BROWSER_NAMES, "Navigateur")
    if "capture_exts" in data:
        import re as _re
        data["capture_exts"] = sorted({e.strip().lower().lstrip(".") for e in data["capture_exts"]
                                       if _re.fullmatch(r"\.?[a-z0-9]{1,8}", e.strip().lower())})
    manager.settings.update(data)
    if sched:
        manager.settings["schedule"].update(sched)
    if autostart is not None:
        try:
            set_autostart(autostart)
        except OSError as e:
            raise HTTPException(500, f"Impossible de modifier le demarrage automatique : {e}")
    Path(manager.settings["download_dir"]).mkdir(parents=True, exist_ok=True)
    manager.save_settings()
    manager.wake()
    return await get_settings()


# ---------- fenetres et outils ----------
@app.post("/api/window")
async def open_window(req: WindowRequest):
    """Ouvre une petite fenetre (capture / progression) : native dans l'application Windows."""
    manager.open_window(f"/w?view={req.view}&id={req.id}", req.width, req.height)
    return {"ok": True}


@app.post("/api/window-action")
async def window_action(req: WindowActionRequest):
    """Fermer / redimensionner une petite fenetre native (remplace le pont JavaScript de
    pywebview, incompatible avec la Content-Security-Policy stricte)."""
    if not UI["window_action"]:
        return {"ok": False}
    return {"ok": bool(UI["window_action"](req.token, req.action, req.width, req.height))}


@app.post("/api/show")
async def show_main():
    """Ramene la fenetre principale au premier plan (2e lancement de Rapido.exe)."""
    if UI["show_main"]:
        UI["show_main"]()
    return {"ok": UI["desktop"]}


@app.post("/api/tools/ffmpeg")
async def install_ffmpeg():
    if not IS_WINDOWS:
        raise HTTPException(400, "Uniquement sous Windows")
    cmd = ("echo Installation de ffmpeg pour Rapido... & echo. & "
           "winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements & "
           "echo. & echo Termine : tu peux fermer cette fenetre. & pause")
    subprocess.Popen(["cmd", "/c", cmd], creationflags=CREATE_NEW_CONSOLE)
    return {"ok": True}


@app.post("/api/tools/deno")
async def install_deno():
    """Deno = moteur JavaScript dont yt-dlp a besoin pour toutes les qualites YouTube."""
    if not IS_WINDOWS:
        raise HTTPException(400, "Uniquement sous Windows")
    cmd = ("echo Installation de Deno pour Rapido (qualites YouTube completes)... & echo. & "
           "winget install -e --id DenoLand.Deno --accept-source-agreements --accept-package-agreements & "
           "echo. & echo Termine : tu peux fermer cette fenetre. & pause")
    subprocess.Popen(["cmd", "/c", cmd], creationflags=CREATE_NEW_CONSOLE)
    return {"ok": True}


@app.post("/api/tools/extension")
async def extension_help():
    """Ouvre le dossier de l'extension dans l'Explorateur.
    (On n'ouvre plus chrome://extensions nous-memes : Chrome refuse les adresses chrome://
    transmises par un autre programme, il s'ouvrait puis se refermait. L'interface guide
    l'utilisateur pas a pas a la place.)"""
    _reveal(extension_dir(), select=False)
    return {"ok": True, "path": str(extension_dir())}


# ---------- lancement ----------
def run_tray(on_open, on_quit):
    """Icone dans la zone de notification (a cote de l'horloge)."""
    try:
        import pystray
        from PIL import Image
    except ImportError:
        return None

    def pause_all(*_):
        import asyncio
        asyncio.run_coroutine_threadsafe(bulk("pause", IdsRequest(all=True)), manager.loop)

    def resume_all(*_):
        manager.loop.call_soon_threadsafe(lambda: [manager.resume(d.id) for d in list(manager.downloads.values())
                                                   if d.status in ("paused", "error")])

    def toggle_clip(icon, item):
        manager.settings["monitor_clipboard"] = not manager.settings.get("monitor_clipboard")
        manager.save_settings()

    def quit_app(icon, *_):
        icon.stop()
        on_quit()

    icon = pystray.Icon(
        "Rapido", Image.open(BASE / "extension" / "icon128.png"), "Rapido",
        menu=pystray.Menu(
            pystray.MenuItem("Ouvrir Rapido", lambda *_: on_open(), default=True),
            pystray.MenuItem("Tout reprendre", resume_all),
            pystray.MenuItem("Tout mettre en pause", pause_all),
            pystray.MenuItem("Surveiller le presse-papiers", toggle_clip,
                             checked=lambda i: bool(manager.settings.get("monitor_clipboard"))),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quitter Rapido", quit_app),
        ),
    )
    icon.run_detached()
    return icon


if __name__ == "__main__":
    import uvicorn

    if sys.stdout is None or sys.stderr is None:   # lance via pythonw (sans console)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        log = open(DATA_DIR / "rapido.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log

    import webbrowser
    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT, log_level="warning"))
    manager.on_exit = lambda: setattr(server, "should_exit", True)
    tray = (run_tray(lambda: webbrowser.open(f"http://localhost:{PORT}"),
                     lambda: setattr(server, "should_exit", True))
            if IS_WINDOWS or os.environ.get("RAPIDO_TRAY") else None)
    print(f"\n  Rapido tourne sur http://localhost:{PORT}\n")
    try:
        server.run()
    finally:
        if tray:
            tray.stop()
