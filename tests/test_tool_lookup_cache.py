"""ffmpeg()/deno() run on the event loop (the UI polls /api/state every second).

Without ffmpeg, each call scanned PATH and the WinGet folders: about 11 ms per
call on a test PC, every second.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import engine


class ToolLookupCacheTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.manager = engine.Manager(self.root, port=0)
        self.now = [1000.0]
        patcher = patch.object(engine.time, "monotonic", lambda: self.now[0])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_repeated_lookups_are_cached_briefly(self):
        with patch.object(engine.shutil, "which", return_value=None) as which:
            for _ in range(5):
                self.manager.ffmpeg()
                self.manager.deno()
            self.assertEqual(which.call_count, 2, "one PATH scan per tool")
            self.now[0] += engine.TOOL_LOOKUP_TTL + 0.1
            self.manager.ffmpeg()
            self.assertEqual(which.call_count, 3, "found again after the delay")

    def test_changing_the_ffmpeg_setting_takes_effect_at_once(self):
        exe = self.root / "ffmpeg.exe"
        exe.write_bytes(b"")
        with patch.object(engine.shutil, "which", return_value=None):
            self.assertIsNone(self.manager.ffmpeg())
            self.manager.settings["ffmpeg_path"] = str(exe)
            self.assertEqual(self.manager.ffmpeg(), str(exe))
            self.manager.settings["ffmpeg_path"] = ""
            self.assertIsNone(self.manager.ffmpeg())

    def test_a_removed_tool_is_noticed_after_the_delay(self):
        exe = self.root / "ffmpeg.exe"
        exe.write_bytes(b"")
        self.manager.settings["ffmpeg_path"] = str(exe)
        with patch.object(engine.shutil, "which", return_value=None):
            self.assertEqual(self.manager.ffmpeg(), str(exe))
            exe.unlink()
            self.now[0] += engine.TOOL_LOOKUP_TTL + 0.1
            self.assertIsNone(self.manager.ffmpeg())


if __name__ == "__main__":
    unittest.main()
