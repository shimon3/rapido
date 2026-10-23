"""End-to-end contract between each browser extension build and the native host.

Chrome, Edge and Firefox must each reach com.rapido.bridge with an identity the
host manifest allows, and every message the extension sends must be one the host
understands and answers in the shape the extension checks. No browser, registry
or real Rapido process is involved.
"""
import base64
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import native_host
import native_registration
from scripts.build_browser_extension import build

ROOT = Path(__file__).resolve().parents[1]
BACKGROUND = (ROOT / "extension" / "background.js").read_text(encoding="utf-8")
TICKET = "ab" * 32

# Message the extension sends -> (sample message, backend reply, reply the extension accepts).
EXCHANGES = {
    "ping": ({"type": "ping"}, None, {"type": "pong", "protocol": 1}),
    "capabilities": (
        {"type": "capabilities"},
        {"type": "capabilities", "protocol": 1,
         "features": ["ping", "capture_public", "settings_public", "capture_handoff"]},
        {"type": "capabilities", "protocol": 1,
         "features": ["ping", "capture_public", "settings_public", "capture_handoff"]}),
    "settings_public": (
        {"type": "settings_public"},
        {"type": "settings_public", "capture_exts": ["zip"], "min_capture_kb": 512},
        {"type": "settings_public", "capture_exts": ["zip"], "min_capture_kb": 512}),
    "capture_public": (
        {"type": "capture_public", "url": "https://example.com/a.zip",
         "referrer": "https://example.com/page", "filename": "a.zip"},
        {"type": "capture_result", "ok": True},
        {"type": "capture_result", "ok": True}),
    "capture_prepare": (
        {"type": "capture_prepare", "url": "https://example.com/a.zip",
         "referrer": None, "filename": None},
        {"type": "capture_prepared", "ticket": TICKET},
        {"type": "capture_prepared", "ticket": TICKET}),
    "capture_commit": (
        {"type": "capture_commit", "ticket": TICKET},
        {"type": "capture_result", "ok": True},
        {"type": "capture_result", "ok": True}),
    "capture_abort": (
        {"type": "capture_abort", "ticket": TICKET},
        {"type": "capture_aborted", "ok": True},
        {"type": "capture_aborted", "ok": True}),
}


def sent_message_types():
    return set(re.findall(r'sendNativeMessage\(\s*NATIVE_HOST\s*,\s*\{\s*type\s*:\s*"(\w+)"', BACKGROUND))


def chromium_id(manifest):
    digest = hashlib.sha256(base64.b64decode(manifest["key"], validate=True)).digest()[:16].hex()
    return "".join(chr(ord("a") + int(c, 16)) for c in digest)


class BrowserNativeContractTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        install = self.root / "install"
        install.mkdir()
        self.exe = install / "RapidoNativeHost.exe"
        self.exe.touch()
        self.exe.with_name("Rapido.exe").touch()
        self.host = native_registration.manifests(self.exe)

    def built_manifest(self, browser):
        if browser == "chrome":
            folder = ROOT / "extension"
        else:
            folder = self.root / browser
            build(browser, folder)
        return json.loads((folder / "manifest.json").read_text(encoding="utf-8"))

    def test_extension_and_host_agree_on_the_host_name(self):
        self.assertIn(f'const NATIVE_HOST = "{native_registration.HOST}";', BACKGROUND)
        for _, _, value in self.host.values():
            self.assertEqual(value["name"], native_registration.HOST)
            self.assertEqual(value["type"], "stdio")

    def test_each_browser_build_is_allowed_by_its_host_manifest(self):
        for browser in ("chrome", "edge", "firefox"):
            with self.subTest(browser=browser):
                manifest = self.built_manifest(browser)
                self.assertIn("nativeMessaging", manifest["permissions"])
                allowed = self.host[browser][2]
                if browser == "firefox":
                    identity = manifest["browser_specific_settings"]["gecko"]["id"]
                    self.assertEqual(allowed["allowed_extensions"], [identity])
                    self.assertEqual(manifest["background"], {"scripts": ["background.js"]})
                else:
                    origin = "chrome-extension://" + chromium_id(manifest) + "/"
                    self.assertEqual(allowed["allowed_origins"], [origin])
                    self.assertEqual(manifest["background"], {"service_worker": "background.js"})

    def test_every_message_the_extension_sends_is_covered_here(self):
        self.assertEqual(sent_message_types(), set(EXCHANGES))

    def test_host_answers_each_message_in_the_shape_the_extension_checks(self):
        for kind, (message, backend, expected) in EXCHANGES.items():
            with self.subTest(kind=kind), patch.object(native_host, "_native_request",
                                                       return_value=backend) as request:
                self.assertEqual(native_host.handle_message(dict(message)), expected)
                if backend is None:
                    request.assert_not_called()

    def test_host_fails_closed_for_each_message_when_rapido_is_absent(self):
        for kind, (message, backend, _) in EXCHANGES.items():
            with self.subTest(kind=kind), patch.object(native_host, "_native_request",
                                                       side_effect=OSError("no Rapido")):
                reply = native_host.handle_message(dict(message))
                if kind == "ping":
                    self.assertEqual(reply["type"], "pong")
                elif kind == "capabilities":
                    # Only ping remains: the extension then keeps every download.
                    self.assertEqual(reply["features"], ["ping"])
                else:
                    self.assertEqual(reply["type"], "error")


if __name__ == "__main__":
    unittest.main()
