"""A failed settings write must leave the previous settings.json intact."""
import errno
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import engine


class SettingsPersistenceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name)
        self.manager = engine.Manager(self.data, port=0)
        self.manager.settings["download_dir"] = "D:/Mes telechargements"
        self.manager.save_settings()

    def test_disk_full_during_write_keeps_the_previous_file(self):
        real_write = Path.write_text

        def half_then_full(path, text, *args, **kwargs):
            real_write(path, text[: len(text) // 2], *args, **kwargs)
            raise OSError(errno.ENOSPC, "No space left on device")

        self.manager.settings["max_concurrent"] = 5
        with patch.object(Path, "write_text", half_then_full), self.assertRaises(OSError):
            self.manager.save_settings()
        saved = json.loads((self.data / "settings.json").read_text("utf-8"))
        self.assertEqual(saved["download_dir"], "D:/Mes telechargements")
        reloaded = engine.Manager(self.data, port=0)
        self.assertEqual(reloaded.settings["download_dir"], "D:/Mes telechargements")

    def test_successful_write_replaces_the_file(self):
        self.manager.settings["max_concurrent"] = 7
        self.manager.save_settings()
        self.assertEqual(engine.Manager(self.data, port=0).settings["max_concurrent"], 7)
        self.assertEqual(sorted(p.name for p in self.data.iterdir() if p.suffix == ".tmp"), [])


if __name__ == "__main__":
    unittest.main()
