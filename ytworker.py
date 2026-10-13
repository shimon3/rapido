"""
Rapido - yt-dlp dans un PROCESSUS separe.

Pourquoi : pour YouTube, yt-dlp fait de gros calculs en Python (expressions regulieres sur
des pages de plusieurs Mo). Dans un simple thread, ces calculs gardent le verrou global de
Python (GIL) : l'interface et le serveur de Rapido se figent ("ne repond pas"). Dans un
processus a part, Rapido reste fluide, une analyse trop longue peut etre interrompue, et un
plantage de yt-dlp ne fait pas tomber l'application.

Communication : une file multiprocessing (messages simples, serialisables).
    ("progress", {...})   pendant un telechargement
    ("result", {...})     fin d'une analyse
    ("done", {...})       fin d'un telechargement
    ("error", "message")  echec
"""

from __future__ import annotations

import time

# Champs gardes des formats : de quoi construire la liste des qualites, sans tout copier
_FORMAT_KEYS = ("format_id", "ext", "height", "width", "fps", "vcodec", "acodec",
                "tbr", "abr", "filesize", "filesize_approx", "protocol")


def _slim(info: dict) -> dict:
    if info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise ValueError("Playlist vide")
        info = entries[0]
    return {
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "ext": info.get("ext"),
        "url": bool(info.get("url")),
        "filesize": info.get("filesize"),
        "filesize_approx": info.get("filesize_approx"),
        "tbr": info.get("tbr"),
        "formats": [{k: f.get(k) for k in _FORMAT_KEYS} for f in (info.get("formats") or [])],
    }


def _clean(msg) -> str:
    return str(msg).replace("ERROR: ", "").strip()[:400]


def _busy(seconds: float) -> None:
    """Pour les tests seulement : imite le gros calcul de yt-dlp sur YouTube (expression
    reguliere qui garde le verrou de Python)."""
    import re
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        re.search(r"(a|aa)*c", "a" * 30)    # un seul appel garde le verrou ~0,5 s, comme sur YouTube


def extract(url: str, opts: dict, q) -> None:
    try:
        opts = dict(opts)
        _busy(opts.pop("_test_busy_seconds", 0))
        import yt_dlp
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        q.put(("result", _slim(info or {})))
    except BaseException as e:          # tout remonte au parent, meme un plantage inattendu
        q.put(("error", _clean(e)))


def download(url: str, opts: dict, q) -> None:
    try:
        import yt_dlp
        last = [0.0]

        def hook(d):
            now = time.monotonic()
            if d.get("status") == "downloading" and now - last[0] < 0.3:
                return                   # pas plus de ~3 messages par seconde
            last[0] = now
            q.put(("progress", {
                "status": d.get("status"),
                "filename": d.get("filename") or "",
                "downloaded_bytes": d.get("downloaded_bytes") or 0,
                "total_bytes": d.get("total_bytes") or 0,
                "total_bytes_estimate": d.get("total_bytes_estimate") or 0,
            }))

        opts = {**opts, "progress_hooks": [hook]}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        reqs = (info or {}).get("requested_downloads") or []
        q.put(("done", {"filepath": reqs[0].get("filepath") if reqs else ""}))
    except BaseException as e:
        q.put(("error", _clean(e)))
