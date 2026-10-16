"""One beta version everywhere, ordered before its final release."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import rapido_version
from scripts.build_browser_extension import build

ROOT = Path(__file__).resolve().parents[1]


class VersioningTests(unittest.TestCase):
    def test_beta_orders_between_previous_and_final_release(self):
        self.assertLess(rapido_version.numeric("1.2.2"), rapido_version.numeric("1.3.0-beta.1"))
        self.assertLess(rapido_version.numeric("1.3.0-beta.1"), rapido_version.numeric("1.3.0-beta.2"))
        self.assertLess(rapido_version.numeric("1.3.0-beta.2"), rapido_version.numeric("1.3.0"))
        self.assertEqual(rapido_version.dotted("1.3.0-beta.1"), "1.3.0.1")
        self.assertEqual(rapido_version.dotted("v1.3.0"), "1.3.0.100")
        self.assertTrue(rapido_version.is_prerelease("1.3.0-beta.1"))
        self.assertFalse(rapido_version.is_prerelease("1.3.0"))
        for bad in ("1.3", "1.3.0-beta.0", "1.3.0-beta.100", "1.3.0-rc.1", "1.3.0-beta.1 ", "x"):
            with self.subTest(bad=bad):
                self.assertIsNone(rapido_version.numeric(bad))
                self.assertFalse(rapido_version.is_prerelease(bad))
        with self.assertRaises(ValueError):
            rapido_version.dotted("1.3")

    def test_every_shipped_version_string_matches_the_single_source(self):
        version = rapido_version.VERSION
        self.assertTrue(rapido_version.is_prerelease(version))
        import engine
        self.assertEqual(engine.VERSION, version)
        manifest = json.loads((ROOT / "extension/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], rapido_version.dotted(version))
        self.assertEqual(manifest["version_name"], version)
        installer = (ROOT / "packaging/rapido.iss").read_text(encoding="utf-8-sig")
        self.assertIn(f'#define AppVersion "{version}"', installer)
        self.assertIn(f'#define AppFileVersion "{rapido_version.dotted(version)}"', installer)
        self.assertIn("VersionInfoVersion={#AppFileVersion}", installer)

    def test_windows_version_resource_uses_numeric_and_display_forms(self):
        result = subprocess.run([sys.executable, str(ROOT / "packaging/make_version_file.py"), "1.3.0-beta.1"],
                                capture_output=True, text=True, check=True, timeout=30)
        self.assertIn("filevers=(1, 3, 0, 1)", result.stdout)
        self.assertIn("StringStruct('FileVersion', '1.3.0.1')", result.stdout)
        self.assertIn("StringStruct('ProductVersion', '1.3.0-beta.1')", result.stdout)
        bad = subprocess.run([sys.executable, str(ROOT / "packaging/make_version_file.py"), "1.3.0-rc.1"],
                             capture_output=True, text=True, timeout=30)
        self.assertNotEqual(bad.returncode, 0)

    def test_firefox_build_drops_chromium_only_version_label(self):
        with tempfile.TemporaryDirectory() as folder:
            build("firefox", Path(folder) / "firefox")
            build("edge", Path(folder) / "edge")
            firefox = json.loads((Path(folder) / "firefox/manifest.json").read_text(encoding="utf-8"))
            edge = json.loads((Path(folder) / "edge/manifest.json").read_text(encoding="utf-8"))
        self.assertNotIn("version_name", firefox)
        self.assertEqual(firefox["version"], rapido_version.dotted(rapido_version.VERSION))
        self.assertEqual(edge["version_name"], rapido_version.VERSION)

    def test_update_check_offers_final_release_to_beta_users(self):
        import asyncio
        from unittest.mock import patch
        import app
        with patch.object(app, "_latest_rapido_release", return_value=("1.3.0", "https://example.invalid")), \
             patch.object(app, "VERSION", "1.3.0-beta.1"):
            reply = asyncio.run(app.check_updates())
        self.assertTrue(reply["update_available"])
        with patch.object(app, "_latest_rapido_release", return_value=("1.2.2", "https://example.invalid")), \
             patch.object(app, "VERSION", "1.3.0-beta.1"):
            reply = asyncio.run(app.check_updates())
        self.assertFalse(reply["update_available"])

    def test_workflow_marks_betas_as_prereleases_never_latest(self):
        source = (ROOT / ".github/workflows/windows.yml").read_text(encoding="utf-8")
        release = source.split("\n  release:\n", 1)[1]
        self.assertIn("prerelease: ${{ needs.build.outputs.prerelease == 'true' }}", release)
        self.assertIn("make_latest: ${{ needs.build.outputs.prerelease == 'true' && 'false' || 'true' }}", release)
        self.assertNotIn("make_latest: true", release)
        self.assertIn("needs.build.outputs.prerelease == 'true' && '**Version bêta.** Non protégée contre un compte Windows déjà compromis (#26", release)
        notes = (ROOT / "docs/beta-release-notes.md").read_text(encoding="utf-8")
        self.assertIn(rapido_version.VERSION, notes)
        self.assertIn("#26", notes)
        self.assertTrue(re.search(r'/DAppFileVersion=\$\{\{ steps\.ver\.outputs\.file_version \}\}', source))


if __name__ == "__main__":
    unittest.main()
