"""Plaintext cookie files left by an interrupted yt-dlp analysis are removed at start.

_ydl_opts writes ck-XXXXXXXX.txt (tempfile.mkstemp) in the data folder and
deletes it afterwards; an exit or crash during the analysis left such files
behind.
"""
import tempfile
import unittest
from pathlib import Path

import engine


class StaleCookieFileTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name)

    def test_leftover_cookie_files_are_deleted_when_the_manager_starts(self):
        leftovers = [self.data / "ck-k7m2q9x4.txt", self.data / "ck-p3t8w1z6.txt", self.data / "ck-0788j6an.txt"]
        for path in leftovers:
            path.write_text("# Netscape HTTP Cookie File\nexample.org\tFALSE\t/\tFALSE\t0\tsid\tsecret\n")
        engine.Manager(self.data, port=0)
        self.assertEqual([p for p in leftovers if p.exists()], [])

    def test_only_rapido_cookie_file_names_are_touched(self):
        kept = ["ck-notes.txt", "ck-k7m2q9x4.txt.bak", "ck-k7m2q9x4.TXT.old", "my-ck-k7m2q9x4.txt",
                "downloads.json", "settings.json", "rapido.log", "ck-K7M2Q9X4.txt"]
        for name in kept:
            (self.data / name).write_text({"downloads.json": "[]", "settings.json": "{}"}.get(name, "x"))
        (self.data / "ck-sub0000x.txt").mkdir()
        engine.Manager(self.data, port=0)
        for name in kept + ["ck-sub0000x.txt"]:
            self.assertTrue((self.data / name).exists(), name)

    def test_cookie_files_written_during_a_session_are_still_removed_after_use(self):
        manager = engine.Manager(self.data, port=0)
        dl = engine.Download(id="v1", url="https://video.example/watch", kind="video",
                             page_url="https://video.example/watch",
                             headers={"Cookie": "sid=secret"}, yt_cookies=True)
        with manager._ydl_opts(dl) as opts:
            path = Path(opts["cookiefile"])
            self.assertTrue(path.exists())
            self.assertRegex(path.name, r"^ck-[a-z0-9_]{8}\.txt$")
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
