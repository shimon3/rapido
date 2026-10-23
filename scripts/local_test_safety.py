"""pytest plugin for running tests on a developer's own PC.

Loaded only by scripts/run_safe_local_tests.py, never by CI. It:
  * deselects tests that need a disposable Windows machine (VM_ONLY);
  * makes every in-process winreg write fail, so a test cannot change the
    developer's registry even by mistake (reads stay allowed);
  * refuses to start any program outside a short allowlist, because a child
    process (reg.exe, RapidoNativeHost --register-native-hosts, a browser)
    would not see the winreg patch. os.startfile and os.system are refused;
  * refuses to start Rapido itself: binding port 9614, webview windows;
  * never reads the real clipboard (Manager clipboard monitoring is a no-op).
"""
from __future__ import annotations

import os
import sys

# Tests that change real Windows state or need CI-only fixtures.
VM_ONLY = {
    # Writes and deletes real HKCU NativeMessagingHosts keys.
    "tests/test_native_registration.py::RealRegistrationTests":
        "writes real HKCU native-messaging keys",
    # Runs Windows PowerShell with -ExecutionPolicy Bypass and Authenticode checks.
    "tests/test_release_signing_scripts.py::test_candidate_verification_runs_and_rejects_a_mismatch":
        "runs a PowerShell release script with ExecutionPolicy Bypass",
    # Needs signed fixtures produced only by the GitHub-hosted harness.
    "tests/test_windows_signature.py::WindowsSignedFixtureTests":
        "needs CI signed fixtures",
}

_WRITE_FUNCTIONS = ("CreateKey", "CreateKeyEx", "SetValue", "SetValueEx", "DeleteKey",
                    "DeleteKeyEx", "DeleteValue", "SaveKey", "LoadKey", "ConnectRegistry")


def _blocked(name):
    def refuse(*args, **kwargs):
        raise PermissionError(f"{name} is blocked on this PC by local_test_safety")
    return refuse


def _block_registry_writes():
    if os.name != "nt":
        return
    import winreg
    for name in _WRITE_FUNCTIONS:
        setattr(winreg, name, _blocked("winreg." + name))


# Child processes escape the winreg patch, so only these programs may start.
# Anything else (reg, sc, RapidoNativeHost, Rapido, browsers, explorer,
# installers...) is refused before CreateProcess.
_ALLOWED_PROGRAMS = {"node", "python", "pythonw", "bash"}


def _program(args, executable):
    first = executable or (args if isinstance(args, (str, bytes)) else args[0])
    name = os.path.basename(os.fsdecode(first).strip('"')).lower()
    return name[:-4] if name.endswith(".exe") else name


def _allowed_launch(args, executable, shell):
    if shell or isinstance(args, (str, bytes)):
        return False
    words = [os.fsdecode(a).lower() for a in args]
    name = _program(args, executable)
    if name in _ALLOWED_PROGRAMS:
        return True
    if name == "cmd":
        # Junction fixtures only: cmd /d /c mklink /J <alias> <target>
        return words[1:5] == ["/d", "/c", "mklink", "/j"] and len(words) == 7
    if name == "powershell":
        # Parser-only check; scripts (-File) may change system state.
        return "-command" in words and "-file" not in words
    return False


def _block_risky_launches():
    import inspect
    import subprocess
    original = subprocess.Popen._execute_child
    names = list(inspect.signature(original).parameters)
    shell_index = names.index("shell") - names.index("executable") - 1

    def guarded(self, args, executable, *rest):
        shell = rest[shell_index]
        if not _allowed_launch(args, executable, shell):
            raise PermissionError(f"process launch blocked by local_test_safety: {args!r}")
        return original(self, args, executable, *rest)

    subprocess.Popen._execute_child = guarded
    for name in ("startfile", "system"):
        if hasattr(os, name):
            setattr(os, name, _blocked("os." + name))


def _block_running_rapido():
    """No test may start the real application on this PC: its port and its windows.
    (2026-10-23: a test reached desktop.main() and opened WebView2 windows.)"""
    import socket
    original_bind = socket.socket.bind

    def bind(self, address, *args, **kwargs):
        if isinstance(address, tuple) and len(address) >= 2 and address[1] == 9614:
            raise PermissionError("binding Rapido's port 9614 is blocked by local_test_safety")
        return original_bind(self, address, *args, **kwargs)
    socket.socket.bind = bind
    try:
        import webview
    except ImportError:
        return
    for name in ("start", "create_window"):
        setattr(webview, name, _blocked("webview." + name))


def _block_clipboard_monitor():
    """Manager.start() reads the real Windows clipboard; a URL copied during a run would make
    a test probe it over the network. Several tests start a manager with monitoring on."""
    try:
        import engine
    except ImportError:
        return
    engine.Manager._clipboard_loop = lambda self: None


def _vm_only_reason(nodeid):
    nodeid = nodeid.replace("\\", "/")
    for prefix, reason in VM_ONLY.items():
        if nodeid == prefix or nodeid.startswith(prefix + "::"):
            return reason
    return None


def pytest_configure(config):
    if not os.environ.get("RAPIDO_LOCAL_SANDBOX"):
        raise RuntimeError("Use scripts/run_safe_local_tests.py: the sandbox environment is not set")
    _block_registry_writes()
    _block_risky_launches()
    _block_running_rapido()
    _block_clipboard_monitor()


def pytest_collection_modifyitems(config, items):
    kept, removed = [], []
    for item in items:
        (removed if _vm_only_reason(item.nodeid) else kept).append(item)
    if removed:
        config.hook.pytest_deselected(items=removed)
        items[:] = kept
        sys.stderr.write(f"local_test_safety: {len(removed)} VM-only test(s) deselected\n")
