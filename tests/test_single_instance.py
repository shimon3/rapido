"""A second launch brings the running Rapido forward instead of showing errors."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import desktop


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = 0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps += 1
        self.now += seconds


def args(selftest=False, tray=False):
    return SimpleNamespace(selftest=selftest, tray=tray)


class SingleInstanceTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        patcher = patch.object(desktop, "time", self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_starting_instance_is_retried_until_its_window_answers(self):
        # Seen on the Windows 10 VM: an instance still starting refused "show",
        # and the second launch showed an error instead of waiting.
        replies = [OSError("pipe not ready"), {"ok": False}, {"ok": True}]
        def request(message, server_images, timeout):
            self.assertEqual(message, {"type": "show"})
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        with patch("native_pipe.request", side_effect=request):
            self.assertTrue(desktop.wake_existing(self.clock.monotonic() + desktop.START_WAIT))
        self.assertEqual(replies, [])

    def test_unresponsive_instance_gives_up_after_the_deadline(self):
        with patch("native_pipe.request", side_effect=TimeoutError("hung")):
            self.assertFalse(desktop.wake_existing(self.clock.monotonic() + 5))
        self.assertGreaterEqual(self.clock.now, 1005.0)

    def test_second_launch_shows_existing_window_without_any_message(self):
        with patch.object(desktop, "wake_existing", return_value=True) as wake, \
                patch.object(desktop, "message_box") as box:
            self.assertEqual(desktop.defer_to_running(args()), 0)
        wake.assert_called_once()
        box.assert_not_called()

    def test_hung_instance_produces_exactly_one_clear_message(self):
        with patch.object(desktop, "wake_existing", return_value=False), \
                patch.object(desktop, "message_box") as box:
            self.assertEqual(desktop.defer_to_running(args()), 1)
        box.assert_called_once()
        self.assertIn("ne repond pas", box.call_args.args[0])

    def test_tray_autostart_and_selftest_never_disturb_the_running_instance(self):
        with patch.object(desktop, "wake_existing") as wake, patch.object(desktop, "message_box") as box:
            self.assertEqual(desktop.defer_to_running(args(tray=True)), 0)
            self.assertEqual(desktop.defer_to_running(args(selftest=True)), 2)
        wake.assert_not_called()
        box.assert_not_called()

    def test_simultaneous_launch_waits_for_the_other_instance(self):
        states = iter([False, "other", True])
        with patch.object(desktop, "already_running", side_effect=lambda: next(states)):
            self.assertTrue(desktop.wait_for_running(self.clock.monotonic() + desktop.START_WAIT))
        with patch.object(desktop, "already_running", return_value=False):
            self.assertFalse(desktop.wait_for_running(self.clock.monotonic() + 3))


if __name__ == "__main__":
    unittest.main()


class BusyInstanceTests(unittest.TestCase):
    """A running Rapido whose loop is busy answers /api/ping late: the response timeout
    raised TimeoutError, reported as "port used by another program"."""

    def serve(self, delay):
        import http.server
        import socket
        import threading

        class Slow(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                import time as _t
                _t.sleep(delay)
                body = b'{"app": "Rapido"}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Slow)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def test_slow_rapido_is_busy_not_another_program(self):
        base = self.serve(3)
        with patch.object(desktop, "BASE_URL", base), patch.object(desktop, "_rapido", None):
            self.assertEqual(desktop.already_running(), "busy")

    def test_prompt_rapido_is_detected(self):
        base = self.serve(0)
        with patch.object(desktop, "BASE_URL", base), patch.object(desktop, "_rapido", None):
            self.assertIs(desktop.already_running(), True)

    # Never call desktop.main() here: past these checks it really starts Rapido
    # (server on 127.0.0.1:9614 and WebView2 windows).
    def test_busy_instance_is_waited_for_then_brought_forward(self):
        states = iter(["busy"])
        with patch.object(desktop, "already_running", side_effect=lambda: next(states, True)), \
                patch.object(desktop.time, "sleep"), \
                patch.object(desktop, "wake_existing", return_value=True) as wake, \
                patch.object(desktop, "message_box") as box:
            self.assertEqual(desktop.handle_existing_instance(args()), 0)
        wake.assert_called_once()
        box.assert_not_called()

    def test_instance_busy_until_the_deadline_is_not_called_another_program(self):
        with patch.object(desktop, "already_running", return_value="busy"), \
                patch.object(desktop, "wait_for_running", return_value=False), \
                patch.object(desktop, "message_box") as box:
            self.assertEqual(desktop.handle_existing_instance(args()), 1)
        self.assertIn("ne repond pas", box.call_args.args[0])
        self.assertNotIn("autre programme", box.call_args.args[0])

    def test_free_port_continues_and_foreign_port_stops(self):
        with patch.object(desktop, "already_running", return_value=False):
            self.assertIsNone(desktop.handle_existing_instance(args()))
        with patch.object(desktop, "already_running", return_value="other"), \
                patch.object(desktop, "message_box") as box:
            self.assertEqual(desktop.handle_existing_instance(args()), 1)
        self.assertIn("autre programme", box.call_args.args[0])
