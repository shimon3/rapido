"""An unreadable downloads.json/settings.json is kept aside, never overwritten."""
import json
import tempfile
import unittest
from pathlib import Path

import engine


class CorruptStateTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name)

    def test_corrupt_history_is_moved_aside_before_the_next_save(self):
        broken = b'[{"id": "abc", "private_state_version": 1, "private_state_enc": "AQAAANCMnd8BFdER'
        (self.data / "downloads.json").write_bytes(broken)
        manager = engine.Manager(self.data, port=0)
        self.assertEqual(manager.downloads, {})
        manager.add("http://127.0.0.1:9/a.zip", "a.zip", later=True)      # writes a new history
        kept = sorted(self.data.glob("downloads.json.unreadable-*"))
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].read_bytes(), broken)

    def test_corrupt_settings_are_moved_aside(self):
        (self.data / "settings.json").write_text('{"download_dir": "D:/x", "max_conc', "utf-8")
        manager = engine.Manager(self.data, port=0)
        manager.save_settings()
        kept = sorted(self.data.glob("settings.json.unreadable-*"))
        self.assertEqual(len(kept), 1)
        self.assertIn("D:/x", kept[0].read_text("utf-8"))

    def test_valid_files_are_not_moved(self):
        manager = engine.Manager(self.data, port=0)
        manager.add("http://127.0.0.1:9/a.zip", "a.zip", later=True)
        manager.save_settings()
        engine.Manager(self.data, port=0)
        self.assertEqual(list(self.data.glob("*.unreadable-*")), [])

    def test_repeated_corruption_keeps_each_copy(self):
        for content in (b"{", b"[1,"):
            (self.data / "downloads.json").write_bytes(content)
            engine.Manager(self.data, port=0)
        self.assertEqual(len(list(self.data.glob("downloads.json.unreadable-*"))), 2)


if __name__ == "__main__":
    unittest.main()


class BadRecordTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name)

    def test_one_bad_record_does_not_drop_the_following_ones(self):
        writer = engine.Manager(self.data, port=0)
        first = writer.add("http://127.0.0.1:9/first.zip", "first.zip", later=True)
        last = writer.add("http://127.0.0.1:9/last.zip", "last.zip", later=True)
        records = json.loads((self.data / "downloads.json").read_text("utf-8"))
        # e.g. a segment field added by a newer Rapido, then a downgrade
        bad = {"id": "newer00001", "url": "http://127.0.0.1:9/x", "segments": [{"start": 0, "end": 9, "done": 1, "crc": 7}]}
        broken = [records[0], "not a record", bad, records[1]]
        raw = json.dumps(broken)
        (self.data / "downloads.json").write_text(raw, "utf-8")
        reader = engine.Manager(self.data, port=0)
        self.assertIn(first.id, reader.downloads)
        self.assertIn(last.id, reader.downloads)
        kept = sorted(self.data.glob("downloads.json.unreadable-*"))
        self.assertEqual(len(kept), 1, "the original file is kept before it is rewritten")
        self.assertEqual(kept[0].read_text("utf-8"), raw)


class LockedAtStartupTests(unittest.TestCase):
    """The antivirus was observed holding downloads.json (WinError 32)."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name)
        writer = engine.Manager(self.data, port=0)
        self.kept = writer.add("http://127.0.0.1:9/precieux.zip", "precieux.zip", later=True)
        writer.save_settings()
        self.history = (self.data / "downloads.json").read_bytes()

    def lock_reads(self, failures):
        from unittest.mock import patch
        real = Path.read_text
        seen = {"n": 0}

        def read_text(path, *a, **k):
            if path.name in ("downloads.json", "settings.json") and seen["n"] < failures:
                seen["n"] += 1
                raise PermissionError(13, "locked", str(path))
            return real(path, *a, **k)
        return patch.object(Path, "read_text", read_text)

    def test_a_brief_lock_at_startup_still_loads_the_history(self):
        with self.lock_reads(2):
            manager = engine.Manager(self.data, port=0)
        self.assertIn(self.kept.id, manager.downloads)

    def test_a_lasting_lock_never_lets_the_first_save_erase_the_history(self):
        with self.lock_reads(10_000):
            manager = engine.Manager(self.data, port=0)
        self.assertNotIn(self.kept.id, manager.downloads)
        manager.add("http://127.0.0.1:9/nouveau.zip", "nouveau.zip", later=True)   # lock released
        manager.save_settings()
        kept = sorted(self.data.glob("downloads.json.unreadable-*"))
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].read_bytes(), self.history)
        self.assertEqual(len(sorted(self.data.glob("settings.json.unreadable-*"))), 1)
