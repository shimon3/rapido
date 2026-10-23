r"""Uninstall must not leave empty NativeMessagingHosts keys behind.

Windows 10 and 11 runs left empty HKCU ...\NativeMessagingHosts\com.rapido.bridge
keys after uninstall (docs/windows-11-pc-verification-20261018.md). The real
registry is never touched here: WindowsRegistry runs against an in-memory winreg.
"""
import tempfile
import unittest
from pathlib import Path

from native_registration import WindowsRegistry, register, unregister, manifests


class _Handle:
    def __init__(self, path):
        self.path = path
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False


class FakeWinreg:
    r"""HKCU\Software is shared by both registry views, as on 64-bit Windows."""
    HKEY_CURRENT_USER = "HKCU"
    KEY_READ, KEY_SET_VALUE, KEY_QUERY_VALUE = 0x20019, 0x2, 0x1
    KEY_WOW64_32KEY, KEY_WOW64_64KEY = 0x200, 0x100
    REG_SZ = 1

    def __init__(self):
        self.keys = {}

    @staticmethod
    def _norm(key):
        return key.lower()

    def _subkeys(self, path):
        prefix = path + "\\"
        return [k for k in self.keys if k.startswith(prefix)]

    def OpenKey(self, root, key, reserved=0, access=0):
        path = self._norm(key)
        if path not in self.keys:
            raise FileNotFoundError(key)
        return _Handle(path)

    def CreateKeyEx(self, root, key, reserved=0, access=0):
        parts = self._norm(key).split("\\")
        for i in range(1, len(parts) + 1):
            self.keys.setdefault("\\".join(parts[:i]), {})
        return _Handle(self._norm(key))

    def QueryValueEx(self, handle, name):
        if name not in self.keys[handle.path]:
            raise FileNotFoundError(name)
        return self.keys[handle.path][name], self.REG_SZ

    def SetValueEx(self, handle, name, reserved, kind, value):
        self.keys[handle.path][name] = value

    def DeleteValue(self, handle, name):
        if name not in self.keys[handle.path]:
            raise FileNotFoundError(name)
        del self.keys[handle.path][name]

    def QueryInfoKey(self, handle):
        direct = [k for k in self._subkeys(handle.path) if "\\" not in k[len(handle.path) + 1:]]
        return len(direct), len(self.keys[handle.path]), 0

    def DeleteKeyEx(self, root, key, access=0, reserved=0):
        path = self._norm(key)
        if path not in self.keys:
            raise FileNotFoundError(key)
        if self._subkeys(path):
            raise PermissionError("key has subkeys")
        del self.keys[path]


def fake_registry():
    registry = WindowsRegistry.__new__(WindowsRegistry)
    registry.reg = FakeWinreg()
    return registry


class RegistryCleanupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.exe = Path(temp.name).resolve() / "RapidoNativeHost.exe"
        self.exe.touch()
        self.exe.with_name("Rapido.exe").touch()
        self.registry = fake_registry()
        self.reg = self.registry.reg

    def host_keys(self):
        return sorted(k for k in self.reg.keys if k.endswith("\\com.rapido.bridge"))

    def test_uninstall_removes_owned_host_keys_but_keeps_parents(self):
        register(self.exe, registry=self.registry)
        self.assertEqual(len(self.host_keys()), 3)
        unregister(self.exe, registry=self.registry)
        self.assertEqual(self.host_keys(), [])
        # The browsers' own NativeMessagingHosts parents are not ours to delete.
        for key, _, _ in manifests(self.exe).values():
            self.assertIn(key.lower().rsplit("\\", 1)[0], self.reg.keys)

    def test_foreign_owner_value_and_key_are_preserved(self):
        register(self.exe, registry=self.registry)
        key, path, _ = manifests(self.exe)["edge"]
        foreign = str(path.with_name("other-install.json"))
        with self.reg.OpenKey(None, key) as handle:
            self.reg.SetValueEx(handle, "", 0, self.reg.REG_SZ, foreign)
        unregister(self.exe, registry=self.registry)
        self.assertEqual(self.registry.read((key, self.reg.KEY_WOW64_64KEY)), foreign)
        self.assertIn(key.lower(), self.reg.keys)
        self.assertEqual(len(self.host_keys()), 1)

    def test_key_with_other_values_or_subkeys_is_kept(self):
        register(self.exe, registry=self.registry)
        chrome, _, _ = manifests(self.exe)["chrome"]
        firefox, _, _ = manifests(self.exe)["firefox"]
        with self.reg.OpenKey(None, chrome) as handle:
            self.reg.SetValueEx(handle, "note", 0, self.reg.REG_SZ, "someone else's")
        self.reg.CreateKeyEx(None, firefox + "\\child")
        unregister(self.exe, registry=self.registry)
        self.assertEqual(self.reg.keys[chrome.lower()], {"note": "someone else's"})
        self.assertIn(firefox.lower(), self.reg.keys)
        self.assertNotIn(manifests(self.exe)["edge"][0].lower(), self.reg.keys)

    def test_remove_of_missing_key_is_harmless(self):
        key, _, _ = manifests(self.exe)["chrome"]
        for location in self.registry.locations(key):
            self.registry.remove(location)
        self.assertEqual(self.reg.keys, {})


if __name__ == "__main__":
    unittest.main()
