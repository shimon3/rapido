"""A native request that timed out must not take effect later.

When Rapido's event loop is busy for longer than the native reply timeout, the
host answers "error" and the extension keeps the download in the browser. The
queued preparation then ran anyway and left a "Transfert interrompu" entry for
a download the browser was still doing (and it counts toward MAX_PREPARED).
"""
import asyncio
import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("RAPIDO_DATA", tempfile.mkdtemp(prefix="rapido-busy-loop-"))
import app  # noqa: E402

PREPARE = {"type": "capture_prepare", "url": "https://example.org/a.zip", "referrer": None, "filename": "a.zip"}
PUBLIC = {"type": "capture_public", "url": "https://example.org/b.zip", "referrer": None, "filename": "b.zip"}


@unittest.skipUnless(os.name == "nt", "Durable handoff requires Windows DPAPI")
class BusyLoopTests(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(folder.cleanup)
        self.manager = app.Manager(Path(folder.name), port=0)
        self.manager.loop = self.loop
        self.manager.open_window = lambda *a, **k: None
        patcher = patch.object(app, "manager", self.manager)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.stop_loop)

    def stop_loop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)
        self.loop.close()

    def block_loop(self, seconds):
        started = threading.Event()

        def busy():
            started.set()
            time.sleep(seconds)
        self.loop.call_soon_threadsafe(busy)
        self.assertTrue(started.wait(2))

    def drain(self):
        done = threading.Event()
        self.loop.call_soon_threadsafe(done.set)
        self.assertTrue(done.wait(5))
        done.clear()
        self.loop.call_soon_threadsafe(done.set)     # let follow-up callbacks run too
        self.assertTrue(done.wait(5))

    def test_timed_out_preparation_never_creates_a_handoff(self):
        with patch.object(app, "NATIVE_REPLY_TIMEOUT", 0.4), patch.object(app, "NATIVE_START_DEADLINE", 0.2):
            self.block_loop(0.8)
            with self.assertRaises(FutureTimeout):
                app.native_dispatch("native", dict(PREPARE))
            self.drain()
        self.assertEqual([d.status for d in self.manager.downloads.values()], [])

    def test_timed_out_public_capture_never_appears_later(self):
        with patch.object(app, "NATIVE_REPLY_TIMEOUT", 0.4), patch.object(app, "NATIVE_START_DEADLINE", 0.2):
            self.block_loop(0.8)
            with self.assertRaises(FutureTimeout):
                app.native_dispatch("native", dict(PUBLIC))
            self.drain()
        self.assertEqual(list(self.manager.downloads), [])

    def test_responsive_loop_still_prepares(self):
        reply = app.native_dispatch("native", dict(PREPARE))
        self.assertEqual(reply["type"], "capture_prepared")
        self.assertEqual([d.status for d in self.manager.downloads.values()], ["handoff"])


if __name__ == "__main__":
    unittest.main()
