"""Per-user native-host registration for Chrome, Edge and Firefox on Windows.

Register only these exact extension identities. Never replace another install's
registry value, and uninstall only values/manifests still owned by this install.
"""
from __future__ import annotations
import json
import os
import re
import stat
from pathlib import Path
from native_paths import has_linked_component as _has_linked_component

HOST = "com.rapido.bridge"
CHROMIUM_ID = "hlpkfnodjoglfdiekijebbppfgkjkbmp"
FIREFOX_ID = "rapido-capture@rapido.local"
MAX_MANIFEST_BYTES = 16 * 1024
BROWSERS = {
    "chrome": (r"Software\Google\Chrome\NativeMessagingHosts", "rapido-native-host.json"),
    "edge": (r"Software\Microsoft\Edge\NativeMessagingHosts", "rapido-native-edge.json"),
    "firefox": (r"Software\Mozilla\NativeMessagingHosts", "rapido-native-firefox.json"),
}


def _same_path(left, right):
    # A registry owner is the exact manifest pathname, not a path redirected
    # through a symbolic link. Never adopt or remove a foreign registration.
    left, right = Path(left), Path(right)
    if _has_linked_component(left) or _has_linked_component(right):
        return False
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def manifests(executable, *, name=HOST):
    if not re.fullmatch(r"[a-z0-9_]+(?:\.[a-z0-9_]+)+", name):
        raise ValueError("Invalid native host name")
    executable = Path(executable)
    if _has_linked_component(executable):
        raise ValueError("Native host executable must not be a symbolic link")
    executable = executable.resolve()
    if executable.name != "RapidoNativeHost.exe" or not executable.is_file():
        raise ValueError("Missing packaged native host")
    if _has_linked_component(executable.with_name("Rapido.exe")):
        raise ValueError("Desktop executable must not be a symbolic link")
    if not executable.with_name("Rapido.exe").is_file():
        raise ValueError("Missing adjacent Rapido executable")
    result = {}
    for browser, (registry, filename) in BROWSERS.items():
        value = {"name":name, "description":"Rapido secure native bridge",
                 "path":str(executable), "type":"stdio"}
        if browser == "firefox":
            value["allowed_extensions"] = [FIREFOX_ID]
        else:
            value["allowed_origins"] = ["chrome-extension://" + CHROMIUM_ID + "/"]
        result[browser] = (registry + "\\" + name, executable.with_name(filename), value)
    return result


class WindowsRegistry:
    def __init__(self):
        if os.name != "nt":
            raise OSError("Native host registration requires Windows")
        import winreg
        self.reg = winreg

    def locations(self, key):
        # Register both views: browser bitness must not select a stale value.
        return [(key, self.reg.KEY_WOW64_32KEY), (key, self.reg.KEY_WOW64_64KEY)]

    def read(self, location):
        key, view = location
        try:
            with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER, key, 0, self.reg.KEY_READ | view) as handle:
                value, kind = self.reg.QueryValueEx(handle, "")
                if kind != self.reg.REG_SZ:
                    raise ValueError("Existing native-host value is not a string")
                return value
        except FileNotFoundError:
            return None

    def write(self, location, value):
        key, view = location
        with self.reg.CreateKeyEx(self.reg.HKEY_CURRENT_USER, key, 0, self.reg.KEY_SET_VALUE | view) as handle:
            self.reg.SetValueEx(handle, "", 0, self.reg.REG_SZ, value)

    def remove(self, location):
        key, view = location
        try:
            with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER, key, 0, self.reg.KEY_SET_VALUE | view) as handle:
                self.reg.DeleteValue(handle, "")
        except FileNotFoundError:
            pass


def _manifest_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate native manifest key")
        result[key] = value
    return result


def _manifest_constant(value):
    raise ValueError("Non-JSON number in native manifest")


def _owned_manifest(path, value):
    # Never follow an attacker-controlled manifest link when checking ownership.
    try:
        if _has_linked_component(path) or not path.is_file():
            return False
        with path.open("rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_MANIFEST_BYTES:
                return False
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            return False
        existing = json.loads(raw.decode("utf-8"), object_pairs_hook=_manifest_pairs,
                              parse_constant=_manifest_constant)
        if not isinstance(existing, dict):
            return False
        expected = dict(value)
        existing.pop("description", None)
        expected.pop("description", None)
        return existing == expected
    except (OSError, ValueError, RecursionError):
        return False


def register(executable, *, registry=None, name=HOST):
    specs = manifests(executable, name=name)
    registry = registry or WindowsRegistry()
    # Validate all browsers before changing any file/value.
    for key, path, value in specs.values():
        if path.exists() and not _owned_manifest(path, value):
            raise FileExistsError("Existing native-host manifest belongs to another registration")
        for location in registry.locations(key):
            current = registry.read(location)
            if current is not None and not _same_path(current, path):
                raise FileExistsError("Another Rapido installation owns this browser registration")
    for key, path, value in specs.values():
        if not path.exists():
            with path.open("x", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
    # Recheck staged manifests and registry ownership before writing any value.
    # This catches changes since preflight, not races after the final check.
    # On failure, newly staged owned files may remain for repair/uninstall.
    for key, path, value in specs.values():
        if not _owned_manifest(path, value):
            raise FileExistsError("Native-host manifest changed before registration")
        for location in registry.locations(key):
            current = registry.read(location)
            if current is not None and not _same_path(current, path):
                raise FileExistsError("Browser registration changed before registration")
    for key, path, value in specs.values():
        for location in registry.locations(key):
            registry.write(location, str(path))
    return list(specs)


def unregister(executable, *, registry=None, name=HOST):
    specs = manifests(executable, name=name)
    registry = registry or WindowsRegistry()
    for key, path, value in specs.values():
        for location in registry.locations(key):
            current = registry.read(location)
            if current is not None and _same_path(current, path):
                registry.remove(location)
        if _owned_manifest(path, value):
            path.unlink()
    return list(specs)
