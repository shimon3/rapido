"""Window changes run on the GUI thread; the local server never waits for it."""
import inspect
import threading
import unittest
from unittest.mock import patch

import desktop


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class UiThreadSafetyTests(unittest.TestCase):
    def test_serial_queue_bounds_window_work_and_preserves_order(self):
        gate = threading.Event()
        first_started = threading.Event()
        second_done = threading.Event()
        order = []
        tasks = desktop.SerialTaskQueue("test-ui-queue")

        def first():
            first_started.set()
            gate.wait(2)
            order.append("first")

        self.assertTrue(tasks.submit(first))
        self.assertTrue(tasks.submit(lambda: (order.append("second"), second_done.set())))
        self.assertTrue(first_started.wait(1))
        self.assertFalse(second_done.is_set(), "the second GUI operation must not run concurrently")
        gate.set()
        self.assertTrue(second_done.wait(1))
        self.assertEqual(order, ["first", "second"])
        self.assertTrue(tasks.stop(1))

    def test_serial_queue_refuses_and_discards_work_after_stop(self):
        gate = threading.Event()
        first_started = threading.Event()
        late_ran = threading.Event()
        tasks = desktop.SerialTaskQueue("test-ui-stop")

        def first():
            first_started.set()
            gate.wait(2)

        self.assertTrue(tasks.submit(first))
        self.assertTrue(tasks.submit(late_ran.set))
        self.assertTrue(first_started.wait(1))
        self.assertFalse(tasks.stop(.01), "the active operation is still deliberately blocked")
        self.assertFalse(tasks.submit(late_ran.set))
        gate.set()
        self.assertTrue(tasks.stop(1))
        self.assertFalse(late_ran.is_set(), "queued window work must not run during shutdown")

    def test_serial_queue_survives_a_failed_operation(self):
        done = threading.Event()
        tasks = desktop.SerialTaskQueue("test-ui-error")

        def failing():
            raise RuntimeError("window already closed")

        with patch("traceback.print_exc") as report:
            self.assertTrue(tasks.submit(failing))
            self.assertTrue(tasks.submit(done.set))
            self.assertTrue(done.wait(1))
            self.assertTrue(tasks.stop(1))
        report.assert_called_once()

    def test_in_background_returns_before_the_slow_window_work(self):
        # Opening a capture window took 1.3-8 s on the Windows 10 VM and the
        # native capture reply timed out ("rapido_unavailable").
        started, release = threading.Event(), threading.Event()
        def slow():
            started.set()
            release.wait(5)
        desktop.in_background(slow, name="test-slow")
        self.assertTrue(started.wait(2))
        release.set()

    def test_in_background_swallows_window_errors(self):
        done = threading.Event()
        def failing():
            done.set()
            raise RuntimeError("window already closed")
        desktop.in_background(failing)
        self.assertTrue(done.wait(2))

    def test_window_changes_are_posted_to_the_form_not_applied_here(self):
        posted = []
        class Form:
            TopMost = True
            activated = False
            def BeginInvoke(self, delegate):
                posted.append(delegate)
            def Activate(self):
                self.activated = True
        form = Form()
        win = type("Win", (), {"native": form})()
        with patch.dict("sys.modules", {"System": type("System", (), {"Action": staticmethod(lambda fn: fn)})}):
            self.assertTrue(desktop.set_topmost(win, False))
            self.assertTrue(form.TopMost, "TopMost must not change on the calling thread")
            posted.pop()()
            self.assertFalse(form.TopMost)
            self.assertTrue(desktop.bring_to_front(win))
            posted.pop()()
            self.assertFalse(form.TopMost)
            self.assertTrue(form.activated)

    def test_without_a_native_form_nothing_is_touched(self):
        self.assertFalse(desktop.set_topmost(type("Win", (), {"native": None})(), False))
        self.assertFalse(desktop.bring_to_front(object()))

    def test_disposed_native_form_refuses_delayed_post_without_escaping(self):
        class Form:
            def BeginInvoke(self, _delegate):
                raise RuntimeError("form disposed")
        win = type("Win", (), {"native": Form()})()
        with patch.dict("sys.modules", {"System": type("System", (), {"Action": staticmethod(lambda fn: fn)})}):
            self.assertFalse(desktop.set_topmost(win, False))

    def test_popup_unpin_is_cancelled_by_shutdown_or_close(self):
        stopping = threading.Event()
        stopping.set()
        with patch.object(desktop, "set_topmost") as set_topmost:
            self.assertFalse(desktop.unpin_after_delay(object(), stopping, lambda: True, delay=0))
            set_topmost.assert_not_called()

        stopping.clear()
        with patch.object(desktop, "set_topmost") as set_topmost:
            self.assertFalse(desktop.unpin_after_delay(object(), stopping, lambda: False, delay=0))
            set_topmost.assert_not_called()

    def test_popup_unpin_posts_only_for_a_live_window(self):
        stopping = threading.Event()
        win = object()
        with patch.object(desktop, "set_topmost", return_value=True) as set_topmost:
            self.assertTrue(desktop.unpin_after_delay(win, stopping, lambda: True, delay=0))
            set_topmost.assert_called_once_with(win, False)

    def test_desktop_no_longer_sets_on_top_from_worker_threads(self):
        source = inspect.getsource(desktop.main)
        self.assertNotIn("on_top = False", source)
        self.assertNotIn("main_win.on_top", source)
        self.assertIn("rapido.manager.open_window = lambda", source)
        self.assertIn("popup_tasks.submit(win.destroy)", source)
        self.assertIn("popup_tasks.stop()", source)
        self.assertIn("if quitting.is_set()", source)

    def test_watchdog_dumps_once_per_stall_and_rearms(self):
        clock, dumps, queue = FakeClock(), [], []
        dog = desktop.UiWatchdog(queue.append, dumps.append, interval=5, stall=10, clock=clock)
        for _ in range(3):           # GUI thread answers every tick
            dog.tick(); queue.pop()(); clock.now += 5
        self.assertEqual(dumps, [])
        for _ in range(5):           # GUI thread stops processing messages
            dog.tick(); clock.now += 5
        self.assertEqual(len(dumps), 1, "one dump per stall")
        self.assertGreaterEqual(dumps[0], 10)
        queue[-1]()                  # GUI thread recovers
        clock.now += 30
        dog.tick()
        self.assertEqual(len(dumps), 2, "a new stall is reported again")

    def test_watchdog_survives_post_errors(self):
        clock, dumps = FakeClock(), []
        def post(_):
            raise RuntimeError("form disposed")
        dog = desktop.UiWatchdog(post, dumps.append, stall=10, clock=clock)
        clock.now = 11
        dog.tick()
        self.assertEqual(len(dumps), 1)


if __name__ == "__main__":
    unittest.main()

