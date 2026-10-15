"""Self-test main-window load wait: late WebView2 cold starts must not fail, missing loads must."""
import inspect
import threading
import time
import unittest
from types import SimpleNamespace

import desktop

try:
    from webview.event import Event as PywebviewEvent
except ImportError:  # pywebview is installed on the Windows CI runner
    PywebviewEvent = None


class FakeEvent:
    def __init__(self):
        self._items, self._event = [], threading.Event()

    def __iadd__(self, item):
        self._items.append(item)
        return self

    def set(self):
        for item in self._items:
            item()
        self._event.set()

    def wait(self, timeout=None):
        return self._event.wait(timeout)


class FakeWindow:
    def __init__(self, event=FakeEvent, href=desktop.BASE_URL + "/"):
        self.events = SimpleNamespace(shown=event(), before_load=event(), loaded=event())
        self.href, self.scripts = href, []

    def evaluate_js(self, script):
        if not self.events.loaded.wait(0):
            raise AssertionError("evaluate_js before loaded")
        self.scripts.append(script)
        return self.href if script == "location.href" else None


class SelftestLoadWaitTests(unittest.TestCase):
    def test_first_window_timeout_covers_observed_cold_start(self):
        # CI run 38787572553 attempts 1-2: loaded fired between 30 and 50 s.
        self.assertGreaterEqual(desktop.SELFTEST_FIRST_LOAD_TIMEOUT, 60)
        self.assertEqual(desktop.SELFTEST_POPUP_LOAD_TIMEOUT, 30)
        source = inspect.getsource(desktop.run_selftest)
        self.assertIn("wait_main_loaded(main_win, result, main_timeline)", source)
        self.assertNotIn("main_win.events.loaded.wait(", source)
        self.assertIn('result["main_url_ok"]', inspect.getsource(desktop.run_selftest).split("result[\"ok\"]")[1])

    def test_late_loaded_event_passes_and_is_timed(self):
        window, ticks = FakeWindow(), iter([0.0, 0.5, 2.0, 41.25])
        timeline = desktop.track_window_load(window, clock=lambda: next(ticks))
        def fire():
            time.sleep(0.2)
            window.events.shown.set()
            window.events.before_load.set()
            window.events.loaded.set()
        threading.Thread(target=fire).start()
        result = {}
        self.assertTrue(desktop.wait_main_loaded(window, result, timeline, timeout=5))
        self.assertEqual(result, {"main_loaded": True, "main_url_ok": True,
            "main_load_timeline": {"shown": 0.5, "before_load": 2.0, "loaded": 41.25}})

    def test_missing_loaded_event_still_fails_without_touching_the_page(self):
        window, result = FakeWindow(), {}
        timeline = desktop.track_window_load(window)
        self.assertFalse(desktop.wait_main_loaded(window, result, timeline, timeout=0.1))
        self.assertEqual(result["main_loaded"], False)
        self.assertEqual(result["main_url_ok"], False)
        self.assertEqual(result["main_load_timeline"], {})
        self.assertEqual(window.scripts, [])

    def test_loaded_page_must_be_the_trusted_main_page(self):
        for href in ("about:blank", desktop.BASE_URL + "/w", "https://evil.example/", None):
            window, result = FakeWindow(href=href), {}
            window.events.loaded.set()
            self.assertTrue(desktop.wait_main_loaded(window, result, timeout=1))
            self.assertFalse(result["main_url_ok"], href)

    @unittest.skipIf(PywebviewEvent is None, "pywebview not installed")
    def test_tracking_uses_real_pywebview_event_semantics(self):
        window = FakeWindow(event=lambda: None)
        window.events = SimpleNamespace(shown=PywebviewEvent(window), loaded=PywebviewEvent(window),
                                        before_load=PywebviewEvent(window, should_lock=True))
        timeline = desktop.track_window_load(window, clock=iter([0.0, 1.0, 3.0]).__next__)
        window.events.before_load.set()
        self.assertEqual(timeline, {"before_load": 1.0})
        window.events.loaded.set()  # non-locking: handler runs on its own thread
        for _ in range(50):
            if "loaded" in timeline:
                break
            time.sleep(0.02)
        self.assertEqual(timeline, {"before_load": 1.0, "loaded": 3.0})
        self.assertTrue(window.events.loaded.wait(0))


if __name__ == "__main__":
    unittest.main()
