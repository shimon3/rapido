"""
Rapido - application Windows.

Demarre le serveur Rapido en arriere-plan et l'affiche dans de vraies fenetres
Windows (moteur Edge WebView2), avec une icone dans la zone de notification.

    Rapido.exe              ouvre la fenetre principale
    Rapido.exe --tray       demarre reduit dans la zone de notification (demarrage avec Windows)
    Rapido.exe --selftest   verification automatique (utilisee par la compilation)

Fermer la fenetre principale ne quitte pas Rapido : les telechargements continuent.
Pour quitter : clic droit sur l'icone pres de l'horloge > Quitter Rapido.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

PORT = 9614
BASE_URL = f"http://127.0.0.1:{PORT}"
_rapido = None

WEBVIEW2_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"


def parse_args():
    p = argparse.ArgumentParser(prog="Rapido")
    p.add_argument("--tray", action="store_true", help="demarrer reduit dans la zone de notification")
    p.add_argument("--selftest", action="store_true", help="verification automatique puis fermeture")
    p.add_argument("--selftest-out", default="", help="fichier de resultat du selftest (JSON)")
    args, _ = p.parse_known_args()
    return args


def message_box(text: str, error: bool = False):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "Rapido", 0x10 if error else 0x40)
    except Exception:
        print(text)


def api(path: str, body: dict | None = None, timeout: float = 3):
    if _rapido is not None:
        from trusted_api import call
        return call(_rapido, path, body, timeout=timeout)
    if path != "/api/ping" or body is not None:
        raise RuntimeError("Internal API unavailable before startup")
    data = None
    req = urllib.request.Request(BASE_URL + path, data=data, method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "null")


def already_running():
    """True = Rapido tourne deja, False = port libre, "other" = port pris par autre chose."""
    try:
        return True if api("/api/ping", timeout=1.5).get("app") == "Rapido" else "other"
    except urllib.error.URLError:
        return False
    except Exception:
        return "other"


def setup_logging(data_dir: Path):
    """Un .exe sans console n'a pas de sys.stdout : on ecrit dans un fichier."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    data_dir.mkdir(parents=True, exist_ok=True)
    log = open(data_dir / "rapido.log", "a", encoding="utf-8", buffering=1)
    log.write(f"\n--- demarrage {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    sys.stdout = sys.stdout or log
    sys.stderr = sys.stderr or log


def main() -> int:
    global _rapido
    args = parse_args()
    if args.selftest and not os.environ.get("RAPIDO_DATA"):
        os.environ["RAPIDO_DATA"] = tempfile.mkdtemp(prefix="rapido-selftest-")
    data_dir = Path(os.environ.get("RAPIDO_DATA", Path.home() / ".rapido"))
    setup_logging(data_dir)

    # ----- une seule instance : on reveille celle qui tourne deja -----
    state = already_running()
    if state is True:
        if args.selftest:
            print("selftest: Rapido tourne deja sur le port", PORT)
            return 2
        if not args.tray:
            try:
                from native_pipe import request
                result = request({"type":"show"}, server_images=[sys.executable], timeout=2)
                if result.get("ok") is not True:
                    raise RuntimeError("Native instance refused")
            except Exception:
                message_box("L'instance locale n'a pas pu etre verifiee. Ferme l'ancienne instance puis relance Rapido.", True)
                return 1
        return 0
    if state == "other":
        message_box(f"Le port {PORT} est deja utilise par un autre programme.\nRapido ne peut pas demarrer.", True)
        return 1

    # WebView authorization must reach our owned listener directly, never a proxy.
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--no-proxy-server"
    os.environ.pop("WEBVIEW2_PIPE_FOR_SCRIPT_DEBUGGER", None)
    import uvicorn
    import webview
    import app as rapido
    from webview_auth import attach
    _rapido = rapido

    if args.selftest:
        rapido.manager.settings["download_dir"] = str(data_dir / "Downloads")
        rapido.manager.settings["show_complete_dialog"] = False

    # ----- serveur en arriere-plan -----
    server = uvicorn.Server(uvicorn.Config(rapido.app, host="127.0.0.1", port=PORT,
                                           log_level="warning", access_log=False))
    # Claim the port exclusively before any window can add authorization headers.
    import socket
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name == "nt":
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(("127.0.0.1", PORT))
        listener.listen(128)
    except OSError:
        listener.close()
        message_box("Le port local n'a pas pu etre reserve exclusivement.", True)
        return 1
    server_thread = threading.Thread(target=lambda: server.run(sockets=[listener]),
                                     name="rapido-server", daemon=True)
    server_thread.start()
    for _ in range(200):
        if server.started:
            break
        if not server_thread.is_alive():
            break
        time.sleep(0.1)
    if not server.started:
        listener.close()
        _rapido = None
        message_box("Le serveur de Rapido n'a pas pu demarrer.\n"
                    f"Details dans : {data_dir / 'rapido.log'}", True)
        return 1

    # ----- fenetres -----
    quitting = threading.Event()
    notified = threading.Event()
    tray = None

    main_win = webview.create_window(
        "Rapido", BASE_URL + "/", width=1180, height=720, min_size=(760, 460),
        hidden=args.tray, background_color="#EEF0EC",
    )

    def on_main_closing():
        if quitting.is_set():
            return True
        # comme les gestionnaires de telechargement classiques : on reste dans la zone de notification
        main_win.hide()
        if tray is not None and not notified.is_set():
            notified.set()
            try:
                tray.notify("Rapido continue en arrière-plan. Clic droit sur l'icône pour quitter.", "Rapido")
            except Exception:
                pass
        return False

    attach(main_win, BASE_URL + "/", rapido._LOCAL_AUTH)
    main_win.events.closing += on_main_closing

    def show_main():
        try:
            main_win.show()
            main_win.restore()
            main_win.on_top = True       # passe devant les autres fenetres...
            main_win.on_top = False      # ...sans rester epingle
        except Exception as e:
            print("show_main:", e)

    def quit_all():
        quitting.set()
        for w in list(webview.windows):
            try:
                w.destroy()
            except Exception:
                pass

    popups: dict[str, object] = {}       # jeton secret -> fenetre

    def open_popup(path: str, width: int = 540, height: int = 480):
        """Petites fenetres : capture, choix de qualite video, progression, termine."""
        import secrets
        dl_id = path.split("id=")[-1].split("&")[0]
        token = secrets.token_hex(16)
        win = webview.create_window(
            "Rapido", f"{BASE_URL}{path}&w={token}", width=width, height=height, min_size=(420, 300),
            on_top=True, background_color="#F3F4F1",
        )
        attach(win, f"{BASE_URL}{path}&w={token}", rapido._LOCAL_AUTH)
        popups[token] = win

        def unpin():
            time.sleep(2.5)
            try:
                win.on_top = False
            except Exception:
                pass

        def on_closed():
            popups.pop(token, None)
            # fenetre de capture fermee avec la croix = annuler (sans effet si deja confirme)
            threading.Thread(target=lambda: _quiet(lambda: api(f"/api/downloads/{dl_id}/cancel-capture", {})),
                             daemon=True).start()

        win.events.shown += lambda: threading.Thread(target=unpin, daemon=True).start()
        win.events.closed += on_closed
        return win

    def window_action(token: str, action: str, width: int, height: int) -> bool:
        win = popups.get(token)
        if win is None:
            return False
        if action == "close":
            win.destroy()
        else:
            win.resize(width, height)
        return True

    rapido.UI.update(desktop=True, show_main=show_main, window_action=window_action)
    rapido.manager.open_window = open_popup
    rapido.manager.on_exit = quit_all          # action "Quitter Rapido" a la fin de la file d'attente

    native_server = None
    if os.name == "nt" and getattr(sys, "frozen", False):
        from native_pipe import PipeServer
        native_server = PipeServer(rapido.native_dispatch, clients={
            str(Path(sys.executable).with_name("RapidoNativeHost.exe")):"native",
            sys.executable:"desktop",
        }).start()

    if not args.selftest:
        tray = rapido.run_tray(show_main, quit_all)

    result = {"ok": False}

    def on_start():
        if webview.renderer != "edgechromium":
            message_box("Rapido a besoin de Microsoft Edge WebView2 (inclus dans Windows 10 et 11 a jour).\n\n"
                        "La page de telechargement va s'ouvrir : installe-le puis relance Rapido.", True)
            import webbrowser
            webbrowser.open(WEBVIEW2_URL)
            quit_all()
            return
        if args.selftest:
            run_selftest(main_win, open_popup, result)
            quit_all()

    try:
        webview.start(on_start, private_mode=True)
    finally:
        quitting.set()
        if tray is not None:
            try:
                tray.stop()
            except Exception:
                pass
        if native_server is not None:
            native_server.stop()
        server.should_exit = True
        server_thread.join(timeout=10)
        listener.close()
        _rapido = None

    if args.selftest:
        out = args.selftest_out or str(Path(tempfile.gettempdir()) / "rapido-selftest.json")
        Path(out).write_text(json.dumps(result, indent=2, ensure_ascii=False), "utf-8")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    return 0


def _quiet(fn):
    try:
        fn()
    except Exception:
        pass


def run_selftest(main_win, open_popup, result: dict):
    """Verifie la fenetre, le moteur de telechargement, yt-dlp et les petites fenetres."""
    import webview
    try:
        result["renderer"] = webview.renderer
        result["main_loaded"] = main_win.events.loaded.wait(30)
        time.sleep(1.5)
        result["main_title"] = main_win.evaluate_js("document.title")
        result["main_rows_html"] = main_win.evaluate_js("document.querySelector('#thead') !== null")

        dl = api("/api/downloads", {"url": BASE_URL + "/favicon.ico", "filename": "selftest.png"})[0]
        status = ""
        for _ in range(100):
            d = api(f"/api/downloads/{dl['id']}")
            status = d["status"]
            if status in ("completed", "error"):
                break
            time.sleep(0.2)
        result["download_status"] = status
        result["download_file_ok"] = bool(d.get("path")) and Path(d["path"]).is_file() \
            and Path(d["path"]).stat().st_size == d.get("size")

        import yt_dlp
        result["yt_dlp"] = yt_dlp.version.__version__

        popup = open_popup(f"/w?view=progress&id={dl['id']}", 520, 360)
        result["popup_loaded"] = popup.events.loaded.wait(30)
        time.sleep(1.5)
        result["popup_title"] = popup.evaluate_js("document.title")
        result["popup_token"] = popup.evaluate_js("!!new URLSearchParams(location.search).get('w')")
        # la page fait elle-meme l'appel, comme le bouton "Fermer" (verifie aussi la CSP)
        popup.evaluate_js("resize(600, 400)")
        time.sleep(1.5)
        result["popup_resized"] = abs(popup.width - 600) <= 20
        result["csp"] = "script-src 'sha256-" in urllib.request.urlopen(BASE_URL + "/").headers.get(
            "Content-Security-Policy", "")
        # securite : un site web ne doit pas pouvoir piloter Rapido
        try:
            urllib.request.urlopen(urllib.request.Request(
                BASE_URL + "/api/show", data=b"{}", method="POST",
                headers={"Content-Type": "application/json", "Origin": "https://evil.example"}), timeout=3)
            result["guard_ok"] = False
        except urllib.error.HTTPError as e:
            result["guard_ok"] = e.code == 403
        # yt-dlp tourne dans un processus separe (sinon Rapido gele pendant l'analyse YouTube)
        import asyncio
        import app as rapido
        fut = asyncio.run_coroutine_threadsafe(rapido.manager._yt_process(
            "extract", BASE_URL + "/favicon.ico", {"quiet": True, "no_warnings": True}, timeout=90),
            rapido.manager.loop)
        kind, payload = fut.result(120)
        result["ytdlp_detail"] = f"{kind}: {str(payload)[:160]}"
        result["ytdlp_process"] = kind == "result" or (
            kind == "error" and "s'est arrete" not in str(payload) and "trop longue" not in str(payload))
        import engine
        result["dpapi_ok"] = engine.unprotect(engine.protect("session=abc")) == "session=abc"
        zi = Path(d["path"] + ":Zone.Identifier")
        raw = zi.read_bytes() if zi.exists() else b""
        result["motw_ok"] = b"ZoneId=3\r\n" in raw and b"\r\r" not in raw
        result["settings_desktop"] = api("/api/settings").get("desktop")

        # Exercise native WebView2 header authentication without an exposed JS token.
        main_win.evaluate_js("api('/api/settings').then(s=>window._nativeAuthProbe=s.desktop).catch(()=>window._nativeAuthProbe=false); true")
        for _ in range(30):
            if main_win.evaluate_js("window._nativeAuthProbe === true"):
                break
            time.sleep(.1)
        result["webview_auth"] = main_win.evaluate_js("window._nativeAuthProbe === true")
        # An arbitrary local client cannot read private state or mutate the API.
        result["unauthenticated_api"] = True
        for path, body in (("/api/settings",None), ("/api/state",None), ("/api/capture",{"url":BASE_URL+"/favicon.ico"})):
            req = urllib.request.Request(BASE_URL+path, data=None if body is None else json.dumps(body).encode(),
                method="GET" if body is None else "POST", headers={"Content-Type":"application/json"})
            try:
                urllib.request.urlopen(req, timeout=2)
                result["unauthenticated_api"] = False
            except urllib.error.HTTPError as error:
                result["unauthenticated_api"] &= error.code == 403
        # The actual packaged native host must authenticate the actual desktop pipe.
        import subprocess, struct
        def native_message(value):
            payload = json.dumps(value).encode()
            process = subprocess.run([str(Path(sys.executable).with_name("RapidoNativeHost.exe"))],
                input=struct.pack("<I",len(payload))+payload, capture_output=True, timeout=8,
                creationflags=subprocess.CREATE_NO_WINDOW)
            if process.returncode != 0 or len(process.stdout) < 4:
                raise RuntimeError("Packaged native host failed")
            size = struct.unpack("<I",process.stdout[:4])[0]
            if size > 65536 or len(process.stdout) != size+4:
                raise RuntimeError("Invalid packaged native reply")
            return json.loads(process.stdout[4:])
        capabilities = native_message({"type":"capabilities"})
        result["native_pipe"] = capabilities.get("protocol") == 1 and "capture_public" in capabilities.get("features",[])
        reply = native_message({"type":"capture_public","url":BASE_URL+"/favicon.ico",
                                "referrer":None,"filename":"native-selftest.png"})
        result["native_capture"] = reply == {"type":"capture_result","ok":True}


        result["ok"] = bool(
            result["renderer"] == "edgechromium" and result["main_loaded"]
            and result["main_title"] == "Rapido" and status == "completed" and result["download_file_ok"]
            and result["popup_loaded"] and result["popup_token"] and result["popup_resized"]
            and result["settings_desktop"] and result["csp"] and result["guard_ok"]
            and result["dpapi_ok"] and result["motw_ok"] and result["ytdlp_process"]
            and result["webview_auth"] and result["unauthenticated_api"]
            and result["native_pipe"] and result["native_capture"]
        )
    except Exception as e:
        import traceback
        result["error"] = "".join(traceback.format_exception(e))[-2000:]


if __name__ == "__main__":
    # indispensable dans Rapido.exe : les processus yt-dlp relancent l'exe lui-meme
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
