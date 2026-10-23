"""The local safe runner must keep VM-only tests and registry writes off a developer PC."""
import os
import re
import tempfile
import unittest
from pathlib import Path

from scripts import local_test_safety as safety
from scripts import run_safe_local_tests as runner

ROOT = Path(__file__).resolve().parents[1]


class LocalTestSafetyTests(unittest.TestCase):
    def test_every_vm_only_entry_names_an_existing_test(self):
        for nodeid in safety.VM_ONLY:
            path, _, name = nodeid.partition("::")
            source = (ROOT / path).read_text(encoding="utf-8")
            self.assertRegex(source, r"(?m)^\s*(class|def) " + re.escape(name) + r"\b", nodeid)

    def test_real_registry_class_is_vm_only(self):
        source = (ROOT / "tests" / "test_native_registration.py").read_text(encoding="utf-8")
        self.assertIn("registry=WindowsRegistry()", source)
        self.assertTrue(safety._vm_only_reason(
            "tests/test_native_registration.py::RealRegistrationTests::test_real_registry_register_and_preserve_other_install"))
        self.assertTrue(safety._vm_only_reason(
            "tests\\test_native_registration.py::RealRegistrationTests"))
        self.assertIsNone(safety._vm_only_reason(
            "tests/test_native_registration.py::RegistrationTests::test_three_browsers_exact_identities_and_idempotent_registration"))
        self.assertIsNone(safety._vm_only_reason(
            "tests/test_native_registration.py::RealRegistrationTestsMore"))

    def test_blocked_registry_function_refuses(self):
        with self.assertRaises(PermissionError):
            safety._blocked("SetValueEx")(None, "", 0, 1, "x")
        self.assertIn("SetValueEx", safety._WRITE_FUNCTIONS)
        self.assertIn("DeleteKeyEx", safety._WRITE_FUNCTIONS)

    def test_only_audited_programs_may_start(self):
        allowed = [
            (["C:\\node\\node.exe", "x.cjs"], None),
            (["C:\\py\\python.exe", "-c", "pass"], None),
            (["C:\\Git\\bin\\bash.exe", "--noprofile", "-c", "true"], None),
            (["cmd", "/d", "/c", "mklink", "/J", "alias", "target"], None),
            (["powershell", "-NoProfile", "-Command", "parse"], None),
        ]
        refused = [
            (["reg", "add", "HKCU\\Software\\X"], None),
            (["C:\\Rapido\\RapidoNativeHost.exe", "--register-native-hosts"], None),
            (["C:\\Rapido\\Rapido.exe", "--tray"], None),
            (["explorer", "/select,", "C:\\x"], None),
            (["firefox.exe"], None), (["msedge.exe"], None), (["chrome.exe"], None),
            (["sc", "stop", "x"], None),
            (["cmd", "/c", "reg", "add", "x"], None),
            (["cmd", "/d", "/c", "mklink", "/J", "a", "b", "&", "reg"], None),
            (["powershell", "-ExecutionPolicy", "Bypass", "-File", "x.ps1"], None),
            (["python.exe"], "C:\\Windows\\System32\\reg.exe"),
        ]
        for args, executable in allowed:
            self.assertTrue(safety._allowed_launch(args, executable, False), args)
        for args, executable in refused:
            self.assertFalse(safety._allowed_launch(args, executable, False), args)
        self.assertFalse(safety._allowed_launch(["python", "-c", "pass"], None, True), "shell")
        self.assertFalse(safety._allowed_launch("reg add x", None, False), "string command")

    def test_rapido_port_and_windows_are_refused_when_the_guard_runs(self):
        source = Path(safety.__file__).read_text(encoding="utf-8")
        self.assertIn("_block_running_rapido()", source.split("def pytest_configure")[1])
        self.assertIn("address[1] == 9614", source)
        self.assertIn('for name in ("start", "create_window")', source)

    def test_clipboard_monitoring_is_disabled_by_the_guard(self):
        source = Path(safety.__file__).read_text(encoding="utf-8")
        self.assertIn("_block_clipboard_monitor()", source.split("def pytest_configure")[1])
        self.assertIn("engine.Manager._clipboard_loop = lambda self: None", source)

    def test_sandbox_redirects_profile_temp_and_rapido_data(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            env = runner.sandbox_environment(base)
            for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "RAPIDO_DATA"):
                self.assertTrue(Path(env[key]).is_relative_to(base), key)
                self.assertTrue(Path(env[key]).is_dir(), key)
            self.assertEqual(env["RAPIDO_LOCAL_SANDBOX"], "1")
            self.assertNotIn("RAPIDO_SIGNATURE_FIXTURES", env)

    def test_each_run_gets_its_own_sandbox(self):
        source = Path(runner.__file__).read_text(encoding="utf-8")
        self.assertIn("os.getpid()", source.split("def main")[1])

    def test_plugin_refuses_to_run_outside_the_runner(self):
        saved = os.environ.pop("RAPIDO_LOCAL_SANDBOX", None)
        try:
            with self.assertRaises(RuntimeError):
                safety.pytest_configure(None)
        finally:
            if saved is not None:
                os.environ["RAPIDO_LOCAL_SANDBOX"] = saved


if __name__ == "__main__":
    unittest.main()
