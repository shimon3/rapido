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
import queue
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

# The self-test thread starts with webview.start(), before WebView2 exists. The
# first window's wait therefore covers the WebView2 cold start, which on CI
# runners intermittently exceeded 30 s (loaded fired between 30 and 50 s).
SELFTEST_FIRST_LOAD_TIMEOUT = 90
SELFTEST_POPUP_LOAD_TIMEOUT = 30


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


def forbidden_response(request, *, timeout: float, attempts: int = 3,
                       retry_delay: float = .1) -> bool:
    """Require an actual 403, retrying transient loopback transport failures.

    Windows can occasionally abort a newly opened loopback connection before
    urllib receives the HTTP response.  A reset is not proof that the API guard
    worked, so only a real 403 passes; transport failures merely get retried.
    """
    if attempts < 1:
        raise ValueError("attempts must be positive")
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout):
                return False
        except urllib.error.HTTPError as error:
            return error.code == 403
        except (urllib.error.URLError, OSError):
            if attempt + 1 == attempts:
                return False
            time.sleep(retry_delay)
    return False


def already_running():
    """True = Rapido tourne deja, False = port libre, "other" = port pris par autre chose."""
    try:
        return True if api("/api/ping", timeout=1.5).get("app") == "Rapido" else "other"
    except urllib.error.URLError:
        return False
    except Exception:
        return "other"


START_WAIT = 15        # secondes laissees a une instance qui demarre (WebView2 a froid)


def wake_existing(deadline: float) -> bool:
    """Demande a l'instance qui tourne de montrer sa fenetre, en reessayant tant
    qu'elle demarre encore (canal natif pas pret, fenetre pas encore creee)."""
    from native_pipe import request
    while True:
        try:
            if request({"type":"show"}, server_images=[sys.executable], timeout=2).get("ok") is True:
                return True
        except Exception:
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.5)


def wait_for_running(deadline: float) -> bool:
    """Deux lancements simultanes : attendre que l'autre instance reponde."""
    while time.monotonic() < deadline:
        if already_running() is True:
            return True
        time.sleep(0.5)
    return False


def defer_to_running(args) -> int:
    """Une instance tourne deja : la ramener au premier plan, un seul message au pire."""
    if args.selftest:
        print("selftest: Rapido tourne deja sur le port", PORT)
        return 2
    if args.tray:
        return 0
    if wake_existing(time.monotonic() + START_WAIT):
        return 0
    message_box("Rapido est deja ouvert mais ne repond pas.\n"
                "Ferme-le dans le Gestionnaire des taches, puis relance Rapido.", True)
    return 1


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
        return defer_to_running(args)
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
        # Lance deux fois tres vite : l'autre instance a pris le port entre-temps.
        if wait_for_running(time.monotonic() + START_WAIT):
            return defer_to_running(args)
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
    popup_tasks = SerialTaskQueue("rapido-popup-queue")
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

    def start_watchdog():
        form = getattr(main_win, "native", None)
        if form is None or not hasattr(form, "BeginInvoke"):
            return
        from System import Action
        dog = UiWatchdog(lambda ack: form.BeginInvoke(Action(ack)), dump_threads)
        in_background(dog.run, name="rapido-ui-watchdog")

    main_win.events.shown += start_watchdog
    # Registered before webview.start() so no window event can be missed.
    main_timeline = track_window_load(main_win) if args.selftest else None

    def show_main():
        try:
            main_win.show()
            main_win.restore()
            bring_to_front(main_win)     # sur le fil graphique, sans rester epinglee
        except Exception as e:
            print("show_main:", e)

    def quit_all():
        quitting.set()
        popup_tasks.stop()
        for w in list(webview.windows):
            try:
                w.destroy()
            except Exception:
                pass

    popups: dict[str, object] = {}       # jeton secret -> fenetre

    def open_popup(path: str, width: int = 540, height: int = 480):
        """Petites fenetres : capture, choix de qualite video, progression, termine."""
        if quitting.is_set():
            return None
        import secrets
        dl_id = path.split("id=")[-1].split("&")[0]
        token = secrets.token_hex(16)
        win = webview.create_window(
            "Rapido", f"{BASE_URL}{path}&w={token}", width=width, height=height, min_size=(420, 300),
            on_top=True, background_color="#F3F4F1",
        )
        attach(win, f"{BASE_URL}{path}&w={token}", rapido._LOCAL_AUTH)
        if quitting.is_set():
            # La fermeture a commence pendant la creation WinForms synchrone.
            # Ne jamais laisser cette fenetre tardive garder la boucle GUI en vie.
            _quiet(win.destroy)
            return None
        popups[token] = win

        def on_closed():
            popups.pop(token, None)
            # fenetre de capture fermee avec la croix = annuler (sans effet si deja confirme)
            threading.Thread(target=lambda: _quiet(lambda: api(f"/api/downloads/{dl_id}/cancel-capture", {})),
                             daemon=True).start()

        win.events.shown += lambda: threading.Thread(
            target=unpin_after_delay,
            args=(win, quitting, lambda: popups.get(token) is win),
            name="rapido-popup-unpin",
            daemon=True,
        ).start()
        win.events.closed += on_closed
        return win

    def window_action(token: str, action: str, width: int, height: int) -> bool:
        win = popups.get(token)
        if win is None:
            return False
        # Appele depuis le serveur local : ne pas attendre le fil graphique.
        if action == "close":
            return popup_tasks.submit(win.destroy)
        return popup_tasks.submit(lambda: win.resize(width, height))

    rapido.UI.update(desktop=True, show_main=show_main, window_action=window_action)
    # Le serveur demande une fenetre puis repond aussitot a l'extension.
    rapido.manager.open_window = lambda path, width=540, height=480: popup_tasks.submit(
        lambda: open_popup(path, width, height))
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
            run_selftest(main_win, open_popup, result, main_timeline)
            quit_all()

    try:
        webview.start(on_start, private_mode=True)
    finally:
        quitting.set()
        popup_tasks.stop()
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


class SerialTaskQueue:
    """Execute les operations graphiques lentes dans l'ordre, sur un seul fil.

    Une rafale de captures ne doit pas creer un fil bloque par fenetre pendant
    que WinForms traite les creations une par une. ``stop`` refuse les nouvelles
    operations et ignore celles qui attendaient encore : une fermeture de
    Rapido ne peut donc pas etre suivie par l'apparition tardive d'une fenetre.
    """

    _STOP = object()

    def __init__(self, name="rapido-ui-queue"):
        self._queue = queue.Queue()
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._thread.start()

    def submit(self, fn) -> bool:
        with self._lock:
            if self._stopped.is_set():
                return False
            self._queue.put(fn)
            return True

    def stop(self, timeout=0.0) -> bool:
        with self._lock:
            if not self._stopped.is_set():
                self._stopped.set()
                self._queue.put(self._STOP)
        if timeout:
            self._thread.join(timeout)
        return not self._thread.is_alive()

    def _run(self):
        import traceback
        while True:
            task = self._queue.get()
            try:
                if task is self._STOP:
                    return
                if not self._stopped.is_set():
                    task()
            except Exception:
                # setup_logging redirige ceci vers rapido.log dans l'executable.
                traceback.print_exc()
            finally:
                self._queue.task_done()


def in_background(fn, name="rapido-ui"):
    """Lance fn hors du fil appelant. Le serveur local (boucle asyncio) ne doit
    jamais attendre le fil graphique : creer une fenetre prenait 1 a 8 s sur la
    VM Windows 10 et la reponse a l'extension arrivait trop tard."""
    threading.Thread(target=lambda: _quiet(fn), name=name, daemon=True).start()


def on_ui_thread(win, action) -> bool:
    """Execute action(form) sur le fil graphique WinForms, sans l'attendre.
    pywebview 6.2.1 applique on_top (TopMost) depuis le fil appelant : modifier
    une fenetre depuis un autre fil est une cause connue de blocages Windows."""
    form = getattr(win, "native", None)
    if form is None or not hasattr(form, "BeginInvoke"):
        return False
    try:
        from System import Action
        form.BeginInvoke(Action(lambda: _quiet(lambda: action(form))))
        return True
    except Exception:
        # A delayed operation can race a window closing.  WinForms rejects
        # BeginInvoke once its native handle has been destroyed; shutdown must
        # not leave an unhandled daemon-thread exception behind.
        return False


def unpin_after_delay(win, stopping: threading.Event, still_open, delay=2.5) -> bool:
    """Release popup topmost state unless shutdown/close won the delay race."""
    if stopping.wait(delay) or not still_open():
        return False
    return set_topmost(win, False)


def set_topmost(win, value: bool) -> bool:
    def apply(form):
        form.TopMost = value
    return on_ui_thread(win, apply)


def bring_to_front(win) -> bool:
    """Passe devant les autres fenetres sans rester epinglee."""
    def apply(form):
        form.TopMost = True
        form.TopMost = False
        form.Activate()
    return on_ui_thread(win, apply)


class UiWatchdog:
    """Si le fil graphique ne traite plus ses messages pendant `stall` secondes,
    ecrit une fois la pile de chaque fil Python dans le journal (diagnostic des
    blocages « Application Hang » vus le 15/10 21:29 et le 16/10 09:38)."""

    def __init__(self, post, dump, *, interval=5.0, stall=10.0, clock=time.monotonic, sleep=time.sleep):
        self.post, self.dump = post, dump
        self.interval, self.stall = interval, stall
        self.clock, self.sleep = clock, sleep
        self.last_ack = clock()
        self.reported = False
        self.stopped = False

    def _ack(self):
        self.last_ack = self.clock()
        self.reported = False

    def tick(self):
        try:
            self.post(self._ack)
        except Exception:
            pass
        if self.clock() - self.last_ack >= self.stall and not self.reported:
            self.reported = True
            self.dump(self.clock() - self.last_ack)

    def run(self):
        while not self.stopped:
            self.tick()
            self.sleep(self.interval)


def dump_threads(stalled_for: float):
    import faulthandler
    print(f"--- fil graphique bloque depuis {stalled_for:.0f} s : piles des fils Python ---", flush=True)
    try:
        faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
    except Exception as e:
        print("dump_threads:", e)


def check_confirmation_ui(window, fixture_id, *, popup=False):
    """Exercise actual DOM dialogs/handlers in WebView2; intercept destructive POSTs."""
    script = r'''
    window._confirmationCheck = null;
    (async () => {
      const check = (value, message) => { if(!value) throw Error(message); };
      const dialog = document.querySelector('#confirmDialog');
      const no = () => document.querySelector('#confirmNo').click();
      const yes = () => document.querySelector('#confirmYes').click();
      const escape = () => dialog.dispatchEvent(new Event('cancel', {cancelable:true}));
      const calls = [];
      let closes = 0, failPause = false;
      const savedApi = api;
      const savedClose = typeof closeWin === 'function' ? closeWin : null;
      try {
        let pending = askConfirm('<img src=x onerror=alert(1)>');
        check(dialog.open && document.activeElement.id === 'confirmNo', 'default refusal focus');
        check(!document.querySelector('#confirmMessage img'), 'message must remain text');
        check(await askConfirm('re-entry') === false, 're-entry must refuse');
        no(); check(await pending === false, 'cancel must refuse');
        pending = askConfirm('Escape'); escape(); check(await pending === false, 'cancel event must refuse');
        pending = askConfirm('external close'); dialog.close('confirmed'); check(await pending === false, 'external close must refuse');
        pending = askConfirm('explicit approval'); yes(); check(await pending === true, 'explicit approval');
        api = async (path, method='GET', body) => {
          if(method === 'POST') {
            calls.push({path, body});
            if(failPause && path.endsWith('/pause')) throw Error('simulated pause failure');
            return {};
          }
          return savedApi(path, method, body);
        };
        if(__POPUP__) {
          clearInterval(timer);
          dl = {...dl, status:'paused'};
          renderProgress();
          closeWin = () => { closes++; };
          for(const refuse of [no, escape, () => dialog.close()]) {
            pending = document.querySelector('#cancel').onclick();
            refuse(); await pending;
            check(calls.length === 0 && closes === 0, 'refusal must not pause or close');
          }
          pending = document.querySelector('#cancel').onclick();
          await document.querySelector('#cancel').onclick();
          yes(); await pending;
          check(calls.length === 1 && closes === 1, 'approval must pause and close once');
          failPause = true;
          pending = document.querySelector('#cancel').onclick(); yes(); await pending;
          check(closes === 1 && !document.querySelector('#actionError').hidden, 'pause failure must stay visible');
        } else {
          for(const action of ['redownload','delete','deletefile']) {
            const before = calls.length;
            const item = {id:__FIXTURE__, filename:'dialog fixture', status:'completed'};
            pending = act(action, [item]); no(); await pending;
            check(calls.length === before, 'main refusal must not mutate');
            pending = act(action, [item]);
            item.id = 'changed-after-dialog';
            await act(action, [{id:'second-click'}]);
            yes(); await pending;
            check(calls.length === before + 1, 'approval must submit exactly once');
            const request = calls[calls.length-1];
            check(action === 'redownload' ? request.path === '/api/downloads/' + __FIXTURE__ + '/redownload' : request.body.ids[0] === __FIXTURE__, 'confirmed identity must stay frozen');
          }
        }
        window._confirmationCheck = {ok:true, interceptedPosts:calls.length};
      } catch(error) {
        window._confirmationCheck = {ok:false, error:String(error)};
      } finally {
        api = savedApi;
        if(savedClose) closeWin = savedClose;
      }
    })(); true
    '''
    script = script.replace('__POPUP__', 'true' if popup else 'false').replace('__FIXTURE__', json.dumps(fixture_id))
    window.evaluate_js(script)
    for _ in range(100):
        outcome = window.evaluate_js('window._confirmationCheck')
        if outcome is not None:
            return outcome
        time.sleep(.1)
    return {"ok": False, "error": "Dialog UI self-test timed out"}


def track_window_load(window, clock=time.monotonic) -> dict:
    """Record when pywebview's shown/before_load/loaded first fire (seconds).

    before_load fires on WebView2 NavigationCompleted and loaded after the
    pywebview bridge is injected, so a slow run shows which phase was late.
    """
    start = clock()
    timeline: dict[str, float] = {}

    def mark(name):
        def handler():
            timeline.setdefault(name, round(clock() - start, 2))
        return handler

    window.events.shown += mark("shown")
    window.events.before_load += mark("before_load")
    window.events.loaded += mark("loaded")
    return timeline


def wait_main_loaded(main_win, result: dict, timeline: dict | None = None,
                     timeout: float = SELFTEST_FIRST_LOAD_TIMEOUT) -> bool:
    """Wait for the real loaded event of the trusted main page; never assume it."""
    loaded = main_win.events.loaded.wait(timeout)
    result["main_loaded"] = loaded
    if timeline is not None:
        result["main_load_timeline"] = dict(timeline)
    if loaded:
        result["main_url_ok"] = main_win.evaluate_js("location.href") == BASE_URL + "/"
    else:
        result["main_url_ok"] = False
    return loaded


def run_selftest(main_win, open_popup, result: dict, main_timeline: dict | None = None):
    """Verifie la fenetre, le moteur de telechargement, yt-dlp et les petites fenetres."""
    import webview
    try:
        result["renderer"] = webview.renderer
        wait_main_loaded(main_win, result, main_timeline)
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
        result["popup_loaded"] = popup.events.loaded.wait(SELFTEST_POPUP_LOAD_TIMEOUT)
        time.sleep(1.5)
        result["popup_title"] = popup.evaluate_js("document.title")
        result["popup_token"] = popup.evaluate_js("!!new URLSearchParams(location.search).get('w')")
        # la page fait elle-meme l'appel, comme le bouton "Fermer" (verifie aussi la CSP)
        popup.evaluate_js("resize(600, 400)")
        time.sleep(1.5)
        result["popup_resized"] = abs(popup.width - 600) <= 20
        result["main_confirmations"] = check_confirmation_ui(main_win, dl['id'])
        result["popup_confirmations"] = check_confirmation_ui(popup, dl['id'], popup=True)
        result["csp"] = "script-src 'sha256-" in urllib.request.urlopen(BASE_URL + "/").headers.get(
            "Content-Security-Policy", "")
        # securite : un site web ne doit pas pouvoir piloter Rapido
        result["guard_ok"] = forbidden_response(urllib.request.Request(
            BASE_URL + "/api/show", data=b"{}", method="POST",
            headers={"Content-Type": "application/json", "Origin": "https://evil.example"}), timeout=3)
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
            result["unauthenticated_api"] &= forbidden_response(req, timeout=2)
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
        # Actual packaged prepare/abort/commit: durable staging and no duplicate.
        baseline = len(rapido.manager.downloads)
        prepared = native_message({"type":"capture_prepare","url":BASE_URL+"/favicon.ico",
                                   "referrer":None,"filename":"handoff-selftest.png"})
        ticket = prepared.get("ticket")
        staged = [value for value in rapido.manager.downloads.values() if value.handoff_ticket == ticket]
        staged_ok = prepared.get("type") == "capture_prepared" and len(staged) == 1 and staged[0].status == "handoff"
        aborted = native_message({"type":"capture_abort","ticket":ticket})
        abort_ok = aborted == {"type":"capture_aborted","ok":True} and len(rapido.manager.downloads) == baseline
        prepared = native_message({"type":"capture_prepare","url":BASE_URL+"/favicon.ico",
                                   "referrer":None,"filename":"handoff-selftest.png"})
        ticket = prepared.get("ticket")
        first = native_message({"type":"capture_commit","ticket":ticket})
        second = native_message({"type":"capture_commit","ticket":ticket})
        result["native_handoff"] = bool(staged_ok and abort_ok and
            first == {"type":"capture_result","ok":True} and first == second and
            len(rapido.manager.downloads) == baseline + 1)



        result["ok"] = bool(
            result["renderer"] == "edgechromium" and result["main_loaded"] and result["main_url_ok"]
            and result["main_title"] == "Rapido" and status == "completed" and result["download_file_ok"]
            and result["popup_loaded"] and result["popup_token"] and result["popup_resized"]
            and result["settings_desktop"] and result["csp"] and result["guard_ok"]
            and result["dpapi_ok"] and result["motw_ok"] and result["ytdlp_process"]
            and result["webview_auth"] and result["unauthenticated_api"]
            and result["native_pipe"] and result["native_capture"] and result["native_handoff"]
            and result["main_confirmations"].get("ok") and result["popup_confirmations"].get("ok")
        )
    except Exception as e:
        import traceback
        result["error"] = "".join(traceback.format_exception(e))[-2000:]


if __name__ == "__main__":
    # indispensable dans Rapido.exe : les processus yt-dlp relancent l'exe lui-meme
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())

