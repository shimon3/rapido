import json
import tempfile
import unittest
from pathlib import Path
from scripts.firefox_native_smoke import prepare_probe

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
    def test_probe_preserves_shipped_manifest_and_background(self):
        target=prepare_probe(self.source,self.root/"probe","http://127.0.0.1:8765")
        self.assertEqual(json.loads((target/"manifest.json").read_text()),self.manifest)
        self.assertEqual((target/"background.js").read_text(),"original-background")
        self.assertFalse((self.source/"smoke.js").exists())
        self.assertIn('src="smoke.js"',(target/"smoke.html").read_text())
        script=(target/"smoke.js").read_text()
        self.assertIn("http://127.0.0.1:8765",script)
        self.assertNotIn("__BASE__",script)
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

if __name__=="__main__":
    unittest.main()
