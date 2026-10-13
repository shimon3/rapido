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

    @app.get("/{mode}/fichier.bin")
    async def serve(mode: str, request: Request):
        app.state.hits[mode] = app.state.hits.get(mode, 0) + 1
        app.state.accept_encoding.append(request.headers.get("accept-encoding", ""))
        rng = parse_range(request)
        n = len(DATA)
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
    with TestClient(rapido.app, base_url="http://127.0.0.1:9614") as c:
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
