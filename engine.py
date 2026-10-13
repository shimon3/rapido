"""
Rapido - moteur de telechargement.

  * Fichiers classiques : multi-connexions (requetes Range), reprise apres pause,
    coupure ou redemarrage, redecoupage dynamique des segments.
  * Videos (YouTube, sites de streaming, flux .m3u8 / .mpd) : via yt-dlp.
  * File d'attente + planificateur (heure de debut / fin, action en fin de file).
  * Surveillance du presse-papiers (Windows).
  * Ouverture de petites fenetres (capture, progression) via Chrome / Edge en mode --app.
"""

from __future__ import annotations

import asyncio
import ctypes
import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field, asdict
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

CHUNK = 256 * 1024            # taille des blocs lus sur le reseau
MIN_SEGMENT = 1024 * 1024     # on ne decoupe pas en morceaux de moins de 1 Mo
MAX_RETRIES = 5               # echecs consecutifs (sans progression) avant abandon
SAVE_EVERY = 2.0              # secondes entre deux sauvegardes de l'etat
PENDING_TTL = 30 * 60         # une capture non confirmee disparait apres 30 min
IS_WINDOWS = platform.system() == "Windows"
VERSION = "1.1.0"
FROZEN = getattr(sys, "frozen", False)                       # True dans Rapido.exe (PyInstaller)
RES_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))   # fichiers embarques (html, icone)
EXE_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).parent
CREATE_NEW_CONSOLE = 0x00000010
CREATE_NO_WINDOW = 0x08000000

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)

CATEGORIES = {
    "Vidéos": {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".flv", ".m4v", ".ts", ".3gp", ".mpg", ".mpeg"},
    "Musique": {".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".wma", ".opus"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".img", ".tgz"},
    "Programmes": {".exe", ".msi", ".msix", ".apk", ".dmg", ".deb", ".rpm", ".appx", ".bin"},
    "Documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".epub", ".odt"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff"},
}
DEFAULT_CAPTURE_EXTS = sorted(
    e.lstrip(".") for cat, exts in CATEGORIES.items() if cat != "Images" for e in exts
    if e not in {".txt", ".csv", ".svg"}
)


def category_for(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return "Autres"


def safe_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name[:180] or "telechargement"


def filename_from_headers(headers: httpx.Headers, url: str) -> str:
    cd = headers.get("content-disposition", "")
    m = re.search(r"filename\*\s*=\s*[^']*''([^;]+)", cd, re.I)
    if m:
        return safe_filename(unquote(m.group(1).strip('" ')))
    m = re.search(r'filename\s*=\s*"?([^";]+)"?', cd, re.I)
    if m:
        return safe_filename(m.group(1).strip())
    path = unquote(urlparse(url).path)
    base = path.rstrip("/").split("/")[-1]
    return safe_filename(base) if base else "telechargement"


def unique_path(folder: Path, filename: str) -> Path:
    """Evite d'ecraser un fichier existant : fichier.zip -> fichier (1).zip"""
    p = folder / filename
    stem, suffix, i = p.stem, p.suffix, 1
    while p.exists() or p.with_name(p.name + ".part").exists():
        p = folder / f"{stem} ({i}){suffix}"
        i += 1
    return p


def url_ext(url: str) -> str:
    return Path(unquote(urlparse(url).path)).suffix.lower().lstrip(".")


@dataclass
class Segment:
    start: int
    end: int          # inclus ; -1 = taille inconnue (flux unique)
    done: int = 0     # octets deja ecrits pour ce segment

    @property
    def remaining(self) -> int:
        return -1 if self.end < 0 else (self.end - self.start + 1) - self.done

    @property
    def finished(self) -> bool:
        return self.end >= 0 and self.remaining <= 0


@dataclass
class Download:
    id: str
    url: str
    kind: str = "http"          # http | video
    filename: str = ""
    folder: str = ""            # dossier choisi dans la fenetre de capture ("" = defaut)
    path: str = ""              # chemin final
    size: int = -1              # -1 = inconnue
    resumable: bool = False
    connections: int = 8
    status: str = "queued"      # pending | queued | downloading | paused | completed | error
    later: bool = False         # dans la file d'attente (attend le planificateur / "Demarrer la file")
    error: str = ""
    description: str = ""
    segments: list[Segment] = field(default_factory=list)
    headers: dict = field(default_factory=dict)   # cookies / referer envoyes par l'extension
    created: float = field(default_factory=time.time)
    last_try: float = 0
    finished_at: float = 0
    category: str = "Autres"
    # capture / analyse
    probe: str = ""             # "" | probing | ready | failed
    probe_error: str = ""
    # video (yt-dlp)
    page_url: str = ""
    candidates: list = field(default_factory=list)  # flux detectes par l'extension (m3u8, mp4...)
    title: str = ""
    thumbnail: str = ""
    duration: int = 0
    formats: list = field(default_factory=list)     # options de qualite proposees
    video_format: str = ""
    v_base: int = 0             # octets des flux deja termines (video puis audio)
    v_done: int = 0             # octets du flux en cours
    # valeurs calculees (non sauvegardees)
    speed: float = 0
    active_connections: int = 0
    watched: float = 0          # derniere fois qu'une fenetre de progression a regarde ce telechargement

    @property
    def downloaded(self) -> int:
        if self.kind == "video":
            return self.v_base + self.v_done
        return sum(s.done for s in self.segments)

    def to_public(self) -> dict:
        d = asdict(self)
        d["downloaded"] = self.downloaded
        d.pop("headers", None)
        d["segments"] = [{"start": s.start, "end": s.end, "done": s.done} for s in self.segments]
        eta = -1
        if self.size > 0 and self.speed > 0:
            eta = max(0, int((self.size - self.downloaded) / self.speed))
        d["eta"] = eta
        return d

    def to_disk(self) -> dict:
        d = asdict(self)
        for k in ("speed", "active_connections", "watched"):
            d.pop(k, None)
        return d

    @classmethod
    def from_disk(cls, d: dict) -> "Download":
        segs = [Segment(**s) for s in d.pop("segments", [])]
        dl = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        dl.segments = segs
        if dl.status == "downloading":     # le programme a ete ferme en plein telechargement
            dl.status = "queued"
        if dl.probe == "probing":
            dl.probe = ""
        return dl


class StopVideo(Exception):
    pass


class Manager:
    def __init__(self, data_dir: Path, port: int = 9614):
        self.port = port
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = data_dir / "downloads.json"
        self.settings_file = data_dir / "settings.json"
        self.settings = {
            "download_dir": str(Path.home() / "Downloads" / "Rapido"),
            "max_concurrent": 3,
            "connections": 8,
            "sort_by_category": True,
            "speed_limit_kbps": 0,           # 0 = illimite
            "show_capture_dialog": True,     # fenetre "Informations sur le fichier" a chaque capture
            "show_progress_window": True,    # fenetre de progression apres "Demarrer"
            "show_complete_dialog": True,    # fenetre "Telechargement termine"
            "monitor_clipboard": True,
            "capture_exts": DEFAULT_CAPTURE_EXTS,
            "min_capture_kb": 512,
            "ffmpeg_path": "",
            "browser_path": "",
            "schedule": {
                "enabled": False,
                "start": "02:00",
                "stop": "",
                "days": [0, 1, 2, 3, 4, 5, 6],   # 0 = lundi
                "on_complete": "none",           # none | shutdown | sleep | exit
            },
        }
        self.downloads: dict[str, Download] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self._probes: dict[str, asyncio.Task] = {}
        self._stop_flags: dict[str, threading.Event] = {}
        self._last_save = 0.0
        self._wake = asyncio.Event()
        self._rate_bucket = 0.0
        self._rate_ts = time.monotonic()
        self.client: httpx.AsyncClient | None = None
        self.queue_running = False
        self._queue_did_work = False
        self._last_sched_minute = ""
        self.power: dict | None = None   # action d'alimentation programmee (arret / veille)
        self.on_exit = None              # callback pour quitter l'application
        self.loop: asyncio.AbstractEventLoop | None = None
        self._clip_last = ""
        self._load()

    # ---------- persistance ----------
    def _load(self):
        if self.settings_file.exists():
            try:
                saved = json.loads(self.settings_file.read_text("utf-8"))
                sched = {**self.settings["schedule"], **saved.pop("schedule", {})}
                self.settings.update(saved)
                self.settings["schedule"] = sched
            except Exception:
                pass
        if self.state_file.exists():
            try:
                for d in json.loads(self.state_file.read_text("utf-8")):
                    dl = Download.from_disk(d)
                    self.downloads[dl.id] = dl
            except Exception:
                pass

    def save(self, force: bool = False):
        now = time.monotonic()
        if not force and now - self._last_save < SAVE_EVERY:
            return
        self._last_save = now
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([d.to_disk() for d in self.downloads.values()], ensure_ascii=False, indent=1),
            "utf-8",
        )
        os.replace(tmp, self.state_file)

    def save_settings(self):
        self.settings_file.write_text(json.dumps(self.settings, indent=2, ensure_ascii=False), "utf-8")

    # ---------- cycle de vie ----------
    async def start(self):
        self.loop = asyncio.get_running_loop()
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, read=60.0),
            headers={"User-Agent": USER_AGENT},
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
        )
        self._scheduler = asyncio.create_task(self._schedule_loop())
        if IS_WINDOWS:
            threading.Thread(target=self._clipboard_loop, daemon=True).start()

    async def stop(self):
        for dl_id in list(self.tasks):
            await self._cancel_task(dl_id)
        for dl in self.downloads.values():
            if dl.status == "downloading":
                dl.status = "queued"
        self.save(force=True)
        self._scheduler.cancel()
        if self.client:
            await self.client.aclose()

    def wake(self):
        self._wake.set()

    def _eligible(self, dl: Download) -> bool:
        return dl.status == "queued" and (not dl.later or self.queue_running)

    async def _schedule_loop(self):
        """Lance les telechargements en attente sans depasser max_concurrent + planificateur."""
        while True:
            try:
                self._check_schedule()
                running = [i for i, t in self.tasks.items() if not t.done()]
                free = int(self.settings["max_concurrent"]) - len(running)
                if free > 0:
                    waiting = sorted(
                        (d for d in self.downloads.values() if self._eligible(d) and d.id not in running),
                        key=lambda d: d.created,
                    )
                    for dl in waiting[:free]:
                        dl.status = "downloading"
                        dl.last_try = time.time()
                        if dl.later:
                            self._queue_did_work = True
                        runner = self._run_video if dl.kind == "video" else self._run
                        self.tasks[dl.id] = asyncio.create_task(runner(dl))
                self._check_queue_finished()
                self._cleanup_pending()
            except Exception as e:      # le planificateur ne doit jamais mourir
                print("Erreur planificateur:", e)
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    def _cleanup_pending(self):
        now = time.time()
        for dl in list(self.downloads.values()):
            if dl.status == "pending" and now - dl.created > PENDING_TTL:
                self.downloads.pop(dl.id, None)

    # ---------- file d'attente et planificateur ----------
    def start_queue(self):
        self.queue_running = True
        self._queue_did_work = False
        for dl in self.downloads.values():
            if dl.later and dl.status in ("paused", "error"):
                dl.status, dl.error = "queued", ""
        self.wake()

    async def stop_queue(self):
        self.queue_running = False
        for dl in list(self.downloads.values()):
            if dl.later and dl.status == "downloading":
                await self._cancel_task(dl.id)
                dl.status, dl.speed = "queued", 0
        self.save(force=True)

    def _check_schedule(self):
        s = self.settings["schedule"]
        if not s.get("enabled"):
            return
        now = dt.datetime.now()
        minute = now.strftime("%Y-%m-%d %H:%M")
        if minute == self._last_sched_minute:
            return
        self._last_sched_minute = minute
        if now.weekday() not in s.get("days", []):
            return
        hm = now.strftime("%H:%M")
        if hm == s.get("start") and not self.queue_running:
            self.start_queue()
        elif s.get("stop") and hm == s.get("stop") and self.queue_running:
            asyncio.create_task(self.stop_queue())

    def _check_queue_finished(self):
        if not self.queue_running:
            return
        if any(d.later and d.status in ("queued", "downloading") for d in self.downloads.values()):
            return
        self.queue_running = False
        if self._queue_did_work:
            self._queue_did_work = False
            action = self.settings["schedule"].get("on_complete", "none")
            if action != "none":
                self.power_action(action)

    def power_action(self, action: str):
        self.save(force=True)
        self.power = {"action": action, "at": time.time() + 60}
        if action == "exit":
            if self.on_exit:
                self.loop.call_later(5, self.on_exit)
            return
        if not IS_WINDOWS:
            print(f"[Rapido] action '{action}' demandee (uniquement sous Windows)")
            return
        if action == "shutdown":
            subprocess.Popen(["shutdown", "/s", "/t", "60", "/c",
                              "Rapido : file d'attente terminee. Arret dans 60 secondes."],
                             creationflags=CREATE_NO_WINDOW)
        elif action == "sleep":
            # petit delai pour laisser le temps d'annuler depuis l'interface
            def _sleep():
                if self.power and self.power.get("action") == "sleep":
                    self.power = None
                    subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                                     creationflags=CREATE_NO_WINDOW)
            self.loop.call_later(60, _sleep)

    def cancel_power(self):
        if self.power and self.power["action"] == "shutdown" and IS_WINDOWS:
            subprocess.Popen(["shutdown", "/a"], creationflags=CREATE_NO_WINDOW)
        self.power = None

    # ---------- fenetres (capture / progression) ----------
    def _find_browser(self) -> str | None:
        custom = self.settings.get("browser_path")
        if custom and Path(custom).exists():
            return custom
        if not IS_WINDOWS:
            for name in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
                p = shutil.which(name)
                if p:
                    return p
            return None
        env = os.environ
        candidates = [
            Path(env.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
            Path(env.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
            Path(env.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
            Path(env.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
            Path(env.get("PROGRAMFILES", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        return None

    def open_window(self, path: str, width: int = 560, height: int = 440):
        """Ouvre une petite fenetre sans barre d'adresse."""
        url = f"http://localhost:{self.port}{path}"
        exe = self._find_browser()
        try:
            if exe:
                subprocess.Popen([exe, f"--app={url}", f"--window-size={width},{height}"])
            else:
                webbrowser.open(url)
        except Exception as e:
            print("Impossible d'ouvrir la fenetre:", e)

    # ---------- capture (fenetre "Informations sur le fichier") ----------
    def capture(self, url: str, headers: dict | None = None, filename: str | None = None) -> Download:
        """Cree un telechargement en attente de confirmation et analyse le lien."""
        dl = Download(
            id=uuid.uuid4().hex[:10], url=url.strip(), status="pending",
            filename=safe_filename(filename) if filename else "",
            connections=int(self.settings["connections"]),
            headers=self._clean_headers(headers),
        )
        dl.category = category_for(dl.filename or url)
        self.downloads[dl.id] = dl
        self._probes[dl.id] = asyncio.create_task(self._probe_pending(dl))
        return dl

    def capture_video(self, page_url: str, candidates: list | None = None, headers: dict | None = None) -> Download:
        dl = Download(
            id=uuid.uuid4().hex[:10], url=page_url.strip(), kind="video", status="pending",
            page_url=page_url.strip(), candidates=list(candidates or [])[:10],
            headers=self._clean_headers(headers), category="Vidéos",
        )
        self.downloads[dl.id] = dl
        self._probes[dl.id] = asyncio.create_task(self._probe_video(dl))
        return dl

    @staticmethod
    def _clean_headers(headers: dict | None) -> dict:
        return {k.title(): v for k, v in (headers or {}).items() if k.lower() in ("cookie", "referer", "user-agent")}

    async def _probe_pending(self, dl: Download):
        dl.probe = "probing"
        try:
            size, resumable, name = await self._probe(dl)
            dl.size, dl.resumable = size, resumable
            if not dl.filename:
                dl.filename = name
            dl.category = category_for(dl.filename)
            dl.probe = "ready"
        except Exception as e:
            dl.probe, dl.probe_error = "failed", f"{type(e).__name__}: {e}"[:300]
            if not dl.filename:
                dl.filename = filename_from_headers(httpx.Headers(), dl.url)
                dl.category = category_for(dl.filename)

    def confirm(self, dl_id: str, filename: str | None, folder: str | None,
                later: bool, description: str = "") -> Download:
        dl = self.downloads[dl_id]
        if filename:
            dl.filename = safe_filename(filename)
            if dl.kind != "video":
                dl.category = category_for(dl.filename)
        if folder:
            dl.folder = folder
        dl.later = later
        dl.description = description[:200]
        dl.status = "queued"
        self.save(force=True)
        self.wake()
        return dl

    def add(self, url: str, filename: str | None = None, connections: int | None = None,
            headers: dict | None = None, later: bool = False) -> Download:
        """Ajout direct (sans fenetre de capture)."""
        dl = Download(
            id=uuid.uuid4().hex[:10],
            url=url.strip(),
            filename=safe_filename(filename) if filename else "",
            connections=max(1, min(32, int(connections or self.settings["connections"]))),
            headers=self._clean_headers(headers),
            later=later,
        )
        dl.category = category_for(dl.filename or url)
        self.downloads[dl.id] = dl
        self.save(force=True)
        self.wake()
        return dl

    # ---------- actions ----------
    async def pause(self, dl_id: str):
        dl = self.downloads[dl_id]
        if dl.status in ("downloading", "queued"):
            await self._cancel_task(dl_id)
            dl.status = "paused"
            dl.speed = 0
            self.save(force=True)

    def resume(self, dl_id: str):
        dl = self.downloads[dl_id]
        if dl.status in ("paused", "error"):
            dl.status = "queued"
            dl.later = False          # "Reprendre" = maintenant
            dl.error = ""
            self.save(force=True)
            self.wake()

    def redownload(self, dl_id: str):
        """Recommence un telechargement termine ou en erreur depuis zero."""
        dl = self.downloads[dl_id]
        if dl.path:
            Path(dl.path + ".part").unlink(missing_ok=True)
        dl.segments, dl.path, dl.v_base, dl.v_done = [], "", 0, 0
        dl.status, dl.error, dl.finished_at = "queued", "", 0
        self.save(force=True)
        self.wake()

    async def refresh_address(self, dl_id: str, new_url: str):
        """Remplace un lien expire par un nouveau lien vers le meme fichier."""
        dl = self.downloads[dl_id]
        was_running = dl.status == "downloading"
        await self._cancel_task(dl_id)
        if dl.kind == "http" and dl.size > 0:
            old_url, dl.url = dl.url, new_url
            try:
                size, resumable, _ = await self._probe(dl)
            except Exception as e:
                dl.url = old_url
                raise ValueError(f"Nouveau lien injoignable : {e}")
            if size != dl.size:
                dl.url = old_url
                raise ValueError(f"Taille differente ({size} au lieu de {dl.size}) : ce n'est pas le meme fichier")
            dl.resumable = resumable
        else:
            dl.url = new_url
        dl.error = ""
        if was_running or dl.status == "error":
            dl.status = "queued"
        self.save(force=True)
        self.wake()

    async def remove(self, dl_id: str, delete_file: bool = False):
        await self._cancel_task(dl_id)
        p = self._probes.pop(dl_id, None)
        if p and not p.done():
            p.cancel()
        dl = self.downloads.pop(dl_id, None)
        if dl and dl.path:
            for part in Path(dl.path).parent.glob(Path(dl.path).stem + "*.part"):
                part.unlink(missing_ok=True)
            Path(dl.path + ".part").unlink(missing_ok=True)
            if delete_file:
                Path(dl.path).unlink(missing_ok=True)
        self.save(force=True)

    async def _cancel_task(self, dl_id: str):
        flag = self._stop_flags.get(dl_id)
        if flag:
            flag.set()
        t = self.tasks.pop(dl_id, None)
        if t and not t.done():
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

    # ---------- limitation de debit (globale) ----------
    async def _throttle(self, nbytes: int):
        limit = int(self.settings.get("speed_limit_kbps") or 0) * 1024
        if limit <= 0:
            return
        now = time.monotonic()
        self._rate_bucket = max(0.0, self._rate_bucket - (now - self._rate_ts) * limit)
        self._rate_ts = now
        self._rate_bucket += nbytes
        if self._rate_bucket > limit * 0.5:
            await asyncio.sleep((self._rate_bucket - limit * 0.5) / limit)

    def _target_folder(self, dl: Download) -> Path:
        if dl.folder:
            folder = Path(dl.folder)
        else:
            folder = Path(self.settings["download_dir"])
            if self.settings.get("sort_by_category"):
                folder = folder / dl.category
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _after_complete(self, dl: Download):
        if (self.settings.get("show_complete_dialog")
                and time.time() - dl.watched > 3):     # aucune fenetre de progression ouverte
            self.open_window(f"/w?view=progress&id={dl.id}", 520, 360)

    # ---------- fichiers classiques ----------
    async def _probe(self, dl: Download):
        """Recupere taille, nom de fichier et support des Range avec une requete bytes=0-0."""
        headers = {**dl.headers, "Range": "bytes=0-0"}
        async with self.client.stream("GET", dl.url, headers=headers) as r:
            r.raise_for_status()
            final_url = str(r.url)
            if r.status_code == 206:
                cr = r.headers.get("content-range", "")
                m = re.search(r"/(\d+)$", cr)
                size = int(m.group(1)) if m else -1
                resumable = size > 0
            else:
                size = int(r.headers.get("content-length", -1) or -1)
                resumable = False
            name = filename_from_headers(r.headers, final_url)
            ctype = r.headers.get("content-type", "")
            if "." not in name and "/" in ctype:
                ext = {"application/pdf": ".pdf", "application/zip": ".zip", "video/mp4": ".mp4",
                       "audio/mpeg": ".mp3", "application/x-msdownload": ".exe"}.get(ctype.split(";")[0].strip())
                if ext:
                    name += ext
        return size, resumable, name

    def _plan_segments(self, dl: Download):
        if not dl.resumable or dl.size <= 0:
            dl.segments = [Segment(0, dl.size - 1 if dl.size > 0 else -1)]
            return
        n = max(1, min(dl.connections, dl.size // MIN_SEGMENT or 1))
        part = dl.size // n
        dl.segments = []
        for i in range(n):
            start = i * part
            end = dl.size - 1 if i == n - 1 else start + part - 1
            dl.segments.append(Segment(start, end))

    async def _run(self, dl: Download):
        try:
            if not dl.segments:          # premier lancement
                size, resumable, name = await self._probe(dl)
                dl.size, dl.resumable = size, resumable
                if not dl.filename:
                    dl.filename = name
                    dl.category = category_for(dl.filename)
                final = unique_path(self._target_folder(dl), dl.filename)
                dl.path, dl.filename = str(final), final.name
                self._plan_segments(dl)
                with open(dl.path + ".part", "wb") as f:
                    if dl.size > 0 and dl.resumable:
                        f.truncate(dl.size)     # reserve la place sur le disque
                self.save(force=True)
            else:
                part = Path(dl.path + ".part")
                if not part.exists():
                    # fichier partiel supprime : on recommence a zero
                    for s in dl.segments:
                        s.done = 0
                    with open(part, "wb") as f:
                        if dl.size > 0 and dl.resumable:
                            f.truncate(dl.size)
                elif not dl.resumable:
                    # serveur sans reprise possible : on recommence le flux unique
                    dl.segments[0].done = 0
                    with open(part, "wb"):
                        pass

            await self._download_segments(dl)

            os.replace(dl.path + ".part", dl.path)
            dl.status = "completed"
            dl.finished_at = time.time()
            dl.speed = 0
            self._after_complete(dl)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            dl.status = "error"
            dl.error = f"{type(e).__name__}: {e}"[:300]
            dl.speed = 0
        finally:
            dl.active_connections = 0
            self.save(force=True)
            self.wake()

    async def _download_segments(self, dl: Download):
        part_path = dl.path + ".part"
        fh = open(part_path, "r+b")
        speed_task = asyncio.create_task(self._measure_speed(dl))
        pending = [s for s in dl.segments if not s.finished]
        workers = [asyncio.create_task(self._segment_worker(dl, s, fh)) for s in pending]
        try:
            await self._supervise(dl, workers, fh)
            if dl.size > 0 and dl.downloaded < dl.size:
                raise IOError("Telechargement incomplet")
        finally:
            for w in workers:
                if not w.done():
                    w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            speed_task.cancel()
            fh.flush()
            fh.close()

    async def _supervise(self, dl: Download, workers: list[asyncio.Task], fh):
        """Attend les segments, propage les erreurs, et quand une connexion se libere,
        coupe en deux le segment qui a le plus de travail restant (segmentation dynamique)."""
        while True:
            running = [w for w in workers if not w.done()]
            if not running:
                return
            done, _ = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
            for w in done:
                if not w.cancelled() and w.exception():
                    raise w.exception()
            if not dl.resumable:
                continue
            while len([w for w in workers if not w.done()]) < dl.connections:
                active = [s for s in dl.segments if not s.finished]
                if not active:
                    break
                big = max(active, key=lambda s: s.remaining)
                if big.remaining < 2 * MIN_SEGMENT:
                    break
                half = big.remaining // 2
                new_end = big.end
                split = big.start + big.done + (big.remaining - half)
                big.end = split - 1
                new = Segment(split, new_end)
                dl.segments.append(new)
                dl.segments.sort(key=lambda s: s.start)
                workers.append(asyncio.create_task(self._segment_worker(dl, new, fh)))

    async def _segment_worker(self, dl: Download, seg: Segment, fh):
        attempt = 0
        while not seg.finished:
            headers = dict(dl.headers)
            pos = seg.start + seg.done
            before = seg.done
            if dl.resumable:
                headers["Range"] = f"bytes={pos}-{seg.end}"
            try:
                dl.active_connections += 1
                async with self.client.stream("GET", dl.url, headers=headers) as r:
                    r.raise_for_status()
                    if dl.resumable and r.status_code != 206:
                        raise IOError("Le serveur a cesse d'accepter la reprise (Range)")
                    async for chunk in r.aiter_bytes(CHUNK):
                        if dl.resumable:
                            # le segment a pu etre raccourci par _supervise
                            room = seg.end - (seg.start + seg.done) + 1
                            if room <= 0:
                                break
                            chunk = chunk[:room]
                        fh.seek(seg.start + seg.done)
                        fh.write(chunk)
                        seg.done += len(chunk)
                        await self._throttle(len(chunk))
                        self.save()
                    if not dl.resumable:
                        if seg.end < 0:          # taille inconnue : fin de flux = fini
                            seg.end = seg.start + seg.done - 1
                            dl.size = seg.done
                        return
                attempt = 0
            except asyncio.CancelledError:
                raise
            except Exception:
                # une coupure apres avoir progresse ne compte pas comme un echec
                attempt = 1 if seg.done > before else attempt + 1
                if attempt > MAX_RETRIES or not dl.resumable:
                    raise
                await asyncio.sleep(min(2 ** attempt, 20))
            finally:
                dl.active_connections = max(0, dl.active_connections - 1)

    async def _measure_speed(self, dl: Download):
        last, last_t = dl.downloaded, time.monotonic()
        while True:
            await asyncio.sleep(1)
            now, cur = time.monotonic(), dl.downloaded
            inst = max(0.0, (cur - last) / (now - last_t))
            dl.speed = inst if dl.speed == 0 else dl.speed * 0.6 + inst * 0.4
            last, last_t = cur, now

    # ---------- videos (yt-dlp) ----------
    def ffmpeg(self) -> str | None:
        p = self.settings.get("ffmpeg_path")
        if p and Path(p).exists():
            return p
        local = EXE_DIR / ("ffmpeg.exe" if IS_WINDOWS else "ffmpeg")
        if local.exists():
            return str(local)
        found = shutil.which("ffmpeg")
        if found or not IS_WINDOWS:
            return found
        # installe par winget pendant que Rapido tournait (le PATH du processus n'est pas a jour)
        winget = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet"
        link = winget / "Links" / "ffmpeg.exe"
        if link.exists():
            return str(link)
        for exe in (winget / "Packages").glob("Gyan.FFmpeg*/*/bin/ffmpeg.exe"):
            return str(exe)
        return None

    def _ydl_base_opts(self, dl: Download) -> dict:
        opts = {
            "quiet": True, "no_warnings": True, "noprogress": True,
            "noplaylist": True, "http_headers": {"User-Agent": USER_AGENT, **dl.headers},
            "socket_timeout": 30,
        }
        ff = self.ffmpeg()
        if ff:
            opts["ffmpeg_location"] = ff
        return opts

    def _build_formats(self, info: dict) -> list[dict]:
        """Transforme les formats yt-dlp en quelques choix simples : 1080p, 720p, audio..."""
        has_ff = bool(self.ffmpeg())
        fmts = info.get("formats") or []
        dur = info.get("duration") or 0

        def fsize(f):
            s = f.get("filesize") or f.get("filesize_approx")
            if not s and f.get("tbr") and dur:
                s = int(f["tbr"] * 1000 / 8 * dur)
            return s or 0

        audio = [f for f in fmts if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")]
        best_audio = max(audio, key=lambda f: f.get("abr") or f.get("tbr") or 0, default=None)
        heights = sorted({f["height"] for f in fmts if f.get("height") and f.get("vcodec") != "none"}, reverse=True)
        options = []
        for h in heights[:6]:
            vids = [f for f in fmts if f.get("height") == h and f.get("vcodec") != "none"]
            progressive = [f for f in vids if f.get("acodec") not in (None, "none")]
            best_v = max(vids, key=lambda f: f.get("tbr") or 0)
            if has_ff:
                fmt = f"bv*[height={h}]+ba/b[height={h}]/bv*[height<={h}]+ba/b"
                size = fsize(best_v) + (fsize(best_audio) if best_audio and best_v.get("acodec") in (None, "none") else 0)
                ext = "mp4"
            elif progressive:
                best_p = max(progressive, key=lambda f: f.get("tbr") or 0)
                fmt, size, ext = best_p["format_id"], fsize(best_p), best_p.get("ext", "mp4")
            else:
                continue          # sans ffmpeg on ne peut pas fusionner video + audio
            label = f"{h}p" + (f" {int(best_v['fps'])}fps" if (best_v.get("fps") or 0) > 30 else "")
            options.append({"id": f"v{h}", "label": label, "format": fmt, "ext": ext, "size": size})
        if not options:
            # flux simple (m3u8 sans variantes, mp4 direct...)
            options.append({"id": "best", "label": "Meilleure qualité", "format": "bv*+ba/b" if has_ff else "b",
                            "ext": "mp4" if has_ff else (info.get("ext") or "mp4"), "size": fsize(info)})
        if best_audio:
            options.append({"id": "audio", "label": "Audio seulement", "format": "ba[ext=m4a]/ba",
                            "ext": best_audio.get("ext") if best_audio.get("ext") != "webm" else "m4a",
                            "size": fsize(best_audio)})
        return options

    async def _probe_video(self, dl: Download):
        dl.probe = "probing"
        try:
            import yt_dlp  # noqa: F401
        except ImportError:
            dl.probe, dl.probe_error = "failed", "yt-dlp n'est pas installe (pip install yt-dlp)"
            return

        def extract(url):
            import yt_dlp
            with yt_dlp.YoutubeDL(self._ydl_base_opts(dl)) as ydl:
                return ydl.extract_info(url, download=False)

        tried, last_err = [], ""
        # 1) la page elle-meme (YouTube, Vimeo, Dailymotion... ~1800 sites)
        # 2) puis les flux detectes par l'extension (m3u8 / mpd / mp4)
        for url in [dl.page_url, *dl.candidates]:
            if not url or url in tried or url.startswith("blob:"):
                continue
            tried.append(url)
            try:
                info = await asyncio.to_thread(extract, url)
                if info.get("_type") == "playlist":
                    entries = [e for e in (info.get("entries") or []) if e]
                    if not entries:
                        raise ValueError("Playlist vide")
                    info = entries[0]
                if not info.get("formats") and not info.get("url"):
                    raise ValueError("Aucun flux video")
                dl.url = url
                dl.title = info.get("title") or "video"
                dl.thumbnail = info.get("thumbnail") or ""
                dl.duration = int(info.get("duration") or 0)
                dl.formats = self._build_formats(info)
                first = dl.formats[0]
                dl.video_format = first["format"]
                dl.size = first["size"] or -1
                dl.filename = safe_filename(dl.title) + "." + first["ext"]
                dl.probe = "ready"
                return
            except Exception as e:
                last_err = str(e).replace("ERROR: ", "")[:300]
        dl.probe, dl.probe_error = "failed", last_err or "Aucune video trouvee"

    def choose_format(self, dl: Download, option_id: str):
        for o in dl.formats:
            if o["id"] == option_id:
                dl.video_format = o["format"]
                dl.size = o["size"] or -1
                dl.filename = Path(dl.filename).stem + "." + o["ext"]
                if option_id == "audio":
                    dl.category = "Musique"
                return
        raise ValueError("Format inconnu")

    async def _run_video(self, dl: Download):
        stop = threading.Event()
        self._stop_flags[dl.id] = stop
        speed_task = asyncio.create_task(self._measure_speed(dl))
        fut = asyncio.ensure_future(asyncio.to_thread(self._video_blocking, dl, stop))
        try:
            await asyncio.shield(fut)
            dl.status = "completed"
            dl.finished_at = time.time()
            if dl.size <= 0 or dl.downloaded > dl.size:
                dl.size = dl.downloaded
            self._after_complete(dl)
        except asyncio.CancelledError:
            stop.set()
            try:
                await fut
            except Exception:
                pass
            raise
        except Exception as e:
            dl.status = "error"
            dl.error = str(e).replace("ERROR: ", "")[:300]
        finally:
            speed_task.cancel()
            dl.speed = 0
            dl.active_connections = 0
            self._stop_flags.pop(dl.id, None)
            self.save(force=True)
            self.wake()

    def _video_blocking(self, dl: Download, stop: threading.Event):
        import yt_dlp
        folder = self._target_folder(dl)
        if not dl.path:
            dl.path = str(unique_path(folder, dl.filename))   # corrige a la fin avec le vrai nom
        stem = Path(dl.path).stem
        dl.v_base, dl.v_done = 0, 0
        seen_done: set[str] = set()

        def hook(d):
            if stop.is_set():
                raise StopVideo("pause")
            fname = d.get("filename") or ""
            if d["status"] == "downloading":
                dl.v_done = int(d.get("downloaded_bytes") or 0)
                dl.active_connections = 1
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                if total and dl.v_base + total > dl.size:
                    dl.size = int(dl.v_base + total)
            elif d["status"] == "finished" and fname not in seen_done:
                seen_done.add(fname)
                dl.v_base += d.get("total_bytes") or d.get("downloaded_bytes") or dl.v_done
                dl.v_done = 0

        opts = self._ydl_base_opts(dl)
        opts.update({
            "format": dl.video_format or "b",
            "outtmpl": str(folder / (stem + ".%(ext)s")),
            "progress_hooks": [hook],
            "continuedl": True,
            "concurrent_fragment_downloads": max(1, min(16, dl.connections)),
            "retries": 10, "fragment_retries": 10,
        })
        if opts.get("ffmpeg_location") and "+" in opts["format"]:
            opts["merge_output_format"] = "mp4"
        limit = int(self.settings.get("speed_limit_kbps") or 0)
        if limit > 0:
            opts["ratelimit"] = limit * 1024
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(dl.url, download=True)
        except yt_dlp.utils.DownloadError:
            if stop.is_set():
                raise StopVideo("pause")
            raise
        reqs = (info or {}).get("requested_downloads") or []
        if reqs and reqs[0].get("filepath"):
            dl.path = reqs[0]["filepath"]
            dl.filename = Path(dl.path).name
        if Path(dl.path).exists():
            dl.size = Path(dl.path).stat().st_size
            dl.v_base, dl.v_done = dl.size, 0

    # ---------- presse-papiers (Windows) ----------
    def _read_clipboard(self) -> str:
        CF_UNICODETEXT = 13
        u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        u32.GetClipboardData.restype = ctypes.c_void_p
        k32.GlobalLock.restype = ctypes.c_void_p
        k32.GlobalLock.argtypes = [ctypes.c_void_p]
        k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        if not u32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return ""
        if not u32.OpenClipboard(None):
            return ""
        try:
            h = u32.GetClipboardData(CF_UNICODETEXT)
            if not h:
                return ""
            p = k32.GlobalLock(h)
            try:
                return ctypes.wstring_at(p) if p else ""
            finally:
                k32.GlobalUnlock(h)
        finally:
            u32.CloseClipboard()

    def _clipboard_loop(self):
        seq_fn = ctypes.windll.user32.GetClipboardSequenceNumber
        last_seq = seq_fn()
        while True:
            time.sleep(0.8)
            try:
                seq = seq_fn()
                if seq == last_seq:
                    continue
                last_seq = seq
                if not self.settings.get("monitor_clipboard"):
                    continue
                text = self._read_clipboard().strip()
                if text == self._clip_last or not re.fullmatch(r"https?://\S+", text):
                    continue
                self._clip_last = text
                if url_ext(text) in set(self.settings.get("capture_exts", [])):
                    self.loop.call_soon_threadsafe(self._capture_and_show, text)
            except Exception:
                pass

    def _capture_and_show(self, url: str):
        if self.settings.get("show_capture_dialog", True):
            dl = self.capture(url)
            self.open_window(f"/w?view=capture&id={dl.id}", 560, 580)
        else:
            self.add(url)
