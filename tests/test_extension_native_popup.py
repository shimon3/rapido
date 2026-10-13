"""Chrome popup smoke contracts: diagnostics and capture toggle survive migration."""
import json
from pathlib import Path


def test_diagnostic_popup_is_registered():
    manifest = json.loads(Path("extension/manifest.json").read_text("utf-8"))
    assert manifest["action"]["default_popup"] == "popup.html"
    html = Path("extension/popup.html").read_text("utf-8")
    assert 'id="test"' in html and 'id="toggle"' in html
    assert '<script src="popup.js"></script>' in html


def test_popup_only_tests_native_ping_and_preserves_capture_toggle():
    popup = Path("extension/popup.js").read_text("utf-8")
    background = Path("extension/background.js").read_text("utf-8")
    assert 'type:"rapido_native_ping"' in popup
    assert 'type:"rapido_capture_state_changed"' in popup
    assert 'chrome.storage.local.set({enabled:!enabled})' in popup
    assert 'sender.url?.startsWith(chrome.runtime.getURL("popup.html"))' in background
    assert 'probeNativeBridge().then(connected' in background
