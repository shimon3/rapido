"""Regression tests for Rapido language persistence and installer bootstrap."""
import json
from pathlib import Path
from unittest.mock import patch

import engine


def test_installer_language_is_used_for_new_profile(tmp_path):
    with patch.object(engine.Manager, "_installer_language", return_value="he"):
        m = engine.Manager(tmp_path, port=0)
    assert m.settings["language"] == "he"


def test_saved_preference_overrides_installer(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"language": "en"}), encoding="utf-8")
    with patch.object(engine.Manager, "_installer_language", return_value="he"):
        m = engine.Manager(tmp_path, port=0)
    assert m.settings["language"] == "en"


def test_old_settings_without_language_use_installer(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"connections": 6}), encoding="utf-8")
    with patch.object(engine.Manager, "_installer_language", return_value="he"):
        m = engine.Manager(tmp_path, port=0)
    assert m.settings["language"] == "he"
    assert m.settings["connections"] == 6
