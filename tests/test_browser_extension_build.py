"""Experimental browser build manifest tests; no runtime compatibility claim."""
import json
from pathlib import Path

import pytest

from scripts.build_browser_extension import build


@pytest.mark.parametrize("browser", ["edge", "firefox"])
def test_browser_build_preserves_source_and_uses_browser_manifest(tmp_path):
    source = Path(__file__).resolve().parents[1] / "extension" / "manifest.json"
    original = source.read_bytes()
    destination = tmp_path / browser
    build(browser, destination)
    assert source.read_bytes() == original
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert "key" not in manifest
    assert (destination / "background.js").is_file()
    assert (destination / "content.js").is_file()
    if browser == "firefox":
        assert manifest["background"] == {"scripts": ["background.js"]}
        assert manifest["browser_specific_settings"]["gecko"]["id"] == "rapido-capture@rapido.local"
    else:
        assert manifest["background"] == {"service_worker": "background.js"}
        assert "browser_specific_settings" not in manifest
    with pytest.raises(FileExistsError):
        build(browser, destination)


def test_builder_never_overwrites_extension_source(tmp_path):
    root = Path(__file__).resolve().parents[1] / "extension"
    with pytest.raises(ValueError):
        build("edge", root)
    with pytest.raises(ValueError):
        build("firefox", root / "subfolder")
    with pytest.raises(ValueError):
        build("edge", root.parent)
    with pytest.raises(ValueError):
        build("chrome", tmp_path / "chrome")
