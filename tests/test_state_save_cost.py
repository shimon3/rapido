"""Saving progress must not re-encrypt the whole history every two seconds.

Each DPAPI call costs about a millisecond: with 500 history entries, every
save blocked the event loop for about 0.6 s while a download was running.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import engine


def history(manager, count):
    for i in range(count):
        dl = engine.Download(id=f"{i:010d}", url=f"https://files.example/{i}.zip?sig=secret{i}",
                             filename=f"{i}.zip", status="completed", size=10,
                             segments=[engine.Segment(0, 9, 10)])
        manager.downloads[dl.id] = dl


@unittest.skipUnless(os.name == "nt", "DPAPI requires Windows")
class SaveCostTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.manager = engine.Manager(self.folder, port=0)
        history(self.manager, 50)

    def count_protect(self):
        real = engine.protect
        calls = []

        def counting(text):
            calls.append(text)
            return real(text)
        return calls, patch.object(engine, "protect", counting)

    def test_unchanged_records_are_not_encrypted_again(self):
        self.manager.save(force=True)
        calls, patcher = self.count_protect()
        with patcher:
            self.manager.save(force=True)
            self.assertEqual(len(calls), 0)
            active = self.manager.downloads["0000000007"]
            active.status, active.segments[0].done = "downloading", 5
            self.manager.save(force=True)
            self.assertEqual(len(calls), 1, "only the changed download is sealed again")

    def test_saved_history_stays_sealed_and_reloads_the_latest_state(self):
        self.manager.save(force=True)
        changed = self.manager.downloads["0000000003"]
        changed.description = "renamed"
        self.manager.save(force=True)
        raw = (self.folder / "downloads.json").read_text("utf-8")
        self.assertNotIn("secret", raw)
        self.assertNotIn("https://", raw)
        records = json.loads(raw)
        self.assertEqual(len(records), 50)
        self.assertTrue(all(set(r) == {"id", "private_state_version", "private_state_enc"} for r in records))
        reloaded = engine.Manager(self.folder, port=0)
        self.assertEqual(reloaded.downloads["0000000003"].description, "renamed")
        self.assertEqual(reloaded.downloads["0000000049"].url, "https://files.example/49.zip?sig=secret49")

    def test_removed_downloads_leave_no_cached_envelope(self):
        self.manager.save(force=True)
        self.manager.downloads.pop("0000000001")
        self.manager.save(force=True)
        self.assertNotIn("0000000001", self.manager._sealed)
        ids = [r["id"] for r in json.loads((self.folder / "downloads.json").read_text("utf-8"))]
        self.assertNotIn("0000000001", ids)

    def test_dpapi_failure_is_never_cached(self):
        with patch.object(engine, "protect", side_effect=OSError("DPAPI")):
            self.manager.save(force=True)
        self.manager.save(force=True)
        reloaded = engine.Manager(self.folder, port=0)
        self.assertEqual(reloaded.downloads["0000000000"].url, "https://files.example/0.zip?sig=secret0")


if __name__ == "__main__":
    unittest.main()
