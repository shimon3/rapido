"""
Tests de non-regression de Rapido (audit du 2026-10-13).

    pip install pytest
    python -m pytest -q tests

Chaque test reproduit un probleme trouve par l'audit et verifie qu'il ne revient pas :
S1 (CSRF), E1 (suppression des .part d'un autre telechargement), E2 (plage decalee),
E3 (boucle sans pause), E5 (plage compressee), plus l'integrite d'un telechargement
multi-connexions et sa reprise apres un arret brutal.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import os
import random
import re
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("RAPIDO_DATA", tempfile.mkdtemp(prefix="rapido-tests-"))

import engine  # noqa: E402

DATA = random.Random(42).randbytes(3 * 1024 * 1024 + 12345)   # ~3 Mo => 3 segments
SHA = hashlib.sha256(DATA).hexdigest()


# ---------------------------------------------------------------- serveur de test
def make_file_server():
    app = FastAPI()
    app.state.hits = {}
    app.state.accept_encoding = []
    app.state.media_cookies = []
    app.state.dropped = set()

    def parse_range(request: Request):
        m = re.match(r"bytes=(\d+)-(\d*)", request.headers.get("range", ""))
        if not m:
            return None
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else len(DATA) - 1
        return a, min(b, len(DATA) - 1)

    async def body(a, b, delay=0.0):
        pos = a
        while pos <= b:
            yield DATA[pos:min(b + 1, pos + 65536)]
            pos += 65536
            if delay:
                await asyncio.sleep(delay)

    @app.get("/media/{name}")
    async def media(name: str, request: Request):
        """Une 'video' directe (type video/mp4) : yt-dlp la traite comme un lien video simple."""
        n = len(DATA)
        app.state.media_cookies.append((name, request.headers.get("cookie", "")))
        if name.startswith("private") and "session=ok" not in request.headers.get("cookie", ""):
            return Response(b"connexion requise", status_code=403)
        rng = parse_range(request)
        delay = 0.08 if name.startswith("slow") else 0.0
        h = {"Content-Type": "video/mp4", "Accept-Ranges": "bytes"}
        if rng is None:
            return StreamingResponse(body(0, n - 1, delay), headers={**h, "Content-Length": str(n)})
        a, b = rng
        return StreamingResponse(body(a, b, delay), status_code=206, headers={
            **h, "Content-Range": f"bytes {a}-{b}/{n}", "Content-Length": str(b - a + 1)})

    @app.get("/{mode}/fichier.bin")
    async def serve(mode: str, request: Request):
        app.state.hits[mode] = app.state.hits.get(mode, 0) + 1
        app.state.accept_encoding.append(request.headers.get("accept-encoding", ""))
        rng = parse_range(request)
        n = len(DATA)
        if mode == "ignore" or (mode == "switch" and rng != (0, 0)) or (mode == "dropfull" and rng == (0, 0)):
            # annonce Accept-Ranges mais renvoie toujours le fichier entier en 200
            return StreamingResponse(body(0, n - 1), headers={"Content-Length": str(n), "Accept-Ranges": "bytes"})
        if mode in ("drop", "dropfull") and rng != (0, 0):
            # coupure reseau : la premiere reponse de chaque position s'arrete en plein corps
            a, b = (0, n - 1) if mode == "dropfull" or rng is None else rng
            key = (mode, a)
            first = key not in app.state.dropped
            app.state.dropped.add(key)

            async def cut():
                sent = 0
                async for chunk in body(a, b):
                    if first and sent >= 200_000:
                        raise ConnectionResetError("coupure simulee")
                    sent += len(chunk)
                    yield chunk
            if mode == "dropfull":
                return StreamingResponse(cut(), headers={"Content-Length": str(n)})
            return StreamingResponse(cut(), status_code=206, headers={
                "Content-Range": f"bytes {a}-{b}/{n}", "Content-Length": str(b - a + 1)})
        if rng is None:
            return StreamingResponse(body(0, n - 1), headers={"Content-Length": str(n), "Accept-Ranges": "bytes"})
        a, b = rng
        if mode == "badrange" and a > 0:
            # serveur menteur : renvoie toujours le debut du fichier, en le declarant
            a2, b2 = 0, b - a
            return StreamingResponse(body(a2, b2), status_code=206, headers={
                "Content-Range": f"bytes {a2}-{b2}/{n}", "Content-Length": str(b2 - a2 + 1)})
        if mode == "gzip" and a > 0:
            raw = gzip.compress(DATA[a:b + 1])
            return Response(raw, status_code=206, headers={
                "Content-Range": f"bytes {a}-{b}/{n}", "Content-Encoding": "gzip"})
        if mode == "empty" and a > 0:
            return Response(b"", status_code=206, headers={"Content-Range": f"bytes {a}-{b}/{n}"})
        delay = 0.05 if mode == "slow" else 0.0
        return StreamingResponse(body(a, b, delay), status_code=206, headers={
            "Content-Range": f"bytes {a}-{b}/{n}", "Content-Length": str(b - a + 1)})

    return app


@pytest.fixture(scope="module")
def server():
    import uvicorn
    app = make_file_server()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    t = threading.Thread(target=srv.run, kwargs={"sockets": [sock]}, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield app, f"http://127.0.0.1:{port}"
    srv.should_exit = True
    t.join(5)


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    monkeypatch.setattr(engine, "RETRY_DELAY", 0.01)
    monkeypatch.setattr(engine, "MAX_RETRIES", 2)


def run_download(url: str, data_dir: Path, *, pause_after: float | None = None,
                 restart: bool = False, timeout: float = 60):
    """Telecharge avec un vrai Manager ; option : pause puis reprise (avec redemarrage)."""

    async def main():
        m = engine.Manager(data_dir, port=0)
        m.settings["download_dir"] = str(data_dir / "dl")
        m.settings["show_complete_dialog"] = False
        m.settings["monitor_clipboard"] = False
        await m.start()
        dl = m.add(url, "fichier.bin", connections=8)
        dl_id = dl.id
        try:
            if pause_after is not None:
                await asyncio.sleep(pause_after)
                await m.pause(dl_id)
                done_before = m.downloads[dl_id].downloaded
                assert 0 < done_before < len(DATA), "la pause doit tomber en plein telechargement"
                if restart:
                    await m.stop()
                    m = engine.Manager(data_dir, port=0)          # comme une relance de Rapido
                    m.settings["download_dir"] = str(data_dir / "dl")
                    m.settings["show_complete_dialog"] = False
                    m.settings["monitor_clipboard"] = False
                    await m.start()
                    assert m.downloads[dl_id].downloaded == done_before, "la progression doit etre conservee"
                m.resume(dl_id)
            t0 = time.time()
            while time.time() - t0 < timeout:
                d = m.downloads[dl_id]
                if d.status in ("completed", "error"):
                    return d
                await asyncio.sleep(0.05)
            raise AssertionError("telechargement trop long")
        finally:
            await m.stop()

    return asyncio.run(main())


def sha_file(p: str) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------- moteur
def test_download_multi_connexions_integre(server, tmp_path):
    app, base = server
    d = run_download(f"{base}/ok/fichier.bin", tmp_path)
    assert d.status == "completed", d.error
    assert len(d.segments) >= 3
    assert sha_file(d.path) == SHA


def test_reprise_apres_pause_et_redemarrage(server, tmp_path):
    app, base = server
    d = run_download(f"{base}/slow/fichier.bin", tmp_path, pause_after=0.6, restart=True)
    assert d.status == "completed", d.error
    assert sha_file(d.path) == SHA


def test_E5_octets_bruts_demandes(server, tmp_path):
    app, base = server
    app.state.accept_encoding.clear()
    run_download(f"{base}/ok/fichier.bin", tmp_path)
    assert app.state.accept_encoding and all(h == "identity" for h in app.state.accept_encoding)


def test_E5_plage_compressee_refusee(server, tmp_path):
    app, base = server
    d = run_download(f"{base}/gzip/fichier.bin", tmp_path)
    assert d.status == "error" and "compresse" in d.error


def test_E2_plage_decalee_refusee(server, tmp_path):
    app, base = server
    d = run_download(f"{base}/badrange/fichier.bin", tmp_path)
    assert d.status == "error" and "Plage inattendue" in d.error
    assert not Path(d.path).exists(), "un fichier corrompu ne doit jamais etre marque termine"


def test_E3_pas_de_boucle_sur_reponse_vide(server, tmp_path):
    app, base = server
    app.state.hits["empty"] = 0
    d = run_download(f"{base}/empty/fichier.bin", tmp_path, timeout=20)
    assert d.status == "error"
    # 1 sonde + 1 segment qui reussit (le debut) + quelques essais par segment, pas des centaines
    assert app.state.hits["empty"] < 25, app.state.hits["empty"]


# ---------------------------------------------------------------- E1
def test_coupure_reseau_en_plein_segment_reprend_sans_trou(server, tmp_path):
    app, base = server
    d = run_download(f"{base}/drop/fichier.bin", tmp_path)
    assert d.status == "completed", d.error
    assert sha_file(d.path) == SHA
    assert app.state.dropped, "la coupure doit avoir eu lieu"


def test_plusieurs_pauses_et_reprises_fichier_identique(server, tmp_path):
    async def main():
        m = engine.Manager(tmp_path, port=0)
        m.settings.update(download_dir=str(tmp_path / "dl"), show_complete_dialog=False,
                          monitor_clipboard=False)
        await m.start()
        dl = m.add(f"{base}/slow/fichier.bin", "fichier.bin", connections=8)
        try:
            # Chaque pause suit l'arrivee de nouveaux octets (et non un delai fixe) : elle tombe
            # en plein telechargement quelle que soit la vitesse de la machine.
            vu = 0
            for _ in range(3):
                t0 = time.time()
                while m.downloads[dl.id].downloaded <= vu:
                    assert m.downloads[dl.id].status != "completed", "termine avant la pause"
                    assert time.time() - t0 < 30, "aucun progres"
                    await asyncio.sleep(0.01)
                await m.pause(dl.id)
                assert m.downloads[dl.id].status == "paused"
                vu = m.downloads[dl.id].downloaded
                assert 0 < vu < len(DATA), vu
                await asyncio.sleep(0.2)
                assert m.downloads[dl.id].downloaded == vu, "rien ne doit s'ecrire pendant la pause"
                m.resume(dl.id)
            t0 = time.time()
            while m.downloads[dl.id].status not in ("completed", "error"):
                assert time.time() - t0 < 60, "telechargement trop long"
                await asyncio.sleep(0.05)
            return m.downloads[dl.id]
        finally:
            await m.stop()

    _, base = server
    d = asyncio.run(main())
    assert d.status == "completed", d.error
    assert sha_file(d.path) == SHA


def test_serveur_qui_ignore_range_telecharge_en_un_seul_flux(server, tmp_path):
    _, base = server
    d = run_download(f"{base}/ignore/fichier.bin", tmp_path)
    assert d.status == "completed", d.error
    assert not d.resumable
    assert sha_file(d.path) == SHA


def test_serveur_qui_cesse_d_accepter_range_ne_corrompt_rien(server, tmp_path):
    _, base = server
    d = run_download(f"{base}/switch/fichier.bin", tmp_path)
    assert d.status == "error"
    assert "Range" in d.error
    assert not Path(d.path).exists(), "un fichier incomplet ne doit jamais etre presente comme termine"


def test_coupure_sans_reprise_possible_puis_reprendre_recommence_a_zero(server, tmp_path):
    async def main():
        m = engine.Manager(tmp_path, port=0)
        m.settings.update(download_dir=str(tmp_path / "dl"), show_complete_dialog=False,
                          monitor_clipboard=False)
        await m.start()
        dl = m.add(f"{base}/dropfull/fichier.bin", "fichier.bin", connections=8)
        try:
            t0 = time.time()
            while m.downloads[dl.id].status != "error":
                assert m.downloads[dl.id].status != "completed", "la coupure doit etre signalee"
                assert time.time() - t0 < 30
                await asyncio.sleep(0.05)
            assert not m.downloads[dl.id].resumable
            m.resume(dl.id)
            while m.downloads[dl.id].status not in ("completed", "error"):
                assert time.time() - t0 < 60
                await asyncio.sleep(0.05)
            return m.downloads[dl.id]
        finally:
            await m.stop()

    _, base = server
    d = asyncio.run(main())
    assert d.status == "completed", d.error
    assert sha_file(d.path) == SHA


def test_E1_suppression_ne_touche_pas_un_autre_telechargement(tmp_path):
    names = ["film.mp4.part", "film (1).mp4.part", "film.v2.mp4.part", "film.f137.mp4.part",
             "film.f137.mp4.part-Frag3.part", "film.mp4.ytdl", "film.temp.mp4", "filmographie.zip.part"]
    for n in names:
        (tmp_path / n).write_text("x")
    http = engine.Download(id="a", url="u", kind="http", path=str(tmp_path / "film.mp4"))
    video = engine.Download(id="b", url="u", kind="video", path=str(tmp_path / "film.mp4"))
    assert {p.name for p in engine.Manager._temp_files(http)} == {"film.mp4.part"}
    assert {p.name for p in engine.Manager._temp_files(video)} == {
        "film.mp4.part", "film.f137.mp4.part", "film.f137.mp4.part-Frag3.part", "film.mp4.ytdl", "film.temp.mp4"}


# ---------------------------------------------------------------- API (S1 et protections)
@pytest.fixture(scope="module")
def api():
    from fastapi.testclient import TestClient
    import app as rapido
    rapido.manager.settings["monitor_clipboard"] = False
    rapido.manager.open_window = lambda *a, **k: None
    with TestClient(rapido.app, base_url="http://127.0.0.1:9614",
                    headers={"Authorization":"Bearer "+rapido._LOCAL_AUTH.token_for_trusted_transport()}) as c:
        yield c, rapido


JSON = {"Content-Type": "application/json"}
SELF = "http://127.0.0.1:9614"


def test_S1_requete_venant_d_un_autre_site_refusee(api):
    c, _ = api
    for site in ("cross-site", "same-site"):      # same-site = autre port sur 127.0.0.1
        r = c.post("/api/bulk/resume", json={}, headers={**JSON, "Origin": SELF, "Sec-Fetch-Site": site})
        assert r.status_code == 403, site
    # une page d'un autre site qui ouvre la fenetre de Rapido
    assert c.get("/w?view=capture&id=abc", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    # l'interface de Rapido elle-meme
    r = c.post("/api/bulk/resume", json={}, headers={**JSON, "Origin": SELF, "Sec-Fetch-Site": "same-origin"})
    assert r.status_code == 200


def test_S1_liste_vide_ne_veut_pas_dire_tout(api):
    c, rapido = api
    before = len(rapido.manager.downloads)
    c.post("/api/downloads", json={"url": "http://127.0.0.1:9/a.zip", "later": True}, headers=JSON)
    c.post("/api/downloads", json={"url": "http://127.0.0.1:9/b.zip", "later": True}, headers=JSON)
    assert c.post("/api/bulk/delete", json={}, headers=JSON).status_code == 200
    assert len(rapido.manager.downloads) == before + 2
    assert c.post("/api/bulk/delete", json={"all": True}, headers=JSON).status_code == 400


def test_S1_window_html_valide_l_identifiant():
    src = (ROOT / "window.html").read_text("utf-8")
    assert "const ID = /^[0-9a-f]{6,32}$/.test(" in src


def test_protections_de_base(api):
    c, _ = api
    assert c.get("/api/state", headers={"Host": "evil.example:9614"}).status_code == 403          # DNS rebinding
    assert c.post("/api/show", json={}, headers={**JSON, "Origin": "https://evil.example"}).status_code == 403
    r = c.post("/api/downloads", content=b'{"url":"http://x.y/a.exe"}',
               headers={"Content-Type": "text/plain;x=application/json"})
    assert r.status_code == 415
    assert c.post("/api/capture", json={"url": "file:///etc/passwd"}, headers=JSON).status_code == 400
    csp = c.get("/").headers.get("content-security-policy", "")
    assert "script-src 'sha256-" in csp and "unsafe-eval" not in csp


# ---------------------------------------------------------------- videos : yt-dlp dans un processus
def _manager(data_dir: Path):
    m = engine.Manager(data_dir, port=0)
    m.settings.update(download_dir=str(data_dir / "dl"), show_complete_dialog=False, monitor_clipboard=False)
    m.open_window = lambda *a, **k: None
    return m


def test_video_analyse_et_telechargement_sans_figer_rapido(server, tmp_path):
    """Avant : yt-dlp tournait dans un thread et figeait Rapido ("ne repond pas")."""
    app, base = server

    async def main():
        m = _manager(tmp_path)
        await m.start()
        lags = []

        async def ticker():               # mesure la reactivite de Rapido pendant l'analyse
            while True:
                t = time.perf_counter()
                await asyncio.sleep(0.02)
                lags.append(time.perf_counter() - t)

        tk = asyncio.create_task(ticker())
        try:
            dl = m.capture_video(f"{base}/media/clip.mp4")
            for _ in range(600):
                if dl.probe in ("ready", "failed"):
                    break
                await asyncio.sleep(0.05)
            assert dl.probe == "ready", dl.probe_error
            assert m._procs == {}, "aucun processus ne doit rester apres l'analyse"
            m.confirm(dl.id, "clip", None, later=False)
            for _ in range(1200):
                if dl.status in ("completed", "error"):
                    break
                await asyncio.sleep(0.05)
            assert dl.status == "completed", dl.error
            return dl, max(lags), len(lags), sum(lag >= 0.25 for lag in lags)
        finally:
            tk.cancel()
            await m.stop()

    dl, worst, samples, stalls = asyncio.run(main())
    assert sha_file(dl.path) == SHA
    assert worst < 0.5, (f"Rapido s'est fige {worst:.3f} s; "
                         f"{stalls}/{samples} echantillons >= 0.25 s; seuil strict 0.5 s")


def test_video_analyse_lourde_ne_fige_pas_rapido(server, tmp_path, monkeypatch):
    """Reproduit le gel vu sur YouTube : 3 s de calcul intensif pendant l'analyse.
    Dans un thread (ancienne version), Rapido etait bloque pendant tout ce temps."""
    app, base = server
    orig = engine.Manager._ydl_base_opts
    monkeypatch.setattr(engine.Manager, "_ydl_base_opts",
                        lambda self, dl: {**orig(self, dl), "_test_busy_seconds": 3})

    async def main():
        m = _manager(tmp_path)
        await m.start()
        lags = []

        async def ticker():
            while True:
                t = time.perf_counter()
                await asyncio.sleep(0.02)
                lags.append(time.perf_counter() - t)

        tk = asyncio.create_task(ticker())
        try:
            dl = m.capture_video(f"{base}/media/clip.mp4")
            for _ in range(600):
                if dl.probe in ("ready", "failed"):
                    break
                await asyncio.sleep(0.05)
            assert dl.probe == "ready", dl.probe_error
            return max(lags)
        finally:
            tk.cancel()
            await m.stop()

    worst = asyncio.run(main())
    assert worst < 0.25, f"Rapido s'est fige {worst:.2f} s pendant l'analyse"


def test_video_pause_arrete_le_processus(server, tmp_path):
    app, base = server

    async def main():
        m = _manager(tmp_path)
        await m.start()
        try:
            dl = m.capture_video(f"{base}/media/slow-clip.mp4")
            for _ in range(600):
                if dl.probe in ("ready", "failed"):
                    break
                await asyncio.sleep(0.05)
            assert dl.probe == "ready", dl.probe_error
            m.confirm(dl.id, "lent", None, later=False)
            for _ in range(600):
                if dl.id in m._procs and dl.downloaded > 0:
                    break
                await asyncio.sleep(0.05)
            proc = m._procs[dl.id]
            await m.pause(dl.id)
            await asyncio.sleep(0.5)
            assert dl.status == "paused"
            assert not proc.is_alive(), "le processus yt-dlp doit etre arrete a la pause"
            assert dl.id not in m._procs
        finally:
            await m.stop()

    asyncio.run(main())


def test_ouvrir_un_programme_puis_annuler_n_est_pas_une_erreur(api, monkeypatch, tmp_path):
    """Sur le PC : Ouvrir un .exe puis annuler la demande Windows affichait 'Internal Server Error'."""
    c, rapido = api
    f = tmp_path / "setup.exe"
    f.write_bytes(b"MZ")
    dl = rapido.manager.add("http://127.0.0.1:9/setup.exe", "setup.exe", later=True)
    dl.path, dl.status = str(f), "completed"

    def annule(*a, **k):
        e = OSError(22, "L'operation a ete annulee par l'utilisateur")
        e.winerror = 1223
        raise e

    monkeypatch.setattr(rapido.platform, "system", lambda: "Windows")
    monkeypatch.setattr(rapido.os, "startfile", annule, raising=False)
    r = c.post(f"/api/downloads/{dl.id}/open", json={}, headers=JSON)
    assert r.status_code == 200, r.text

    def autre(*a, **k):
        e = OSError(2, "Fichier introuvable")
        e.winerror = 2
        raise e

    monkeypatch.setattr(rapido.os, "startfile", autre, raising=False)
    r = c.post(f"/api/downloads/{dl.id}/open", json={}, headers=JSON)
    assert r.status_code == 400 and "Impossible d'ouvrir" in r.json()["detail"]


def test_video_sans_cookies_d_abord_puis_avec_si_necessaire(server, tmp_path):
    """YouTube refusait la video quand Rapido lui envoyait les cookies du navigateur.
    Desormais : d'abord sans cookies ; avec, seulement si la video l'exige."""
    app, base = server

    async def probe(m, name):
        dl = m.capture_video(f"{base}/media/{name}", headers={"Cookie": "session=ok"})
        for _ in range(600):
            if dl.probe in ("ready", "failed"):
                break
            await asyncio.sleep(0.05)
        return dl

    async def main():
        m = _manager(tmp_path)
        await m.start()
        try:
            app.state.media_cookies.clear()
            public = await probe(m, "public.mp4")
            sent_public = [c for n, c in app.state.media_cookies if n == "public.mp4"]
            private = await probe(m, "private.mp4")
            return public, sent_public, private
        finally:
            await m.stop()

    public, sent_public, private = asyncio.run(main())
    assert public.probe == "ready" and public.yt_cookies is False
    assert sent_public and all(c == "" for c in sent_public), "aucun cookie pour une video publique"
    assert private.probe == "ready", private.probe_error
    assert private.yt_cookies is True


def test_ouvrir_un_programme_ne_fige_pas_le_serveur(api, monkeypatch, tmp_path):
    """os.startfile attend la reponse a la demande UAC (WinError 1223 = annulee) :
    sur la boucle du serveur, tout Rapido etait fige pendant ce temps."""
    c, rapido = api
    f = tmp_path / "setup.exe"
    f.write_bytes(b"MZ")
    dl = rapido.manager.add("http://127.0.0.1:9/setup.exe", "setup.exe", later=True)
    dl.path, dl.status = str(f), "completed"
    gate, started = threading.Event(), threading.Event()

    def demande_uac(*a, **k):
        started.set()
        gate.wait(10)

    monkeypatch.setattr(rapido.platform, "system", lambda: "Windows")
    monkeypatch.setattr(rapido.os, "startfile", demande_uac, raising=False)
    monkeypatch.setattr(rapido.subprocess, "Popen", lambda *a, **k: demande_uac())
    replies = []
    opener = threading.Thread(target=lambda: replies.append(
        c.post(f"/api/downloads/{dl.id}/open", json={}, headers=JSON)))
    opener.start()
    try:
        assert started.wait(5)
        t0 = time.monotonic()
        assert c.get("/api/state").status_code == 200
        assert time.monotonic() - t0 < 2, "le serveur doit repondre pendant la demande Windows"
    finally:
        gate.set()
        opener.join(10)
    assert replies and replies[0].status_code == 200


class _VerrouEtat:
    """Simule un antivirus ou l'indexeur qui tient downloads.json ouvert."""

    def __init__(self, monkeypatch, echecs):
        self.reel, self.echecs, self.vus = os.replace, echecs, 0
        monkeypatch.setattr(engine.os, "replace", self)

    def __call__(self, src, dst):
        if str(dst).endswith("downloads.json") and self.vus < self.echecs:
            self.vus += 1
            raise PermissionError(13, "fichier verrouille", str(dst))
        return self.reel(src, dst)


def test_verrou_passager_de_l_etat_est_absorbe(monkeypatch, tmp_path):
    m = engine.Manager(tmp_path, port=0)
    verrou = _VerrouEtat(monkeypatch, 2)
    dl = m.add("http://127.0.0.1:9/a.bin", "a.bin", later=True)     # save(force=True)
    assert verrou.vus == 2
    assert json.loads((tmp_path / "downloads.json").read_text("utf-8"))[0]["id"] == dl.id


def test_verrou_persistant_de_l_etat_reste_signale_pour_les_sauvegardes_forcees(monkeypatch, tmp_path):
    m = engine.Manager(tmp_path, port=0)
    _VerrouEtat(monkeypatch, 10_000)
    with pytest.raises(PermissionError):
        m.save(force=True)        # le transfert natif exige une ecriture durable


def test_verrou_de_l_etat_n_interrompt_pas_un_telechargement(server, tmp_path, monkeypatch):
    _, base = server
    erreurs = []

    async def main():
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(lambda _loop, ctx: erreurs.append(ctx.get("exception")))
        m = engine.Manager(tmp_path, port=0)
        m.settings.update(download_dir=str(tmp_path / "dl"), show_complete_dialog=False,
                          monitor_clipboard=False)
        await m.start()
        dl = m.add(f"{base}/slow/fichier.bin", "fichier.bin", connections=4)
        try:
            await asyncio.sleep(0.3)
            verrou = _VerrouEtat(monkeypatch, 10_000)     # verrouille jusqu'a la fin
            t0 = time.time()
            while m.downloads[dl.id].status not in ("completed", "error"):
                assert time.time() - t0 < 60
                await asyncio.sleep(0.05)
            await asyncio.sleep(0.2)
            monkeypatch.setattr(engine.os, "replace", verrou.reel)
            assert verrou.vus > 0, "le verrou doit avoir ete rencontre"
            return m.downloads[dl.id]
        finally:
            await m.stop()

    d = asyncio.run(main())
    assert d.status == "completed", d.error
    assert sha_file(d.path) == SHA
    assert not [e for e in erreurs if e is not None], erreurs


def test_fin_de_telechargement_n_ecrase_pas_un_fichier_apparu_entre_temps(server, tmp_path):
    """Un fichier du meme nom cree pendant le telechargement (copie du navigateur, telechargement
    en pause depuis des jours) ne doit pas etre remplace par os.replace a la fin."""
    _, base = server

    async def main():
        m = engine.Manager(tmp_path, port=0)
        m.settings.update(download_dir=str(tmp_path / "dl"), show_complete_dialog=False,
                          monitor_clipboard=False)
        await m.start()
        dl = m.add(f"{base}/slow/fichier.bin", "fichier.bin", connections=4)
        try:
            t0 = time.time()
            while not m.downloads[dl.id].path or m.downloads[dl.id].downloaded == 0:
                assert time.time() - t0 < 30
                await asyncio.sleep(0.02)
            prevu = Path(m.downloads[dl.id].path)
            prevu.write_bytes(b"fichier de l'utilisateur")
            while m.downloads[dl.id].status not in ("completed", "error"):
                assert time.time() - t0 < 60
                await asyncio.sleep(0.05)
            return prevu, m.downloads[dl.id]
        finally:
            await m.stop()

    prevu, d = asyncio.run(main())
    assert prevu.read_bytes() == b"fichier de l'utilisateur"
    assert d.status == "completed", d.error
    assert Path(d.path) != prevu and Path(d.path).name == "fichier (1).bin"
    assert d.filename == "fichier (1).bin"
    assert sha_file(d.path) == SHA
    assert not Path(str(prevu) + ".part").exists()


@pytest.mark.parametrize("statut", ["paused", "error", "queued"])
def test_supprimer_un_telechargement_inacheve_n_efface_pas_un_fichier_du_meme_nom(tmp_path, statut):
    """Inacheve, dl.path n'est qu'un nom prevu : un fichier de l'utilisateur peut porter ce nom."""
    dossier = tmp_path / "dl"
    dossier.mkdir()
    a_l_utilisateur = dossier / "rapport.pdf"
    a_l_utilisateur.write_bytes(b"document personnel")
    partiel = dossier / "rapport.pdf.part"
    partiel.write_bytes(b"debut")

    async def main():
        m = engine.Manager(tmp_path, port=0)
        dl = m.add("http://127.0.0.1:9/rapport.pdf", "rapport.pdf", later=True)
        dl.path, dl.status = str(a_l_utilisateur), statut
        await m.remove(dl.id, delete_file=True)

    asyncio.run(main())
    assert a_l_utilisateur.read_bytes() == b"document personnel"
    assert not partiel.exists(), "le fichier partiel de Rapido est bien supprime"


def test_supprimer_un_telechargement_termine_efface_son_fichier(tmp_path):
    fichier = tmp_path / "fini.zip"
    fichier.write_bytes(b"ok")

    async def main():
        m = engine.Manager(tmp_path, port=0)
        dl = m.add("http://127.0.0.1:9/fini.zip", "fini.zip", later=True)
        dl.path, dl.status = str(fichier), "completed"
        await m.remove(dl.id, delete_file=True)

    asyncio.run(main())
    assert not fichier.exists()


def test_ouvrir_refuse_un_telechargement_inacheve(api, monkeypatch, tmp_path):
    """Inacheve, dl.path n'est qu'un nom prevu : il peut designer un autre fichier (programme)."""
    c, rapido = api
    autre = tmp_path / "setup.exe"
    autre.write_bytes(b"MZ")
    dl = rapido.manager.add("http://127.0.0.1:9/setup.exe", "setup.exe", later=True)
    dl.path, dl.status = str(autre), "paused"
    lances = []
    monkeypatch.setattr(rapido.platform, "system", lambda: "Windows")
    monkeypatch.setattr(rapido.os, "startfile", lambda *a, **k: lances.append(a), raising=False)
    monkeypatch.setattr(rapido.subprocess, "Popen", lambda *a, **k: lances.append(a))
    r = c.post(f"/api/downloads/{dl.id}/open", json={}, headers=JSON)
    assert r.status_code == 409, r.text
    assert lances == []
    # Montrer le dossier reste possible.
    r = c.post(f"/api/downloads/{dl.id}/open?folder=true", json={}, headers=JSON)
    assert r.status_code == 200


def test_reprise_apres_fichier_partiel_raccourci_recommence_sans_corruption(server, tmp_path):
    """Un .part raccourci entre la pause et la reprise (outil de nettoyage, erreur disque) :
    la progression enregistree ne correspond plus aux octets presents."""
    _, base = server

    async def main():
        m = engine.Manager(tmp_path, port=0)
        m.settings.update(download_dir=str(tmp_path / "dl"), show_complete_dialog=False,
                          monitor_clipboard=False)
        await m.start()
        dl = m.add(f"{base}/slow/fichier.bin", "fichier.bin", connections=8)
        try:
            await asyncio.sleep(0.6)
            await m.pause(dl.id)
            assert 0 < m.downloads[dl.id].downloaded < len(DATA)
            with open(m.downloads[dl.id].path + ".part", "r+b") as f:
                f.truncate(100_000)
            m.resume(dl.id)
            t0 = time.time()
            while m.downloads[dl.id].status not in ("completed", "error"):
                assert time.time() - t0 < 60
                await asyncio.sleep(0.05)
            return m.downloads[dl.id]
        finally:
            await m.stop()

    d = asyncio.run(main())
    assert d.status == "completed", d.error
    assert sha_file(d.path) == SHA


def test_dossier_de_telechargement_impossible_a_creer_n_est_pas_applique(api, tmp_path):
    c, rapido = api
    avant = dict(rapido.manager.settings)
    fichier = tmp_path / "un-fichier.txt"
    fichier.write_text("x")
    r = c.put("/api/settings", json={"download_dir": str(fichier / "sous-dossier"), "max_concurrent": 5},
              headers=JSON)
    assert r.status_code == 400, r.text
    assert rapido.manager.settings["download_dir"] == avant["download_dir"]
    assert rapido.manager.settings["max_concurrent"] == avant["max_concurrent"], "rien n'est applique"


def _unlink_verrouille(monkeypatch, suffixe):
    reel = Path.unlink

    def unlink(self, *a, **k):
        if self.name.endswith(suffixe):
            raise PermissionError(13, "fichier verrouille", str(self))
        return reel(self, *a, **k)
    monkeypatch.setattr(Path, "unlink", unlink)


def test_supprimer_avec_fichier_partiel_verrouille_retire_quand_meme_l_entree(tmp_path, monkeypatch):
    async def main():
        m = engine.Manager(tmp_path, port=0)
        dl = m.add("http://127.0.0.1:9/gros.iso", "gros.iso", later=True)
        dl.path, dl.status = str(tmp_path / "gros.iso"), "paused"
        (tmp_path / "gros.iso.part").write_bytes(b"debut")
        _unlink_verrouille(monkeypatch, ".part")
        await m.remove(dl.id)
        return m, dl.id

    m, dl_id = asyncio.run(main())
    assert dl_id not in m.downloads
    assert dl_id not in engine.Manager(tmp_path, port=0).downloads, "la suppression est enregistree"


def test_supprimer_un_fichier_termine_verrouille_garde_l_entree_et_le_signale(tmp_path, monkeypatch):
    fichier = tmp_path / "fini.zip"
    fichier.write_bytes(b"ok")

    async def main():
        m = engine.Manager(tmp_path, port=0)
        dl = m.add("http://127.0.0.1:9/fini.zip", "fini.zip", later=True)
        dl.path, dl.status = str(fichier), "completed"
        _unlink_verrouille(monkeypatch, ".zip")
        with pytest.raises(PermissionError):
            await m.remove(dl.id, delete_file=True)
        return m, dl.id

    m, dl_id = asyncio.run(main())
    assert dl_id in m.downloads, "l'entree reste tant que le fichier demande n'est pas efface"
    assert fichier.exists()


def test_api_suppression_d_un_fichier_verrouille_repond_409(api, monkeypatch, tmp_path):
    c, rapido = api
    fichier = tmp_path / "pris.zip"
    fichier.write_bytes(b"ok")
    dl = rapido.manager.add("http://127.0.0.1:9/pris.zip", "pris.zip", later=True)
    dl.path, dl.status = str(fichier), "completed"
    autre = rapido.manager.add("http://127.0.0.1:9/autre.zip", "autre.zip", later=True)
    _unlink_verrouille(monkeypatch, "pris.zip")
    r = c.delete(f"/api/downloads/{dl.id}?delete_file=true", headers=JSON)
    assert r.status_code == 409 and "supprimer" in r.json()["detail"]
    assert dl.id in rapido.manager.downloads
    r = c.post("/api/bulk/delete", json={"ids": [dl.id, autre.id], "delete_file": True}, headers=JSON)
    assert r.status_code == 409 and "pris.zip" in r.json()["detail"]
    assert autre.id not in rapido.manager.downloads, "les autres elements sont quand meme traites"
    assert dl.id in rapido.manager.downloads


def test_ajouter_plusieurs_liens_ne_sauvegarde_qu_une_fois(api, monkeypatch):
    """Coller N liens faisait N sauvegardes completes de l'historique sur la boucle."""
    c, rapido = api
    sauvegardes = []
    reel = rapido.manager.save
    monkeypatch.setattr(rapido.manager, "save", lambda *a, **k: (sauvegardes.append(k), reel(*a, **k))[1])
    liens = "\n".join(f"http://127.0.0.1:9/lot/{i}.zip" for i in range(200))
    r = c.post("/api/downloads", json={"url": liens, "later": True}, headers=JSON)
    assert r.status_code == 200 and len(r.json()) == 200
    forcees = [k for k in sauvegardes if k.get("force")]
    assert len(forcees) == 1, len(forcees)
    relu = engine.Manager(rapido.manager.data_dir, port=0)
    assert sum(1 for d in relu.downloads.values() if "/lot/" in d.url) == 200


@pytest.mark.parametrize("action,statut", [("resume", "paused"), ("pause", "queued"), ("delete", "paused")])
def test_actions_groupees_sauvegardent_une_seule_fois(api, monkeypatch, action, statut):
    c, rapido = api
    ids = []
    for i in range(200):
        dl = rapido.manager.add(f"http://127.0.0.1:9/grp/{action}/{i}.zip", f"{i}.zip", later=True,
                                persist=False)
        dl.status = statut
        ids.append(dl.id)
    rapido.manager.save(force=True)
    sauvegardes = []
    reel = rapido.manager.save

    def compter(*a, **k):
        # Seules comptent les sauvegardes faites par l'action groupee : les telechargements
        # repris par un cas precedent echouent et sauvegardent en arriere-plan.
        import inspect
        if any(f.function == "bulk" for f in inspect.stack()):
            sauvegardes.append(k)
        return reel(*a, **k)
    monkeypatch.setattr(rapido.manager, "save", compter)
    r = c.post(f"/api/bulk/{action}", json={"ids": ids}, headers=JSON)
    assert r.status_code == 200, r.text
    assert len([k for k in sauvegardes if k.get("force")]) == 1
    relu = engine.Manager(rapido.manager.data_dir, port=0)
    restants = [d for d in relu.downloads.values() if f"/grp/{action}/" in d.url]
    if action == "delete":
        assert restants == []
    else:
        attendu = {"resume": "queued", "pause": "paused"}[action]
        assert len(restants) == 200 and {d.status for d in restants} == {attendu}


def test_sauvegarde_de_progression_ne_bloque_pas_la_boucle_si_le_fichier_est_verrouille(monkeypatch, tmp_path):
    """La sauvegarde de progression (toutes les 2 s) est reprise au tour suivant :
    elle ne doit pas attendre la fin de l'analyse antivirus sur la boucle du serveur."""
    m = engine.Manager(tmp_path, port=0)
    m.add("http://127.0.0.1:9/a.zip", "a.zip", later=True)
    verrou = _VerrouEtat(monkeypatch, 10_000)
    attentes = []
    # Pas de seuil de duree (l'ecriture elle-meme peut prendre ~250 ms sous antivirus) :
    # on verifie directement qu'aucune attente n'a eu lieu et qu'il n'y a qu'un essai.
    monkeypatch.setattr(engine.time, "sleep", attentes.append)
    m._last_save = 0.0
    m.save()                       # sauvegarde de progression, non forcee
    assert attentes == [], "aucune attente sur la boucle du serveur"
    assert verrou.vus == 1, "un seul essai"


def test_etat_complet_rapide_et_identique_avec_un_gros_historique(api):
    """/api/state est appele chaque seconde : l'encodage generique de FastAPI coutait ~100 ms
    pour 2 000 entrees, en plus du calcul."""
    import fastapi.encoders
    c, rapido = api
    for i in range(2000):
        rapido.manager.add(f"http://127.0.0.1:9/histo/{i}.zip", f"{i}.zip", later=True, persist=False)
    from fastapi.responses import JSONResponse
    attendu = fastapi.encoders.jsonable_encoder(asyncio.run(rapido._state_payload()))
    r = c.get("/api/state")
    assert r.status_code == 200
    assert r.json() == attendu
    assert c.get("/api/downloads").json() == attendu["downloads"]
    # Reponse deja encodee : FastAPI ne repasse pas 2 000 objets dans jsonable_encoder.
    assert isinstance(asyncio.run(rapido.state()), JSONResponse)


def test_retelecharger_un_transfert_non_confirme_repond_409(api):
    c, rapido = api
    dl = rapido.manager.add("http://127.0.0.1:9/transfert.zip", "transfert.zip", later=True)
    dl.status = "handoff"
    r = c.post(f"/api/downloads/{dl.id}/redownload", json={}, headers=JSON)
    assert r.status_code == 409, r.text
    assert rapido.manager.downloads[dl.id].status == "handoff"


def test_aucune_route_par_identifiant_ne_repond_500_pour_un_identifiant_inconnu(api, monkeypatch):
    c, rapido = api
    monkeypatch.setattr(rapido.os, "startfile", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(rapido.subprocess, "Popen", lambda *a, **k: None)
    vus = 0
    for route in rapido.app.routes:
        chemin = getattr(route, "path", "")
        if "{dl_id}" not in chemin:
            continue
        for methode in sorted(getattr(route, "methods", []) or []):
            if methode in ("HEAD", "OPTIONS"):
                continue
            url = chemin.replace("{dl_id}", "inconnu000")
            r = c.request(methode, url, json={}, headers=JSON)
            vus += 1
            assert r.status_code < 500, (methode, url, r.status_code, r.text[:200])
            # cancel-capture est volontairement idempotent (fenetre fermee apres suppression).
            permis = (200, 404) if url.endswith("/cancel-capture") else (404, 409, 422)
            assert r.status_code in permis, (methode, url, r.status_code)
    assert vus >= 12, vus


@pytest.mark.parametrize("statut", ["pending", "queued", "paused", "error", "completed", "handoff"])
def test_aucune_route_par_identifiant_ne_repond_500_quel_que_soit_l_etat(api, monkeypatch, tmp_path, statut):
    c, rapido = api
    monkeypatch.setattr(rapido.os, "startfile", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(rapido.subprocess, "Popen", lambda *a, **k: None)
    monkeypatch.setattr(rapido.manager, "_eligible", lambda dl: False)     # ne rien lancer
    for route in rapido.app.routes:
        chemin = getattr(route, "path", "")
        if "{dl_id}" not in chemin:
            continue
        for methode in sorted(set(getattr(route, "methods", []) or []) - {"HEAD", "OPTIONS"}):
            fichier = tmp_path / f"{statut}-{len(rapido.manager.downloads)}.zip"
            fichier.write_bytes(b"x")
            dl = rapido.manager.add("http://127.0.0.1:9/etat.zip", fichier.name, later=True)
            dl.status, dl.path = statut, str(fichier)
            if statut == "pending":
                dl.probe = "ready"
            url = chemin.replace("{dl_id}", dl.id)
            r = c.request(methode, url, json={}, headers=JSON)
            assert r.status_code < 500, (statut, methode, url, r.status_code, r.text[:200])


def test_aucune_route_generale_ne_repond_500_pour_un_corps_vide(api, monkeypatch):
    c, rapido = api
    monkeypatch.setattr(rapido.os, "startfile", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(rapido.subprocess, "Popen", lambda *a, **k: None)
    monkeypatch.setattr(rapido.manager, "_eligible", lambda dl: False)
    exclues = {"/api/updates/check"}          # contacte GitHub : hors des tests locaux
    vus = 0
    for route in rapido.app.routes:
        chemin = getattr(route, "path", "")
        if not chemin.startswith("/api/") or "{dl_id}" in chemin or chemin in exclues:
            continue
        for methode in sorted(set(getattr(route, "methods", []) or []) - {"HEAD", "OPTIONS"}):
            for corps in ({}, {"url": "pas une adresse"}, {"ids": ["inconnu"], "all": False}):
                url = chemin.replace("{action}", "pause")
                r = c.request(methode, url, json=corps, headers=JSON)
                vus += 1
                assert r.status_code < 500, (methode, url, corps, r.status_code, r.text[:200])
    assert vus >= 40, vus


def test_reprise_sans_fichier_partiel_ne_reprend_pas_le_fichier_d_un_autre_telechargement(server, tmp_path):
    """A en pause perd son .part ; B, du meme nom, prend alors ce nom libre. A ne doit pas
    recreer (et vider) le .part de B en reprenant."""
    _, base = server

    async def main():
        m = engine.Manager(tmp_path, port=0)
        m.settings.update(download_dir=str(tmp_path / "dl"), show_complete_dialog=False,
                          monitor_clipboard=False, max_concurrent=3)
        await m.start()
        try:
            a = m.add(f"{base}/slow/fichier.bin", "commun.bin", connections=4)
            await asyncio.sleep(0.5)
            await m.pause(a.id)
            Path(m.downloads[a.id].path + ".part").unlink()        # outil de nettoyage
            b = m.add(f"{base}/slow/fichier.bin", "commun.bin", connections=4)
            t0 = time.time()
            while m.downloads[b.id].downloaded == 0:
                assert time.time() - t0 < 30
                await asyncio.sleep(0.02)
            # Le nom prevu de A (en pause) est reserve : B en prend un autre des le depart.
            assert m.downloads[b.id].path != m.downloads[a.id].path
            m.resume(a.id)
            while any(m.downloads[i].status not in ("completed", "error") for i in (a.id, b.id)):
                assert time.time() - t0 < 90
                await asyncio.sleep(0.05)
            return m.downloads[a.id], m.downloads[b.id]
        finally:
            await m.stop()

    a, b = asyncio.run(main())
    assert (a.status, b.status) == ("completed", "completed"), (a.error[-160:], b.error[-160:], a.path, b.path)
    assert a.path != b.path
    assert sha_file(a.path) == SHA and sha_file(b.path) == SHA


@pytest.mark.parametrize("action", ["remove", "redownload"])
def test_supprimer_ou_retelecharger_ne_touche_pas_le_fichier_partiel_d_un_autre(tmp_path, action):
    async def main():
        m = engine.Manager(tmp_path, port=0)
        dossier = tmp_path / "dl"
        dossier.mkdir()
        chemin = dossier / "commun.bin"
        a = m.add("http://127.0.0.1:9/commun.bin", "commun.bin", later=True)
        b = m.add("http://127.0.0.1:9/commun.bin", "commun.bin", later=True)
        a.path = b.path = str(chemin)                  # A a perdu son .part, B a pris le nom
        a.status, b.status = "paused", "downloading"
        partiel_b = Path(str(chemin) + ".part")
        partiel_b.write_bytes(b"octets de B")
        if action == "remove":
            await m.remove(a.id)
        else:
            m.redownload(a.id)
        return partiel_b

    partiel_b = asyncio.run(main())
    assert partiel_b.read_bytes() == b"octets de B"


def test_supprimer_avec_fichier_un_inacheve_au_chemin_partage_n_efface_pas_le_fichier(tmp_path):
    """Regression de dfb0314 : pour un telechargement inacheve dont le chemin est partage avec
    un autre telechargement inacheve, la branche « fichier final » effacait dl.path, qui n'est
    qu'un nom prevu (ici un fichier de l'utilisateur)."""
    async def main():
        m = engine.Manager(tmp_path, port=0)
        dossier = tmp_path / "dl"
        dossier.mkdir()
        chemin = dossier / "rapport.pdf"
        chemin.write_bytes(b"document personnel")
        a = m.add("http://127.0.0.1:9/rapport.pdf", "rapport.pdf", later=True)
        b = m.add("http://127.0.0.1:9/rapport.pdf", "rapport.pdf", later=True)
        a.path = b.path = str(chemin)
        a.status, b.status = "paused", "downloading"
        await m.remove(a.id, delete_file=True)
        return m, a.id, chemin

    m, a_id, chemin = asyncio.run(main())
    assert a_id not in m.downloads
    assert chemin.read_bytes() == b"document personnel"
