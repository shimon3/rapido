"""yt-dlp worker processes must not outlive a killed Rapido.

A crash, "End task" or a hang closed by Windows left multiprocessing children
running (daemon=True only applies to a normal exit). After a restart Rapido
queued the same video again: two processes wrote the same files.
"""
import os
import subprocess
import sys
import textwrap
import time
import unittest
from pathlib import Path

import windows_job

ROOT = Path(__file__).resolve().parents[1]

PARENT = textwrap.dedent("""
    import multiprocessing as mp, sys, time
    sys.path.insert(0, sys.argv[1])
    import windows_job

    def child(marker):
        open(marker, "w").close()     # fully started: the parent may now be killed
        time.sleep(60)

    if __name__ == "__main__":
        p = mp.get_context("spawn").Process(target=child, args=(sys.argv[3],), daemon=True)
        p.start()
        if sys.argv[2] == "job":
            windows_job.kill_with_this_process(p.pid)
        print(p.pid, flush=True)
        time.sleep(60)
""")


def running(pid):
    import ctypes
    k = ctypes.windll.kernel32
    handle = k.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        return bool(k.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally:
        k.CloseHandle(handle)


def terminate(pid):
    import ctypes
    k = ctypes.windll.kernel32
    handle = k.OpenProcess(0x0001, False, pid)
    if handle:
        k.TerminateProcess(handle, 1)
        k.CloseHandle(handle)


@unittest.skipUnless(os.name == "nt", "Windows job objects")
class KillWithRapidoTests(unittest.TestCase):
    def run_parent(self, mode, tmp):
        script = Path(tmp) / "parent.py"
        script.write_text(PARENT, encoding="utf-8")
        marker = Path(tmp) / "started"
        parent = subprocess.Popen([sys.executable, str(script), str(ROOT), mode, str(marker)],
                                  stdout=subprocess.PIPE, text=True)
        child = int(parent.stdout.readline())
        self.addCleanup(terminate, child)
        deadline = time.monotonic() + 20
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(marker.exists(), "worker did not start")
        self.assertTrue(running(child))
        parent.kill()                 # TerminateProcess, like "End task"
        parent.wait(10)
        parent.stdout.close()
        deadline = time.monotonic() + 5
        while running(child) and time.monotonic() < deadline:
            time.sleep(0.1)
        return running(child)

    def test_worker_in_the_job_dies_with_its_parent(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(self.run_parent("job", tmp))

    def test_without_the_job_the_worker_survives(self):
        # Documents the defect the job fixes (and that the harness can see it).
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(self.run_parent("none", tmp))

    def test_unknown_or_finished_process_is_ignored(self):
        self.assertFalse(windows_job.kill_with_this_process(0))
        done = subprocess.run([sys.executable, "-c", "pass"])
        self.assertEqual(done.returncode, 0)


class PortableTests(unittest.TestCase):
    def test_non_windows_is_a_no_op(self):
        if os.name == "nt":
            self.skipTest("Windows")
        self.assertFalse(windows_job.kill_with_this_process(os.getpid()))


if __name__ == "__main__":
    unittest.main()


class EngineUsesTheJobTests(unittest.TestCase):
    def test_every_ytdlp_worker_is_tied_to_rapido(self):
        import asyncio
        import tempfile
        from unittest.mock import patch
        import engine

        with tempfile.TemporaryDirectory(dir=ROOT) as folder, \
                patch.object(windows_job, "kill_with_this_process", return_value=True) as tie:
            manager = engine.Manager(Path(folder), port=0)
            kind, _ = asyncio.run(manager._yt_process("extract", "http://127.0.0.1:9/nothing.mp4",
                                                      {"quiet": True, "no_warnings": True}, timeout=60))
        self.assertEqual(kind, "error")
        self.assertEqual(tie.call_count, 1)
        self.assertGreater(tie.call_args.args[0], 0)
