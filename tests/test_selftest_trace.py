"""Self-test diagnostics: CI run 39923348850 was killed after 4 minutes with no result
file and an empty rapido.log, so nothing showed where Rapido waited."""
import inspect
import io
import json
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import desktop


class Clock:
    def __init__(self, *ticks):
        self.ticks = iter(ticks)

    def __call__(self):
        return next(self.ticks)


class SelftestTraceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.out = Path(folder.name) / "selftest.json"

    def test_each_phase_is_timed_and_saved_at_once(self):
        trace = desktop.SelftestTrace(self.out, clock=Clock(10.0, 10.5, 42.25))
        log = io.StringIO()
        with patch("sys.stdout", log):
            trace.phase("instance-check")
            self.assertEqual(json.loads(self.out.read_text("utf-8"))["phase"], "instance-check")
            trace.phase("main-window")
        saved = json.loads(self.out.read_text("utf-8"))
        self.assertEqual(saved, {"ok": False, "phase": "main-window",
                                 "phases": [{"name": "instance-check", "t": 0.5},
                                            {"name": "main-window", "t": 32.25}]})
        self.assertEqual(log.getvalue().splitlines(),
                         ["selftest [   0.50 s] instance-check", "selftest [  32.25 s] main-window"])

    def test_writes_are_atomic_and_never_raise(self):
        trace = desktop.SelftestTrace(self.out)
        self.out.write_text("previous run", "utf-8")
        with patch("sys.stdout", io.StringIO()):
            trace.phase("gui-started")
        self.assertEqual(json.loads(self.out.read_text("utf-8"))["phase"], "gui-started")
        self.assertEqual(sorted(p.name for p in self.out.parent.iterdir()), ["selftest.json"])
        missing = desktop.SelftestTrace(self.out.parent / "missing" / "selftest.json")
        log = io.StringIO()
        with patch("sys.stdout", log):
            missing.phase("gui-started")          # a result that cannot be written never stops Rapido
        self.assertIn("resultat non ecrit", log.getvalue())

    def test_only_phase_names_and_durations_are_added(self):
        # No free-form details: URLs, tokens and paths can never reach the log this way.
        self.assertEqual(list(inspect.signature(desktop.SelftestTrace.phase).parameters), ["self", "name"])
        names = re.findall(r'mark\("([^"]+)"\)', inspect.getsource(desktop.run_selftest))
        names += re.findall(r'(?:trace\.phase|stopped)\([^"]*"([^"]+)"\)', inspect.getsource(desktop.main))
        self.assertGreaterEqual(len(names), 15)
        for name in names:
            self.assertRegex(name, r"^[a-z][a-z-]*$")

    def test_a_stall_dumps_the_stack_of_every_thread(self):
        # A real stall in a child Python (never Rapido): faulthandler writes each thread's stack.
        script = textwrap.dedent("""
            import sys, time, desktop
            trace = desktop.SelftestTrace(sys.argv[1])
            assert trace.watch_for_stalls(every=0.3)
            trace.phase("native-host")
            def waiting_for_the_native_host():
                time.sleep(1.2)
            waiting_for_the_native_host()
            trace.stop_watching()
        """)
        run = subprocess.run([sys.executable, "-c", script, str(self.out)], capture_output=True,
                             text=True, timeout=60, cwd=Path(desktop.__file__).parent)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("waiting_for_the_native_host", run.stderr)
        self.assertIn("Thread", run.stderr)
        self.assertEqual(json.loads(self.out.read_text("utf-8"))["phase"], "native-host")

    def test_stop_watching_cancels_the_dumps(self):
        with patch("faulthandler.dump_traceback_later") as arm, \
                patch("faulthandler.cancel_dump_traceback_later") as cancel:
            trace = desktop.SelftestTrace(self.out)
            self.assertTrue(trace.watch_for_stalls())
            trace.stop_watching()
        arm.assert_called_once_with(desktop.SELFTEST_STALL_DUMP, repeat=True, file=sys.stderr)
        cancel.assert_called_once_with()
        self.assertLess(desktop.SELFTEST_STALL_DUMP * 2, 240, "two dumps before the 4-minute CI limit")


class SelftestPhaseTests(unittest.TestCase):
    def test_a_failure_names_the_phase_it_happened_in(self):
        class Broken:
            def wait(self, timeout):
                raise RuntimeError("WebView2 failed")
        main_win = SimpleNamespace(events=SimpleNamespace(loaded=Broken()))
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        trace = desktop.SelftestTrace(Path(folder.name) / "selftest.json")
        with patch.dict(sys.modules, {"webview": SimpleNamespace(renderer="edgechromium")}), \
                patch("sys.stdout", io.StringIO()):
            desktop.run_selftest(main_win, None, trace.result, trace=trace)
        self.assertEqual([p["name"] for p in trace.result["phases"]], ["main-window", "error"])
        self.assertIn("WebView2 failed", trace.result["error"])
        self.assertFalse(trace.result["ok"])

    def test_run_selftest_without_trace_behaves_as_before(self):
        class Broken:
            def wait(self, timeout):
                raise RuntimeError("no window")
        result = {"ok": False}
        with patch.dict(sys.modules, {"webview": SimpleNamespace(renderer="edgechromium")}):
            desktop.run_selftest(SimpleNamespace(events=SimpleNamespace(loaded=Broken())), None, result)
        self.assertEqual(set(result), {"ok", "renderer", "error"})

    def test_main_traces_only_the_selftest(self):
        source = inspect.getsource(desktop.main)
        self.assertIn("trace = None\n    if args.selftest:\n        trace = SelftestTrace(", source)
        self.assertEqual(source.count("SelftestTrace("), 1)
        self.assertLess(source.index("trace.watch_for_stalls()"), source.index("handle_existing_instance(args)"))
        self.assertIn('trace.phase("finished")', source)
        self.assertIn("trace.stop_watching()", source.split('trace.phase("finished")')[1])
        self.assertNotIn("Path(out).write_text", source)
        self.assertIs(desktop._HEADLESS, False)


if __name__ == "__main__":
    unittest.main()
