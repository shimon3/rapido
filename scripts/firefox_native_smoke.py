"""Real Firefox/packaged native bridge smoke, intended for Windows CI only."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

FIREFOX_ID="rapido-capture@rapido.local"
DATA=b"R"* (8*1024*1024)

class ProbeState:
    """Per-run control channel for the isolated extension; never shipped."""
    def __init__(self):
        self.path = "/_rapido_probe/" + secrets.token_hex(24)
        self.lock = threading.Lock()
        self.phase = "start"
        self.results = {}

    def command(self):
        with self.lock:
            return self.phase

    def report(self, value):
        if (not isinstance(value, dict) or set(value) != {"phase", "result"} or
                not isinstance(value["result"], dict) or
                type(value["result"].get("ok")) is not bool):
            raise ValueError("Invalid probe report")
        with self.lock:
            if value["phase"] != self.phase or self.phase in self.results:
                raise ValueError("Unexpected or duplicate probe phase")
            self.results[self.phase] = dict(value["result"])

    def result(self, phase):
        with self.lock:
            return self.results.get(phase)

    def fallback(self):
        with self.lock:
            if self.phase != "start" or self.results.get("start", {}).get("ok") is not True:
                raise ValueError("Start phase has not succeeded")
            self.phase = "fallback"

class DownloadFixture(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass
    def do_GET(self):
        if self.path == self.server.probe.path + "/command":
            self.reply(200, {"phase": self.server.probe.command()})
            return
        if self.path not in ("/probe.zip", "/automatic.zip", "/fallback.zip"):
            self.reply(404, {"error": "unknown_fixture"})
            return
        probe=self.headers.get("Range")=="bytes=0-0"
        self.send_response(206 if probe else 200)
        self.send_header("Content-Type","application/zip")
        self.send_header("Content-Length","1" if probe else str(len(DATA)))
        self.send_header("Accept-Ranges","bytes")
        self.send_header("Content-Disposition","attachment; filename="+self.path.rsplit("/",1)[-1])
        if probe:
            self.send_header("Content-Range",f"bytes 0-0/{len(DATA)}")
        self.end_headers()
        try:
            if probe:
                self.wfile.write(DATA[:1])
            else:
                for offset in range(0,len(DATA),32768):
                    self.wfile.write(DATA[offset:offset+32768])
                    self.wfile.flush()
                    time.sleep(.02)  # Real browser remains active during native startup.
        except (OSError,ConnectionError):
            pass

    def reply(self, status, value):
        payload = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        if self.path != self.server.probe.path + "/result":
            self.reply(404, {"error": "unknown_fixture"})
            return
        try:
            length = self.headers.get("Content-Length", "")
            if not length.isascii() or not length.isdecimal() or not 0 < int(length) <= 4096:
                raise ValueError("Invalid report size")
            value = json.loads(self.rfile.read(int(length)).decode("utf-8"))
            self.server.probe.report(value)
        except (ValueError, UnicodeError):
            self.reply(400, {"error": "invalid_report"})
            return
        self.reply(200, {"accepted": True})

def prepare_probe(source,destination,base,*,control_path=None):
    source,destination=Path(source).resolve(),Path(destination).resolve()
    if destination==source or source in destination.parents or destination in source.parents:
        raise ValueError("Probe must be separate from shipped extension")
    if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]{1,5}", base) or not 0 < int(base.rsplit(":", 1)[1]) <= 65535:
        raise ValueError("Local fixture required")
    control_path = control_path or ProbeState().path
    if not re.fullmatch(r"/_rapido_probe/[0-9a-f]{48}", control_path):
        raise ValueError("Isolated probe control path required")
    manifest=json.loads((source/"manifest.json").read_text(encoding="utf-8-sig"))
    if manifest.get("browser_specific_settings",{}).get("gecko",{}).get("id")!=FIREFOX_ID:
        raise ValueError("Unexpected Firefox identity")
    shutil.copytree(source,destination)
    # Test adapters are outside the distributed extension, using its original background.
    (destination/"smoke.html").write_text('<!doctype html><meta charset="utf-8"><p>Isolated Firefox integration fixture</p><script src="smoke.js"></script>',encoding="utf-8")
    script=Path(__file__).with_name("firefox_native_probe.js").read_text(encoding="utf-8-sig")
    (destination/"smoke.js").write_text(script.replace("__BASE__",base).replace("__CONTROL__",base+control_path),encoding="utf-8")
    # Firefox Marionette forbids direct WebDriver navigation to moz-extension:// pages.
    # Open the test page from the extension itself, in a separate CI-only copy.
    background=manifest.get("background",{})
    if background.get("scripts")!=["background.js"]:
        raise ValueError("Unexpected Firefox background configuration")
    manifest["background"]={"scripts":["background.js","smoke_bootstrap.js"]}
    (destination/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    (destination/"smoke_bootstrap.js").write_text(
        'chrome.runtime.onInstalled.addListener(() => { chrome.tabs.create({url: chrome.runtime.getURL("smoke.html")}); });\n',
        encoding="utf-8")
    return destination

def wait_until(check,timeout=40):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        value=check()
        if value:
            return value
        time.sleep(.1)
    raise TimeoutError("Firefox integration timeout")

def result(state, phase):
    value=wait_until(lambda: state.result(phase))
    if value.get("ok") is not True:
        raise RuntimeError(value.get("error","Browser smoke failed"))
    return value

def run(bundle,data_dir,probe_dir):
    if os.name!="nt":
        raise OSError("Real native browser smoke requires Windows")
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    import engine
    bundle,data_dir=Path(bundle).resolve(),Path(data_dir).resolve()
    desktop=bundle/"Rapido.exe"; host=bundle/"RapidoNativeHost.exe"
    if not desktop.is_file() or not host.is_file():
        raise FileNotFoundError("Compiled bundle missing")
    data_dir.mkdir(parents=True,exist_ok=False)
    server=ThreadingHTTPServer(("127.0.0.1",0),DownloadFixture)
    server.probe = ProbeState()
    threading.Thread(target=server.serve_forever,daemon=True).start()
    probe=prepare_probe(bundle/"extension-firefox",probe_dir,f"http://127.0.0.1:{server.server_port}",control_path=server.probe.path)
    env=dict(os.environ,RAPIDO_DATA=str(data_dir))
    registered=False
    driver=None
    process=None
    try:
        subprocess.run([str(host),"--register-native-hosts"],check=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
        registered=True
        process=subprocess.Popen([str(desktop),"--tray"],env=env,creationflags=subprocess.CREATE_NO_WINDOW)
        # Public ping is readiness only; native capabilities proves the verified bridge.
        import urllib.request
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def ready():
            if process.poll() is not None:
                raise RuntimeError("Desktop exited before browser test")
            try:
                with opener.open("http://127.0.0.1:9614/api/ping",timeout=1) as response:
                    return json.load(response).get("app")=="Rapido"
            except OSError:
                return False
        wait_until(ready)
        (data_dir/"browser-downloads").mkdir()
        options=Options()
        options.add_argument("-headless")
        options.set_preference("browser.download.folderList",2)
        options.set_preference("browser.download.dir",str(data_dir/"browser-downloads"))
        options.set_preference("browser.helperApps.neverAsk.saveToDisk","application/zip")
        options.set_preference("browser.download.alwaysOpenPanel",False)
        driver=webdriver.Firefox(options=options)
        driver.set_page_load_timeout(30)
        identity=driver.install_addon(str(probe),temporary=True)
        if identity!=FIREFOX_ID:
            raise RuntimeError("Unexpected installed add-on identity")
        # Firefox forbids WebDriver DOM commands in privileged extension pages.
        # The CI-only adapter runs itself; do not enable remote system access.
        summary=result(server.probe, "start")
        # The actual background transfer must produce exactly one durable desktop record.
        def native_download():
            try:
                records=json.loads((data_dir/"downloads.json").read_text())
                values=[engine.Download.from_disk(item) for item in records]
                return values if any(item.filename=="automatic.zip" for item in values) else None
            except (OSError,ValueError):
                return None
        values=wait_until(native_download)
        if len(values)!=1 or values[0].handoff_ticket=="" or values[0].status not in ("pending","queued","downloading","completed"):
            raise RuntimeError("Automatic browser transfer was not committed once")
        subprocess.run([str(host),"--unregister-native-hosts"],check=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
        registered=False
        server.probe.fallback()
        summary.update(result(server.probe, "fallback"))
        values=[engine.Download.from_disk(item) for item in json.loads((data_dir/"downloads.json").read_text())]
        if len(values)!=1:
            raise RuntimeError("Missing-host fallback created another native download")
        summary["browser_version"]=driver.capabilities.get("browserVersion")
        print(json.dumps(summary))
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        if process is not None and process.poll() is None:
            process.terminate()  # Exact test-owned process, never a process-name kill.
            process.wait(timeout=15)
        if registered:
            subprocess.run([str(host),"--unregister-native-hosts"],timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
        server.shutdown()
        server.server_close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle",type=Path,required=True)
    parser.add_argument("--data",type=Path,required=True)
    parser.add_argument("--probe",type=Path,required=True)
    args=parser.parse_args()
    run(args.bundle,args.data,args.probe)

if __name__=="__main__":
    main()
