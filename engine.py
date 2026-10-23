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
import contextlib
import ctypes
import datetime as dt
import errno
import email.utils
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field, asdict
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

class ResourceChanged(IOError):
    """Remote bytes no longer match the resource originally probed."""


class ServerBackoff(IOError):
    def __init__(self, status: int, delay: float):
        self.delay = delay
        super().__init__(f"HTTP {status}: server requested retry")


def retry_after_seconds(value: str | None) -> float:
    """Accept Retry-After seconds or HTTP dates; cap untrusted delays at 60 s."""
    if not value:
        return 0.0
    try:
        seconds = float(value.strip())
        if not (0 <= seconds < float("inf")):
            return 0.0
        return min(seconds, 60.0)
    except (ValueError, AttributeError, OverflowError):
        pass
    try:
        when = email.utils.parsedate_to_datetime(value)
        if when.tzinfo is None:
            return 0.0
        now = dt.datetime.now(dt.timezone.utc)
        return min(60.0, max(0.0, (when - now).total_seconds()))
    except (ValueError, TypeError, OverflowError):
        return 0.0


def if_range_validator(dl: "Download") -> str:
    """RFC 9110: strong ETag, or no ETag plus a provably strong date.

    A weak/malformed ETag must not be replaced by a Last-Modified If-Range.
    For a date validator, the probe Date must be at least 60 s newer.
    """
    if dl.etag:
        return dl.etag if re.fullmatch(r'"[\x21\x23-\x7e\x80-\xff]*"', dl.etag) else ""
    try:
        modified = email.utils.parsedate_to_datetime(dl.last_modified)
        dated = email.utils.parsedate_to_datetime(dl.validator_date)
        if modified.tzinfo is not None and dated.tzinfo is not None and (dated - modified).total_seconds() >= 60:
            return dl.last_modified
    except (ValueError, TypeError, OverflowError):
        pass
    return ""


CHUNK = 256 * 1024            # taille des blocs lus sur le reseau
MIN_SEGMENT = 1024 * 1024     # on ne decoupe pas en morceaux de moins de 1 Mo
MAX_RETRIES = 5               # echecs consecutifs (sans progression) avant abandon
PROBE_TIMEOUT = 120           # analyse d'une video : au-dela, on abandonne (processus arrete)
RETRY_DELAY = 1.0             # multiplicateur des pauses entre essais (2, 4, 8, 16, 20 s) ; reduit par les tests
TOOL_LOOKUP_TTL = 10.0         # secondes avant de rechercher a nouveau ffmpeg / deno
SAVE_EVERY = 2.0              # secondes entre deux sauvegardes de l'etat
PENDING_TTL = 30 * 60         # une capture non confirmee disparait apres 30 min
IS_WINDOWS = platform.system() == "Windows"
from rapido_version import VERSION  # source unique de la version
import windows_job
FROZEN = getattr(sys, "frozen", False)                       # True dans Rapido.exe (PyInstaller)
RES_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))   # fichiers embarques (html, icone)
EXE_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).parent
CREATE_NEW_CONSOLE = 0x00000010
CREATE_NO_WINDOW = 0x08000000
BROWSER_EXES = {"chrome.exe", "msedge.exe", "brave.exe", "chromium.exe", "vivaldi.exe",
                "chrome", "chromium", "chromium-browser", "google-chrome", "microsoft-edge", "brave-browser"}

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


MAX_FILENAME = 180
WIN_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def safe_filename(name: str) -> str:
    # caracteres interdits + caracteres de controle
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", name)
    # caracteres d'inversion de texte : "photo\u202egpj.exe" s'afficherait "photoexe.jpg"
    name = re.sub("[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", name)
    name = name.strip(" .")
    if name.split(".")[0].strip().lower() in WIN_RESERVED:     # CON, NUL, COM1... (noms reserves Windows)
        name = "_" + name
    if len(name) > MAX_FILENAME:
        # Garder l'extension (".zip", ".tar.gz") : elle decide de la categorie et de l'ouverture.
        suffix = "".join(re.findall(r"(?:\.[A-Za-z0-9]{1,8}){1,2}$", name)[:1])
        name = name[:MAX_FILENAME - len(suffix)].rstrip(" .") + suffix
    # Windows retire les points et espaces finaux : le nom sur disque differerait.
    return name.rstrip(" .") or "telechargement"


def _retry_while_locked(action, attempts: int = 12, delay: float = 0.01):
    """Sous Windows, un antivirus ou l'indexeur qui tient un fichier ouvert fait echouer sa
    lecture ou son remplacement (acces refuse, WinError 32). Observe sous antivirus au-dela
    de 0,2 s : attente doublee a chaque essai, plafonnee a 0,32 s (~2,5 s au total)."""
    for attempt in range(attempts):
        try:
            return action()
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(min(delay * 2 ** attempt, 0.32))


def _read_text_retrying(path: Path, attempts: int = 12) -> str:
    return _retry_while_locked(lambda: path.read_text("utf-8"), attempts)


def _replace_retrying(src: Path, dst: Path, attempts: int = 12):
    _retry_while_locked(lambda: os.replace(src, dst), attempts)


# ---------- protection des donnees ----------
def _dpapi(data: bytes, encrypt: bool) -> bytes:
    """Chiffre / dechiffre avec Windows DPAPI : seul ton compte Windows peut relire."""
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_void_p)]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = Blob(len(data), ctypes.cast(buf, ctypes.c_void_p))
    blob_out = Blob()
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    fn = crypt32.CryptProtectData if encrypt else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(blob_in), None, None, None, None, 0x1, ctypes.byref(blob_out))  # 0x1 = pas d'interface
    if not ok:
        raise OSError("DPAPI a echoue")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def protect(text: str) -> str:
    import base64
    return base64.b64encode(_dpapi(text.encode("utf-8"), True)).decode()


def unprotect(token: str) -> str:
    import base64
    return _dpapi(base64.b64decode(token), False).decode("utf-8")


def mark_of_the_web(path: str, url: str, referrer: str = ""):
    """Marque le fichier comme venant d'Internet (comme Chrome / Edge) : Windows SmartScreen
    et Office (mode protege) avertiront avant d'ouvrir un programme ou un document telecharge."""
    if not IS_WINDOWS or not path:
        return

    def clean(u: str) -> str:
        try:
            p = urlparse(u)
            netloc = p.hostname or ""
            if p.port:
                netloc += f":{p.port}"
            if p.scheme not in ("http", "https") or not netloc:
                return ""
            # ZoneId=3 is preserved; source metadata only needs the origin.
            # Path, userinfo, query and fragment may all contain bearer tokens.
            if ":" in (p.hostname or ""):
                netloc = "[" + p.hostname + "]" + (f":{p.port}" if p.port else "")
            return p._replace(netloc=netloc, path="/", params="", query="", fragment="").geturl().replace("\r", "").replace("\n", "")
        except Exception:
            return ""
    try:
        # newline="" : on ecrit nous-memes les \r\n (sinon Windows les double en \r\r\n)
        with open(path + ":Zone.Identifier", "w", encoding="utf-8", newline="") as f:
            f.write("[ZoneTransfer]\r\nZoneId=3\r\n")
            if referrer:
                f.write(f"ReferrerUrl={clean(referrer)}\r\n")
            f.write(f"HostUrl={clean(url)}\r\n")
    except OSError:
        pass        # disque non NTFS (cle USB FAT32...) : pas de flux alternatif possible


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


def unique_path(folder: Path, filename: str, taken=frozenset()) -> Path:
    """Evite d'ecraser un fichier existant : fichier.zip -> fichier (1).zip.
    taken : chemins deja prevus par d'autres telechargements (os.path.normcase)."""
    p = folder / filename
    stem, suffix, i = p.stem, p.suffix, 1
    while p.exists() or p.with_name(p.name + ".part").exists() or os.path.normcase(str(p)) in taken:
        p = folder / f"{stem} ({i}){suffix}"
        i += 1
    return p


def _move_without_overwrite(src: Path, dst: Path) -> Path:
    """Renomme le fichier termine sans jamais ecraser un fichier apparu entre-temps sous le
    meme nom : sous Windows, os.rename echoue de facon atomique si la cible existe."""
    while True:
        if not IS_WINDOWS and dst.exists():
            dst = unique_path(dst.parent, dst.name)
        try:
            os.rename(src, dst)
            return dst
        except FileExistsError:
            dst = unique_path(dst.parent, dst.name)


def _safe_ext(ext, default: str = "mp4") -> str:
    """Extension annoncee par le site (via yt-dlp) : elle ne doit jamais former un chemin."""
    return ext if isinstance(ext, str) and re.fullmatch(r"[A-Za-z0-9]{1,8}", ext) else default


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
    etag: str = ""
    last_modified: str = ""
    validator_date: str = ""
    connections: int = 8
    status: str = "queued"      # pending | queued | downloading | paused | completed | error
    later: bool = False         # dans la file d'attente (attend le planificateur / "Demarrer la file")
    error: str = ""
    description: str = ""
    segments: list[Segment] = field(default_factory=list)
    handoff_ticket: str = ""    # private capability; never returned by to_public
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
    yt_cookies: bool = False    # True = la video n'a marche qu'avec les cookies du navigateur
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
        d.pop("handoff_ticket", None)
        d["segments"] = [{"start": s.start, "end": s.end, "done": s.done} for s in self.segments]
        eta = -1
        if self.size > 0 and self.speed > 0:
            eta = max(0, int((self.size - self.downloaded) / self.speed))
        d["eta"] = eta
        return d

    def disk_fields(self) -> dict:
        d = asdict(self)
        for k in ("speed", "active_connections", "watched"):
            d.pop(k, None)
        return d

    def to_disk(self) -> dict:
        d = self.disk_fields()
        if IS_WINDOWS:
            try:
                # Protect the entire record, including signed URLs, referrers,
                # candidates, thumbnails and errors which may contain URLs.
                return {"id": self.id, "private_state_version": 1,
                        "private_state_enc": protect(json.dumps(d, ensure_ascii=False))}
            except (OSError, ValueError, TypeError, UnicodeError):
                # No plaintext fallback, including during DPAPI failure.
                return {"id": self.id, "url": "", "status": "error",
                        "error": "Historique prive indisponible : protection Windows en echec."}
        # Non-Windows development builds have no DPAPI; never persist cookies.
        headers = d.pop("headers", {}) or {}
        d["headers"] = {k: v for k, v in headers.items() if k.lower() != "cookie"}
        return d

    @classmethod
    def from_disk(cls, d: dict) -> "Download":
        d = dict(d)
        sealed = "private_state_enc" in d or "private_state_version" in d
        if sealed:
            try:
                if not IS_WINDOWS or d.get("private_state_version") != 1:
                    raise ValueError("Unsupported private state")
                value = json.loads(unprotect(d["private_state_enc"]))
                if not isinstance(value, dict) or value.get("id") != d.get("id"):
                    raise ValueError("Invalid private state")
                d = value
            except (OSError, ValueError, TypeError, KeyError, UnicodeError):
                # Never interpret attacker-supplied plaintext fields beside an
                # unreadable envelope as a URL to resume.
                return cls(id=str(d.get("id", "")), url="", status="error",
                           error="Historique prive illisible pour ce compte Windows.")
        segs = [Segment(**s) for s in d.pop("segments", [])]
        cookie_enc = d.pop("cookie_enc", "")
        dl = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        dl.segments = segs
        if not sealed:
            # Legacy records may contain encrypted cookies, never trust plain ones.
            dl.headers = {k: v for k, v in (dl.headers or {}).items() if k.lower() != "cookie"}
            if cookie_enc and IS_WINDOWS:
                try:
                    dl.headers["Cookie"] = unprotect(cookie_enc)
                except Exception:
                    pass
        if dl.status == "downloading":
            dl.status = "queued"
        if dl.probe == "probing":
            dl.probe = ""
        return dl


class Manager:
    def __init__(self, data_dir: Path, port: int = 9614):
        self.port = port
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._remove_stale_cookie_files()
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
        self._procs: dict = {}            # processus yt-dlp en cours (telechargements video)
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
        self._unread: set[Path] = set()                   # fichiers verrouilles au demarrage
        self._tools: dict[str, tuple] = {}                 # outil -> (reglage, instant, chemin)
        self._sealed: dict[str, tuple[bytes, dict]] = {}   # id -> (empreinte du contenu, enveloppe DPAPI)
        self._load()

    _COOKIE_FILE = re.compile(r"ck-[a-z0-9_]{8}\.txt")   # noms crees par _ydl_opts (mkstemp)

    def _remove_stale_cookie_files(self):
        """Une analyse yt-dlp interrompue (fermeture, plantage) laissait son fichier de cookies
        en clair dans le dossier de donnees. Une seule instance tourne : aucun n'est en cours."""
        for path in self.data_dir.glob("ck-*.txt"):
            if self._COOKIE_FILE.fullmatch(path.name) and path.is_file():
                try:
                    path.unlink()
                except OSError:
                    pass

    # ---------- persistance ----------
    def _read_json(self, path: Path, kind: type):
        """Contenu JSON de path, ou None. Un fichier illisible est mis de cote (jamais ecrase
        par la sauvegarde suivante) pour pouvoir etre recupere."""
        if not path.exists():
            return None
        try:
            value = json.loads(_read_text_retrying(path))
            if isinstance(value, kind):
                return value
        except (ValueError, UnicodeError):
            pass
        except OSError:
            # Verrouille (antivirus) meme apres les essais : garder une copie avant d'ecrire.
            self._unread.add(path)
            return None
        Manager._keep_aside(path, os.rename)
        return None

    def _preserve_unread(self, path: Path) -> bool:
        """Avant de remplacer un fichier qui n'a pas pu etre lu au demarrage, en garder une copie.
        False : la copie est impossible, il ne faut pas ecrire par-dessus."""
        if path not in self._unread:
            return True
        if not path.exists() or Manager._keep_aside(path, shutil.copy2):
            self._unread.discard(path)
            return True
        return False

    @staticmethod
    def _keep_aside(path: Path, move) -> bool:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for i in range(100):
            aside = path.with_name(f"{path.name}.unreadable-{stamp}" + (f"-{i}" if i else ""))
            if not aside.exists():
                try:
                    move(path, aside)
                    return True
                except OSError:
                    return False
        return False

    def _load(self):
        saved = self._read_json(self.settings_file, dict)
        if saved is not None:
            try:
                sched = {**self.settings["schedule"], **saved.pop("schedule", {})}
                self.settings.update(saved)
                self.settings["schedule"] = sched
            except Exception:
                pass
        records = self._read_json(self.state_file, list)
        if records is not None:
            unreadable = False
            for d in records:
                try:
                    dl = Download.from_disk(d)
                    self.downloads[dl.id] = dl
                except Exception:
                    # Un seul enregistrement illisible ne doit pas faire perdre les suivants.
                    unreadable = True
            if unreadable:
                # La prochaine sauvegarde l'omettra : garder l'original pour le recuperer.
                self._keep_aside(self.state_file, shutil.copy2)
            try:
                if IS_WINDOWS and any(not isinstance(d, dict) or "private_state_enc" not in d for d in records):
                    # Upgrade loaded legacy history immediately, before startup.
                    self.save(force=True)
            except Exception:
                pass

    def save(self, force: bool = False, protected_record=None):
        """Ecrit l'etat. Une sauvegarde forcee leve une erreur si elle echoue (le transfert
        natif exige une ecriture durable) ; une sauvegarde de progression est reessayee plus tard."""
        now = time.monotonic()
        if not force and now - self._last_save < SAVE_EVERY:
            return
        self._last_save = now
        if not self._preserve_unread(self.state_file):
            if force:
                raise PermissionError(errno.EACCES, "Historique illisible et non copie : pas d'ecrasement",
                                      str(self.state_file))
            return
        try:
            tmp = self.state_file.with_suffix(".tmp")
            records = [protected_record[1] if protected_record and d.id == protected_record[0]
                       else self._disk_record(d) for d in self.downloads.values()]
            self._sealed = {k: v for k, v in self._sealed.items() if k in self.downloads}
            tmp.write_text(json.dumps(records, ensure_ascii=False, indent=1), "utf-8")
            # Progression : un seul essai, reprise au tour suivant plutot que d'attendre
            # l'antivirus sur la boucle du serveur. Sauvegarde forcee : on insiste.
            _replace_retrying(tmp, self.state_file, attempts=12 if force else 1)
        except OSError as e:
            if force:
                raise
            print("Sauvegarde de la progression reportee :", e)

    def _disk_record(self, dl: Download) -> dict:
        """Enveloppe DPAPI d'un telechargement, reutilisee tant que son contenu ne change pas :
        chiffrer tout l'historique a chaque sauvegarde bloquait la boucle (~1 ms par entree)."""
        if not IS_WINDOWS:
            return dl.to_disk()
        key = hashlib.sha256(json.dumps(dl.disk_fields(), ensure_ascii=False, sort_keys=True)
                             .encode("utf-8")).digest()
        cached = self._sealed.get(dl.id)
        if cached is not None and cached[0] == key:
            return cached[1]
        record = dl.to_disk()
        if "private_state_enc" in record:
            self._sealed[dl.id] = (key, record)
        else:
            self._sealed.pop(dl.id, None)      # echec DPAPI : on reessaiera a la prochaine sauvegarde
        return record

    def _save_quietly(self):
        # Fin d'une tache : l'etat reste en memoire et sera ecrit a la prochaine sauvegarde.
        try:
            self.save(force=True)
        except OSError as e:
            print("Sauvegarde de l'etat impossible :", e)

    def save_settings(self):
        if not self._preserve_unread(self.settings_file):
            raise PermissionError(errno.EACCES, "Reglages illisibles et non copies : pas d'ecrasement",
                                  str(self.settings_file))
        # Fichier temporaire puis remplacement : une ecriture interrompue (disque plein,
        # arret) ne doit pas laisser un settings.json tronque, ignore au demarrage suivant.
        tmp = self.settings_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.settings, indent=2, ensure_ascii=False), "utf-8")
        _replace_retrying(tmp, self.settings_file)

    # ---------- cycle de vie ----------
    async def start(self):
        self.loop = asyncio.get_running_loop()
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, read=60.0),
            # E5 : on demande les octets bruts, jamais compresses (gzip / br) : seuls des octets
            # bruts correspondent aux positions des plages Range dans le fichier
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
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
        if custom and Path(custom).is_file() and Path(custom).name.lower() in BROWSER_EXES:
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
            headers: dict | None = None, later: bool = False, persist: bool = True) -> Download:
        """Ajout direct (sans fenetre de capture). persist=False : l'appelant sauvegarde
        une seule fois apres un ajout groupe (coller des centaines de liens)."""
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
        if persist:
            self.save(force=True)
        self.wake()
        return dl

    # ---------- actions ----------
    # persist=False : action groupee, l'appelant sauvegarde une seule fois a la fin.
    async def pause(self, dl_id: str, persist: bool = True):
        dl = self.downloads[dl_id]
        if dl.status in ("downloading", "queued"):
            await self._cancel_task(dl_id)
            dl.status = "paused"
            dl.speed = 0
            if persist:
                self.save(force=True)

    def resume(self, dl_id: str, persist: bool = True):
        dl = self.downloads[dl_id]
        if dl.status in ("paused", "error"):
            dl.status = "queued"
            dl.later = False          # "Reprendre" = maintenant
            dl.error = ""
            if persist:
                self.save(force=True)
            self.wake()

    def redownload(self, dl_id: str):
        """Recommence un telechargement termine ou en erreur depuis zero."""
        dl = self.downloads[dl_id]
        if dl.status == "handoff":
            raise ValueError("Recover the interrupted handoff before restarting")
        if dl.path and not self._path_taken_by_other(dl):
            Path(dl.path + ".part").unlink(missing_ok=True)
        dl.segments, dl.path, dl.v_base, dl.v_done = [], "", 0, 0
        dl.status, dl.error, dl.finished_at = "queued", "", 0
        self.save(force=True)
        self.wake()

    async def refresh_address(self, dl_id: str, new_url: str):
        """Remplace un lien expire par un nouveau lien vers le meme fichier."""
        dl = self.downloads[dl_id]
        was_active = dl.status in ("downloading", "queued")
        if was_active:
            # Keep the scheduler from starting the old/new URL while the probe
            # yields. Failed refreshes remain safely paused.
            dl.status = "paused"
        await self._cancel_task(dl_id)
        if dl.kind == "http" and dl.size > 0:
            previous = (dl.url, dl.etag, dl.last_modified, dl.validator_date, dl.resumable)
            validator = if_range_validator(dl)
            dl.url = new_url
            try:
                size, resumable, _ = await self._probe(dl)
                if size != dl.size:
                    raise ValueError(f"Taille differente ({size} au lieu de {dl.size})")
                if dl.downloaded and (not resumable or not validator or if_range_validator(dl) != validator):
                    raise ValueError("Identite du fichier non confirmee : recommencer depuis zero")
            except Exception as e:
                dl.url, dl.etag, dl.last_modified, dl.validator_date, dl.resumable = previous
                self.save(force=True)
                raise ValueError(f"Nouveau lien refuse : {e}") from e
            dl.resumable = resumable
        else:
            if dl.kind == "http" and dl.downloaded:
                self.save(force=True)
                raise ValueError("Identite du fichier non confirmee : recommencer depuis zero")
            dl.url = new_url
        dl.error = ""
        if was_active or dl.status == "error":
            dl.status = "queued"
        self.save(force=True)
        self.wake()

    def _unused_path(self, folder: Path, filename: str, dl: Download) -> Path:
        """Nom libre sur le disque ET parmi les noms prevus par les autres telechargements
        inacheves : yt-dlp ne cree ses fichiers que quelques secondes apres le choix du nom."""
        taken = frozenset(os.path.normcase(o.path) for o in self.downloads.values()
                          if o is not dl and o.path and o.status != "completed")
        return unique_path(folder, filename, taken)

    def _path_taken_by_other(self, dl: Download) -> bool:
        """Un autre telechargement inacheve utilise le meme chemin : les fichiers temporaires
        a ce nom sont les siens (le .part de dl a disparu et l'autre a pris le nom libre)."""
        return any(o is not dl and o.path == dl.path and o.status != "completed"
                   for o in self.downloads.values())

    async def remove(self, dl_id: str, delete_file: bool = False, persist: bool = True):
        await self._cancel_task(dl_id)
        p = self._probes.pop(dl_id, None)
        if p and not p.done():
            p.cancel()
        dl = self.downloads.get(dl_id)
        if dl and dl.path:
            if dl.status != "completed":
                # Inacheve, dl.path n'est qu'un nom prevu : il peut designer un fichier de
                # l'utilisateur, jamais efface ici. Si un autre telechargement inacheve a pris ce
                # nom, ses fichiers temporaires ne sont pas les notres non plus.
                if not self._path_taken_by_other(dl):
                    for tmp in self._temp_files(dl):
                        try:
                            tmp.unlink(missing_ok=True)
                        except OSError as e:     # verrouille (antivirus) : un reste ne bloque pas la suppression
                            print("Fichier temporaire non supprime :", e)
            elif delete_file:
                # Echec : l'entree reste, pour que l'utilisateur sache que le fichier existe encore.
                Path(dl.path).unlink(missing_ok=True)
        self.downloads.pop(dl_id, None)
        if persist:
            self.save(force=True)

    @staticmethod
    def _temp_files(dl: Download) -> list[Path]:
        """Fichiers temporaires appartenant A CE telechargement seulement.
        (Avant : un motif "film*.part" effacait aussi "film (1).mp4.part" d'un autre telechargement.)"""
        own = Path(dl.path + ".part")
        files = [own] if own.exists() else []
        if dl.kind == "video":
            # fichiers de yt-dlp : film.mp4.part, film.f137.mp4.part, film.f137.mp4.part-Frag3.part,
            # film.mp4.ytdl, film.temp.mp4
            stem = re.escape(Path(dl.path).stem)
            pat = re.compile(rf"^{stem}\.(?:(?:f[\w-]+\.)?[A-Za-z0-9]+(?:\.part(?:-Frag\d+\.part)?|\.ytdl)"
                             rf"|temp\.[A-Za-z0-9]+)$")
            folder = Path(dl.path).parent
            if folder.is_dir():
                files += [p for p in folder.iterdir() if p.is_file() and p != own and pat.match(p.name)]
        return files

    async def _cancel_task(self, dl_id: str):
        flag = self._stop_flags.get(dl_id)
        if flag:
            flag.set()
        proc = self._procs.get(dl_id)
        if proc is not None and proc.is_alive():
            proc.terminate()
        # Keep the old task registered until cleanup really finishes. Another
        # request must await the same writer before deleting/resetting its file.
        t = self.tasks.get(dl_id)
        if t is not None:
            try:
                if not t.done():
                    if not t.cancelling():
                        t.cancel()
                    try:
                        # Cancelling an API caller must not cancel the writer's
                        # cleanup a second time or allow that caller to reset it.
                        await asyncio.shield(t)
                    except asyncio.CancelledError:
                        if asyncio.current_task().cancelling():
                            dl = self.downloads.get(dl_id)
                            if dl is not None and dl.status == "downloading":
                                dl.status, dl.speed = "paused", 0
                                self.save(force=True)
                            raise
                    except Exception:
                        pass
            finally:
                if t.done() and self.tasks.get(dl_id) is t:
                    self.tasks.pop(dl_id, None)

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
        mark_of_the_web(dl.path, dl.url if dl.kind == "http" else (dl.page_url or dl.url),
                        dl.headers.get("Referer", ""))
        dl.headers = {}            # on oublie les cookies des que le fichier est termine
        if (self.settings.get("show_complete_dialog")
                and time.time() - dl.watched > 3):     # aucune fenetre de progression ouverte
            self.open_window(f"/w?view=progress&id={dl.id}", 520, 360)

    # ---------- fichiers classiques ----------
    async def _probe(self, dl: Download):
        """Recupere taille, nom de fichier et support des Range avec une requete bytes=0-0."""
        headers = {**dl.headers, "Range": "bytes=0-0", "Accept-Encoding": "identity"}
        async with self.client.stream("GET", dl.url, headers=headers) as r:
            if r.status_code == 416 and re.fullmatch(r"\s*bytes\s+\*/0\s*", r.headers.get("content-range", "")):
                # Fichier vide : nginx et d'autres refusent la plage 0-0 (416, « */0 »).
                return 0, False, filename_from_headers(r.headers, str(r.url))
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
            dl.etag = r.headers.get("etag", "")
            dl.last_modified = r.headers.get("last-modified", "")
            dl.validator_date = r.headers.get("date", "")
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
                final = self._unused_path(self._target_folder(dl), dl.filename, dl)
                dl.path, dl.filename = str(final), final.name
                self._plan_segments(dl)
                with open(dl.path + ".part", "wb") as f:
                    if dl.size > 0 and dl.resumable:
                        f.truncate(dl.size)     # reserve la place sur le disque
                self.save(force=True)
            else:
                part = Path(dl.path + ".part")
                # Un autre telechargement inacheve du meme nom : ce .part est le sien (le notre a
                # ete supprime entre-temps), ne jamais ecrire dedans.
                foreign = self._path_taken_by_other(dl)
                if (not foreign and part.exists() and dl.resumable and dl.size > 0
                        and part.stat().st_size < dl.size):
                    # La place etait reservee en entier : un .part plus court a perdu des octets
                    # deja comptes (nettoyage, erreur disque). Reprendre ecrirait des zeros.
                    part.unlink()
                if foreign or not part.exists():
                    # fichier partiel supprime : on recommence a zero, sous un nom libre (un autre
                    # telechargement du meme nom a pu prendre ce nom entre-temps).
                    final = self._unused_path(self._target_folder(dl), Path(dl.path).name, dl)
                    dl.path, dl.filename = str(final), final.name
                    part = Path(dl.path + ".part")
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

            final = _move_without_overwrite(Path(dl.path + ".part"), Path(dl.path))
            dl.path, dl.filename = str(final), final.name
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
            self._save_quietly()
            self.wake()

    async def _download_segments(self, dl: Download):
        part_path = dl.path + ".part"
        # Advance saved progress only after FileIO actually accepts the bytes;
        # a buffered writer could report success before a later ENOSPC flush.
        fh = open(part_path, "r+b", buffering=0)
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
            if dl.resumable:
                headers["Accept-Encoding"] = "identity"
            pos = seg.start + seg.done
            requested_end = seg.end
            before = seg.done
            if dl.resumable:
                headers["Range"] = f"bytes={pos}-{requested_end}"
                validator = if_range_validator(dl)
                if validator:
                    headers["If-Range"] = validator
            try:
                dl.active_connections += 1
                async with self.client.stream("GET", dl.url, headers=headers) as r:
                    if r.status_code in (429, 503):
                        raise ServerBackoff(r.status_code, retry_after_seconds(r.headers.get("retry-after")))
                    r.raise_for_status()
                    if dl.resumable:
                        got_etag = r.headers.get("etag", "")
                        if dl.etag and got_etag and got_etag != dl.etag:
                            raise ResourceChanged("ETag changed during resumable download")
                        got_modified = r.headers.get("last-modified", "")
                        if dl.last_modified and got_modified and got_modified != dl.last_modified:
                            raise ResourceChanged("Last-Modified changed during resumable download")
                        if r.status_code != 206:
                            raise IOError("Le serveur a cesse d'accepter la reprise (Range)")
                        # E2 : la plage recue doit commencer exactement la ou on l'a demandee,
                        # sinon les octets seraient ecrits au mauvais endroit du fichier
                        m = re.fullmatch(r"\s*bytes\s+(\d+)-(\d+)/(\d+)\s*", r.headers.get("content-range", ""))
                        if (not m or int(m.group(1)) != pos or
                                int(m.group(2)) < int(m.group(1)) or
                                int(m.group(2)) > requested_end or int(m.group(3)) != dl.size):
                            raise ResourceChanged(f"Plage inattendue du serveur : {r.headers.get('content-range')!r} "
                                          f"au lieu de {pos}-{requested_end}")
                        response_end = int(m.group(2))
                        # E5 : des octets compresses ne correspondent plus aux positions du fichier
                        if r.headers.get("content-encoding", "identity").lower() not in ("identity", ""):
                            raise IOError("Le serveur compresse une plage d'octets : impossible de la reprendre")
                        chunks = r.aiter_raw(CHUNK)
                    else:
                        chunks = r.aiter_bytes(CHUNK)
                    async for chunk in chunks:
                        if not chunk:
                            continue
                        if dl.resumable:
                            if len(chunk) > response_end - (seg.start + seg.done) + 1:
                                raise ResourceChanged("Response body exceeds its declared byte range")
                            # le segment a pu etre raccourci par _supervise
                            room = seg.end - (seg.start + seg.done) + 1
                            if room <= 0:
                                break
                            chunk = chunk[:room]
                        fh.seek(seg.start + seg.done)
                        written = fh.write(chunk)
                        if written != len(chunk):
                            raise OSError(errno.ENOSPC, "Incomplete write to download file")
                        seg.done += len(chunk)
                        await self._throttle(len(chunk))
                        self.save()
                    if not dl.resumable:
                        if seg.end < 0:          # taille inconnue : fin de flux = fini
                            seg.end = seg.start + seg.done - 1
                            dl.size = seg.done
                        return
                if seg.finished:
                    return
                # E3 : la reponse s'est terminee sans erreur mais trop tot. Si rien n'est arrive,
                # c'est un echec : on attend avant de reessayer (sinon boucle de requetes sans pause).
                if seg.done > before:
                    attempt = 0
                    continue
                raise IOError("Le serveur n'envoie plus de donnees pour ce segment")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Disk-full and changed resources must never be retried as network errors.
                if isinstance(exc, (ResourceChanged, OSError)) and (
                    isinstance(exc, ResourceChanged) or getattr(exc, "errno", None) in (errno.ENOSPC, errno.EDQUOT)
                ):
                    raise
                attempt = 1 if seg.done > before else attempt + 1
                if attempt > MAX_RETRIES or (not dl.resumable and not isinstance(exc, ServerBackoff)):
                    raise
                delay = min(2 ** attempt, 20) * RETRY_DELAY
                if isinstance(exc, ServerBackoff):
                    delay = max(delay, exc.delay)
                await asyncio.sleep(delay)
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
    def _cached_tool(self, name: str, key, find):
        # Appele a chaque rafraichissement de l'interface (chaque seconde) sur la boucle :
        # parcourir le PATH et WinGet a chaque fois coutait ~11 ms.
        now = time.monotonic()
        hit = self._tools.get(name)
        if hit is not None and hit[0] == key and now - hit[1] < TOOL_LOOKUP_TTL:
            return hit[2]
        found = find()
        self._tools[name] = (key, now, found)
        return found

    def ffmpeg(self) -> str | None:
        p = self.settings.get("ffmpeg_path")
        return self._cached_tool("ffmpeg", p, lambda: self._find_ffmpeg(p))

    def _find_ffmpeg(self, p) -> str | None:
        if p and Path(p).is_file() and Path(p).name.lower() in ("ffmpeg", "ffmpeg.exe"):
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

    def deno(self) -> str | None:
        """Moteur JavaScript utilise par yt-dlp pour obtenir toutes les qualites YouTube."""
        return self._cached_tool("deno", None, self._find_deno)

    def _find_deno(self) -> str | None:
        name = "deno.exe" if IS_WINDOWS else "deno"
        local = EXE_DIR / name
        if local.exists():
            return str(local)
        found = shutil.which("deno")
        if found or not IS_WINDOWS:
            return found
        winget = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet"
        if (winget / "Links" / name).exists():
            return str(winget / "Links" / name)
        for exe in (winget / "Packages").glob(f"DenoLand.Deno*/{name}"):
            return str(exe)
        return None

    def _ydl_base_opts(self, dl: Download) -> dict:
        # Pas de User-Agent ni de cookies ici : yt-dlp choisit lui-meme l'identite adaptee a
        # chaque site (YouTube refuse "The page needs to be reloaded" si on lui impose celle
        # du navigateur). Seul le Referer est transmis (utile aux lecteurs integres).
        headers = {k: v for k, v in dl.headers.items() if k.lower() == "referer"}
        opts = {
            "quiet": True, "no_warnings": True, "noprogress": True,
            "noplaylist": True, "http_headers": headers,
            "socket_timeout": 30,
        }
        ff = self.ffmpeg()
        if ff:
            opts["ffmpeg_location"] = ff
        deno = self.deno()
        if deno:
            opts["js_runtimes"] = {"deno": {"path": deno}}
        return opts

    @contextlib.contextmanager
    def _ydl_opts(self, dl: Download, with_cookies: bool | None = None):
        """Options yt-dlp. Les cookies de la page ne sont PAS mis dans les en-tetes (yt-dlp les
        enverrait a tous les serveurs contactes) : ils vont dans un fichier de cookies limite
        au seul site de la page, supprime juste apres."""
        opts = self._ydl_base_opts(dl)
        if with_cookies is None:
            with_cookies = dl.yt_cookies
        cookie = next((v for k, v in dl.headers.items() if k.lower() == "cookie"), "") if with_cookies else ""
        host = urlparse(dl.page_url or dl.url).hostname or ""
        path = None
        if cookie and host:
            fd, path = tempfile.mkstemp(prefix="ck-", suffix=".txt", dir=self.data_dir)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("# Netscape HTTP Cookie File\n")
                for part in cookie.split(";"):
                    name, sep, value = part.strip().partition("=")
                    if sep and name and not any(c in name + value for c in "\t\r\n"):
                        f.write(f"{host}\tFALSE\t/\tFALSE\t0\t{name}\t{value}\n")
            opts["cookiefile"] = path
        try:
            yield opts
        finally:
            if path:
                try:
                    os.remove(path)
                except OSError:
                    pass

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
                fmt, size, ext = best_p["format_id"], fsize(best_p), _safe_ext(best_p.get("ext"))
            else:
                continue          # sans ffmpeg on ne peut pas fusionner video + audio
            label = f"{h}p" + (f" {int(best_v['fps'])}fps" if (best_v.get("fps") or 0) > 30 else "")
            options.append({"id": f"v{h}", "label": label, "format": fmt, "ext": ext, "size": size})
        if not options:
            # flux simple (m3u8 sans variantes, mp4 direct...)
            options.append({"id": "best", "label": "Meilleure qualité", "format": "bv*+ba/b" if has_ff else "b",
                            "ext": "mp4" if has_ff else _safe_ext(info.get("ext")), "size": fsize(info)})
        if best_audio:
            options.append({"id": "audio", "label": "Audio seulement", "format": "ba[ext=m4a]/ba",
                            "ext": _safe_ext(best_audio.get("ext")) if best_audio.get("ext") != "webm" else "m4a",
                            "size": fsize(best_audio)})
        return options

    async def _probe_video(self, dl: Download):
        dl.probe = "probing"
        import importlib.util
        if importlib.util.find_spec("yt_dlp") is None:   # verifie sans charger yt-dlp ici
            dl.probe, dl.probe_error = "failed", "yt-dlp n'est pas installe (pip install yt-dlp)"
            return

        tried, last_err = [], ""
        # 1) la page elle-meme (YouTube, Vimeo, Dailymotion... ~1800 sites)
        # 2) puis les flux detectes par l'extension (m3u8 / mpd / mp4)
        for url in [dl.page_url, *dl.candidates]:
            if not url or url in tried or url.startswith("blob:"):
                continue
            tried.append(url)
            try:
                # d'abord SANS les cookies du navigateur (conseille par yt-dlp, surtout pour
                # YouTube) ; avec, seulement si ca echoue (video privee, reservee aux adultes...)
                has_cookie = any(k.lower() == "cookie" for k in dl.headers)
                info, errors = None, []
                for with_cookies in ([False, True] if has_cookie else [False]):
                    with self._ydl_opts(dl, with_cookies) as opts:
                        kind, payload = await self._yt_process("extract", url, opts, timeout=PROBE_TIMEOUT)
                    if kind == "result" and (payload.get("formats") or payload.get("url")):
                        info, dl.yt_cookies = payload, with_cookies
                        break
                    errors.append(payload if kind != "result" else "Aucun flux video")
                if info is None:
                    raise ValueError(errors[0])
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
                dl.filename = safe_filename(Path(dl.filename).stem + "." + _safe_ext(o["ext"]))
                if option_id == "audio":
                    dl.category = "Musique"
                return
        raise ValueError("Format inconnu")

    async def _run_video(self, dl: Download):
        speed_task = asyncio.create_task(self._measure_speed(dl))
        try:
            await self._video_download(dl)
            dl.status = "completed"
            dl.finished_at = time.time()
            if dl.size <= 0 or dl.downloaded > dl.size:
                dl.size = dl.downloaded
            self._after_complete(dl)
        except asyncio.CancelledError:
            raise                         # pause : le processus yt-dlp est arrete, les .part restent
        except Exception as e:
            dl.status = "error"
            dl.error = str(e).replace("ERROR: ", "")[:300]
        finally:
            speed_task.cancel()
            dl.speed = 0
            dl.active_connections = 0
            self._save_quietly()
            self.wake()

    async def _video_download(self, dl: Download):
        folder = self._target_folder(dl)
        if not dl.path:
            dl.path = str(self._unused_path(folder, dl.filename, dl))   # corrige a la fin avec le vrai nom
        stem = Path(dl.path).stem
        dl.v_base, dl.v_done = 0, 0
        seen_done: set[str] = set()

        def on_progress(d: dict):
            fname = d.get("filename") or ""
            if d["status"] == "downloading":
                dl.v_done = int(d.get("downloaded_bytes") or 0)
                dl.active_connections = 1
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                if total and dl.v_base + total > dl.size:
                    dl.size = int(dl.v_base + total)
            elif d["status"] == "finished" and fname not in seen_done:
                seen_done.add(fname)
                dl.v_base += int(d.get("total_bytes") or d.get("downloaded_bytes") or dl.v_done)
                dl.v_done = 0

        with self._ydl_opts(dl) as opts:
            opts.update({
                "format": dl.video_format or "b",
                "outtmpl": str(folder / (stem + ".%(ext)s")),
                "continuedl": True,
                "concurrent_fragment_downloads": max(1, min(16, dl.connections)),
                "retries": 10, "fragment_retries": 10,
            })
            if opts.get("ffmpeg_location") and "+" in opts["format"]:
                opts["merge_output_format"] = "mp4"
            limit = int(self.settings.get("speed_limit_kbps") or 0)
            if limit > 0:
                opts["ratelimit"] = limit * 1024
            kind, payload = await self._yt_process("download", dl.url, opts, on_progress=on_progress, key=dl.id)
        if kind != "done":
            raise IOError(payload)
        if payload.get("filepath"):
            dl.path = payload["filepath"]
            dl.filename = Path(dl.path).name
        if Path(dl.path).exists():
            dl.size = Path(dl.path).stat().st_size
            dl.v_base, dl.v_done = dl.size, 0

    async def _yt_process(self, func: str, url: str, opts: dict, on_progress=None,
                          timeout: float | None = None, key: str | None = None):
        """Lance yt-dlp dans un processus separe (voir ytworker.py) et attend son resultat
        sans jamais bloquer Rapido. Annulation (pause) ou delai depasse = processus arrete."""
        import multiprocessing as mp
        import queue as queue_mod
        import ytworker
        ctx = mp.get_context("spawn")
        q = ctx.Queue()
        proc = ctx.Process(target=getattr(ytworker, func), args=(url, opts, q), daemon=True)
        proc.start()
        # daemon ne vaut que pour une fermeture normale : si Rapido est tue (plantage,
        # « Fin de tache »), le noyau arrete aussi yt-dlp au lieu de le laisser tourner.
        windows_job.kill_with_this_process(proc.pid)
        if key:
            self._procs[key] = proc
        t0 = time.monotonic()
        try:
            while True:
                try:
                    kind, payload = await asyncio.to_thread(q.get, True, 0.5)
                except queue_mod.Empty:
                    if not proc.is_alive():
                        try:
                            kind, payload = q.get_nowait()
                        except queue_mod.Empty:
                            return "error", f"yt-dlp s'est arrete de facon inattendue (code {proc.exitcode})"
                    elif timeout and time.monotonic() - t0 > timeout:
                        return "error", (f"Analyse trop longue (plus de {int(timeout)} s) : "
                                         "site non pris en charge ou trop lent")
                    else:
                        continue
                if kind == "progress":
                    if on_progress:
                        on_progress(payload)
                    continue
                return kind, payload
        finally:
            if key:
                self._procs.pop(key, None)
            if proc.is_alive():
                proc.terminate()
            await asyncio.to_thread(proc.join, 5)
            q.close()

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
