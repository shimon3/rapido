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


class PortProbeTests(unittest.TestCase):
    """already_running() on a real loopback port. Windows reports a refused loopback
    connection only after ~2 s, so the 1.5 s ping timed out while connecting: the free
    port was taken for a busy Rapido and every launch ended on a modal message
    (CI run 39923348850, self-test killed after 4 minutes)."""

    @staticmethod
    def closed_port_url():
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        return f"http://127.0.0.1:{port}"

    def serve(self, status, body):
        import http.server
        import threading

        class Fixed(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fixed)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def probe(self, base):
        with patch.object(desktop, "BASE_URL", base), patch.object(desktop, "_rapido", None):
            return desktop.already_running()

    def test_closed_local_port_is_free(self):
        self.assertIs(self.probe(self.closed_port_url()), False)

    def test_free_port_starts_without_waiting_or_any_message(self):
        with patch.object(desktop, "BASE_URL", self.closed_port_url()), \
                patch.object(desktop, "_rapido", None), \
                patch.object(desktop, "wait_for_running", return_value=False) as wait, \
                patch.object(desktop, "message_box") as box:
            self.assertIsNone(desktop.handle_existing_instance(args()))
        wait.assert_not_called()
        box.assert_not_called()

    def test_foreign_http_service_is_another_program(self):
        self.assertEqual(self.probe(self.serve(404, b'{"detail": "Not Found"}')), "other")
        self.assertEqual(self.probe(self.serve(200, b'{"app": "Other"}')), "other")
        self.assertEqual(self.probe(self.serve(200, b"<html>")), "other")

    def test_each_failure_phase_is_classified(self):
        import http.client
        import socket
        import urllib.error
        cases = [
            # Raised while connecting (urllib wraps them): nothing accepted the connection.
            (urllib.error.URLError(TimeoutError("timed out")), False),
            (urllib.error.URLError(ConnectionRefusedError(10061, "refused")), False),
            (urllib.error.URLError(OSError("network unreachable")), False),
            # Raised after the connection was accepted (urllib does not wrap them).
            (TimeoutError("timed out"), "busy"),
            (socket.timeout("timed out"), "busy"),
            (ConnectionResetError(10054, "reset"), "other"),
            (http.client.RemoteDisconnected("closed"), "other"),
            (urllib.error.HTTPError("http://127.0.0.1:9614/api/ping", 404, "Not Found", {}, None), "other"),
            (ValueError("not JSON"), "other"),
        ]
        for error, expected in cases:
            with self.subTest(error=repr(error)), patch.object(desktop, "_rapido", None), \
                    patch("urllib.request.urlopen", side_effect=error):
                state = desktop.already_running()
                self.assertEqual((type(state), state), (type(expected), expected))


class SelftestDialogTests(unittest.TestCase):
    """Nobody can click OK on the CI runner: a self-test must never open a modal box."""

    def test_selftest_messages_are_logged_not_shown(self):
        import io
        out = io.StringIO()
        with patch.object(desktop, "_HEADLESS", True), \
                patch("ctypes.windll", create=True) as windll, \
                patch("sys.stdout", out):
            desktop.message_box("Rapido ne peut pas demarrer.", True)
        windll.user32.MessageBoxW.assert_not_called()
        self.assertIn("Rapido ne peut pas demarrer.", out.getvalue())

    def test_normal_launch_still_shows_the_message(self):
        with patch.object(desktop, "_HEADLESS", False), patch("ctypes.windll", create=True) as windll:
            desktop.message_box("info")
        windll.user32.MessageBoxW.assert_called_once()

    def test_main_enables_headless_mode_for_the_selftest_only(self):
        import inspect
        source = inspect.getsource(desktop.main)
        self.assertIn("_HEADLESS = bool(args.selftest)", source)
        self.assertLess(source.index("_HEADLESS = bool(args.selftest)"),
                        source.index("handle_existing_instance(args)"))
