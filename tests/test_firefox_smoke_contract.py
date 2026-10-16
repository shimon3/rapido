import json
import shutil
import tempfile
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from scripts.firefox_native_smoke import prepare_probe, ProbeState, DownloadFixture

class FirefoxProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/"extension-firefox"
        self.source.mkdir()
        self.manifest={"manifest_version":3,"background":{"scripts":["background.js"]},
            "browser_specific_settings":{"gecko":{"id":"rapido-capture@rapido.local"}}}
        (self.source/"manifest.json").write_text(json.dumps(self.manifest))
        (self.source/"background.js").write_text("original-background")
    def test_module_entrypoint_has_project_root_import_context(self):
        root=Path(__file__).resolve().parents[1]
        reply=subprocess.run([sys.executable,"-m","scripts.firefox_native_smoke","--help"],cwd=root,
                             capture_output=True,text=True,timeout=10)
        self.assertEqual(reply.returncode,0,reply.stderr)
        self.assertIn("--bundle",reply.stdout)

    def test_probe_preserves_shipped_manifest_and_background(self):
        target=prepare_probe(self.source,self.root/"probe","http://127.0.0.1:8765")
        self.assertEqual(json.loads((self.source/"manifest.json").read_text()),self.manifest)
        probe_manifest=json.loads((target/"manifest.json").read_text())
        self.assertEqual(probe_manifest["background"]["scripts"],["background.js","smoke_bootstrap.js"])
        self.assertEqual(probe_manifest["browser_specific_settings"],self.manifest["browser_specific_settings"])
        self.assertEqual(probe_manifest["manifest_version"],self.manifest["manifest_version"])
        self.assertIn("chrome.tabs.create", (target/"smoke_bootstrap.js").read_text())
        self.assertFalse((self.source/"smoke_bootstrap.js").exists())
        self.assertEqual((target/"background.js").read_text(),"original-background")
        self.assertFalse((self.source/"smoke.js").exists())
        self.assertIn('src="smoke.js"',(target/"smoke.html").read_text())
        script=(target/"smoke.js").read_text()
        self.assertIn("http://127.0.0.1:8765",script)
        self.assertNotIn("__BASE__",script)
        self.assertNotIn("__CONTROL__",script)
        self.assertIn("/_rapido_probe/",script)
    def test_reject_external_fixture_and_source_overlap(self):
        for base in ("https://evil.example","http://127.0.0.1:8765/path"):
            with self.assertRaises(ValueError):
                prepare_probe(self.source,self.root/"probe",base)
        for target in (self.source,self.source/"probe",self.root):
            with self.assertRaises(ValueError):
                prepare_probe(self.source,target,"http://127.0.0.1:8765")
    def test_refuse_other_addon_identity_and_destination_overwrite(self):
        self.manifest["browser_specific_settings"]["gecko"]["id"]="other@example"
        (self.source/"manifest.json").write_text(json.dumps(self.manifest))
        with self.assertRaises(ValueError):
            prepare_probe(self.source,self.root/"probe","http://127.0.0.1:8765")
        self.manifest["browser_specific_settings"]["gecko"]["id"]="rapido-capture@rapido.local"
        (self.source/"manifest.json").write_text(json.dumps(self.manifest))
        prepare_probe(self.source,self.root/"probe","http://127.0.0.1:8765")
        with self.assertRaises(FileExistsError):
            prepare_probe(self.source,self.root/"probe","http://127.0.0.1:8765")

    def test_report_phases_cannot_skip_failed_start_or_overwrite_a_result(self):
        state = ProbeState()
        with self.assertRaises(ValueError):
            state.fallback()
        for value in ({}, {"phase": "fallback", "result": {"ok": True}},
                      {"phase": "start", "result": {"ok": 1}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                state.report(value)
        state.report({"phase": "start", "result": {"ok": False}})
        with self.assertRaises(ValueError):
            state.report({"phase": "start", "result": {"ok": True}})
        with self.assertRaises(ValueError):
            state.fallback()
        self.assertEqual(state.result("start"), {"ok": False})

    def test_real_control_http_rejects_unknown_nonce_invalid_and_replayed_reports(self):
        import urllib.request
        from urllib.error import HTTPError
        from http.server import ThreadingHTTPServer
        server = ThreadingHTTPServer(("127.0.0.1", 0), DownloadFixture)
        server.probe = ProbeState()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = f"http://127.0.0.1:{server.server_port}"
        def request(path, value=None):
            data = None if value is None else json.dumps(value).encode()
            with opener.open(urllib.request.Request(base+path, data=data), timeout=2) as response:
                return response, json.load(response)
        def denied(path, value, status):
            with self.assertRaises(HTTPError) as failure:
                request(path, value)
            self.assertEqual(failure.exception.code, status)
            failure.exception.close()
        try:
            denied("/_rapido_probe/wrong/command", None, 404)
            denied("/_rapido_probe/wrong/result", {"phase":"start","result":{"ok":True}}, 404)
            self.assertIsNone(server.probe.result("start"))
            response, command = request(server.probe.path+"/command")
            self.assertEqual(command, {"phase": "start"})
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))
            denied(server.probe.path+"/result", {"phase":"fallback","result":{"ok":True}}, 400)
            report = {"phase":"start","result":{"ok":True}}
            self.assertTrue(request(server.probe.path+"/result", report)[1]["accepted"])
            denied(server.probe.path+"/result", report, 400)
            server.probe.fallback()
            self.assertEqual(request(server.probe.path+"/command")[1], {"phase":"fallback"})
            denied(server.probe.path+"/result", {"padding":"x"*4096}, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    @unittest.skipUnless(shutil.which("node"), "JavaScript runtime unavailable")
    def test_actual_probe_script_runs_each_phase_once_and_reports_native_failure(self):
        script = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
async function scenario(fail) {
  const reports = [], downloads = [], native = [];
  const phases = ['start','start','fallback'];
  let index = 0;
  const context = {
    setTimeout: callback => {callback();},
    chrome: {
      runtime: {sendNativeMessage: async (host, message) => {
        assert.equal(host, 'com.rapido.bridge'); native.push(message.type);
        if(message.type === 'capabilities') return {protocol:1,features:fail?[]:['capture_handoff']};
        if(message.type === 'capture_prepare') return {type:'capture_prepared',ticket:'fixture'};
        if(message.type === 'capture_abort') return {ok:true};
        throw Error('unexpected native operation');
      }},
      downloads: {
        download: async args => {downloads.push(args.url); return downloads.length;},
        search: async ({id}) => id === 1 ? [] : [{state:'complete'}],
      },
    },
    fetch: async (url, options) => {
      if(url.endsWith('/command')) return {ok:true,json:async()=>({phase:phases[index++]})};
      assert(url.endsWith('/result')); reports.push(JSON.parse(options.body)); return {ok:true};
    },
  };
  await vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
  if(fail) {
    assert.equal(reports.length,1); assert.equal(reports[0].result.ok,false);
    assert.equal(reports[0].result.stage,'capabilities');
    assert.equal(downloads.length,0);
  } else {
    assert.deepEqual(reports.map(r=>r.phase),['start','fallback']);
    assert(reports.every(r=>r.result.ok)); assert.equal(downloads.length,2);
    assert.deepEqual(native,['capabilities','capture_prepare','capture_abort']);
    assert(reports[1].result.host_absent_keeps_browser_download);
  }
}
(async()=>{await scenario(false); await scenario(true);})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        source = Path(__file__).resolve().parents[1]/"scripts/firefox_native_probe.js"
        reply = subprocess.run([shutil.which("node"), "-e", script, str(source)],
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(reply.returncode, 0, reply.stdout+reply.stderr)

if __name__=="__main__":
    unittest.main()
