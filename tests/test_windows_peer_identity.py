"""Real Windows kernel identity checks; no identity comes from message JSON."""
import os
import subprocess
import sys
import unittest
from pathlib import Path
from windows_peer import inspect_process, verified_process, canonical_image, pipe_peer_pid


class IdentityInputTests(unittest.TestCase):
    def test_paths_must_be_absolute_and_explicit(self):
        for path in ("", "Rapido.exe", None, "C:\\a\x00b"):
            with self.assertRaises(ValueError):
                canonical_image(path)
        self.assertEqual(canonical_image("C:\\Apps\\Rapido.exe"), "c:\\apps\\rapido.exe")

    def test_pid_and_handle_validation_precedes_os_calls(self):
        for pid in (None, True, 0, -1, 2**32, "1"):
            with self.assertRaises(ValueError):
                with inspect_process(pid):
                    pass
        for handle in (None, True, 0, -1):
            with self.assertRaises(ValueError):
                pipe_peer_pid(handle, server=True)


@unittest.skipUnless(os.name == "nt", "Real Windows process APIs")
class WindowsIdentityTests(unittest.TestCase):
    def test_current_process_uses_kernel_values_and_pins_identity(self):
        with inspect_process(os.getpid()) as current:
            self.assertEqual(current.pid, os.getpid())
            self.assertTrue(current.user_sid.startswith("S-1-"))
            self.assertGreater(current.creation_time, 0)
            self.assertEqual(current.image_path, canonical_image(sys.executable))
            with verified_process(os.getpid(), user_sid=current.user_sid,
                                  image_paths=[sys.executable]) as verified:
                self.assertEqual(verified, current)

    def test_wrong_user_or_full_image_is_rejected(self):
        with inspect_process(os.getpid()) as current:
            wrong_sid = "S-1-5-21-111-222-333-1001"
            if wrong_sid == current.user_sid:
                wrong_sid = "S-1-5-21-111-222-333-1002"
            for sid, images in ((wrong_sid, [sys.executable]),
                                (current.user_sid, [str(Path(sys.executable).with_name("other.exe"))])):
                with self.subTest(sid_matches=sid == current.user_sid):
                    with self.assertRaises(PermissionError):
                        with verified_process(os.getpid(), user_sid=sid, image_paths=images):
                            self.fail("unauthorized identity accepted")

    def test_empty_or_ambiguous_image_allowlist_fails_closed(self):
        with inspect_process(os.getpid()) as current:
            for images in ([], sys.executable, ["python.exe"]):
                with self.assertRaises(ValueError):
                    with verified_process(os.getpid(), user_sid=current.user_sid, image_paths=images):
                        pass

    def test_live_child_and_exited_peer(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            with inspect_process(os.getpid()) as current:
                with verified_process(child.pid, user_sid=current.user_sid,
                                      image_paths=[sys.executable]) as peer:
                    self.assertEqual(peer.pid, child.pid)
                    self.assertNotEqual(peer.creation_time, current.creation_time)
                child.terminate()
                child.wait(timeout=5)
                with self.assertRaises((OSError, PermissionError)):
                    with inspect_process(child.pid):
                        self.fail("exited peer accepted")
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
