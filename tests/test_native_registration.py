import base64
import hashlib
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from native_registration import register, unregister, manifests, WindowsRegistry, CHROMIUM_ID

class FakeRegistry:
    def __init__(self):
        self.values = {}
    def locations(self, key):
        return [(key,32),(key,64)]
    def read(self, key):
        return self.values.get(key)
    def write(self, key, value):
        self.values[key] = value
    def remove(self, key):
        self.values.pop(key,None)

def prepare(test):
    temp=tempfile.TemporaryDirectory()
    test.addCleanup(temp.cleanup)
    exe=Path(temp.name).resolve()/"RapidoNativeHost.exe"
    exe.touch()
    exe.with_name("Rapido.exe").touch()
    return exe

class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.exe=prepare(self)
        self.registry = FakeRegistry()

    def test_three_browsers_exact_identities_and_idempotent_registration(self):
        register(self.exe,registry=self.registry)
        register(self.exe,registry=self.registry)
        self.assertEqual(len(self.registry.values),6)
        for browser,(key,path,value) in manifests(self.exe).items():
            self.assertEqual(json.loads(path.read_text()),value)
            self.assertEqual(value["path"],str(self.exe))
            if browser == "firefox":
                self.assertEqual(value["allowed_extensions"],["rapido-capture@rapido.local"])
                self.assertNotIn("allowed_origins",value)
            else:
                self.assertEqual(value["allowed_origins"],["chrome-extension://"+CHROMIUM_ID+"/"])
                self.assertNotIn("allowed_extensions",value)
        unregister(self.exe,registry=self.registry)
        self.assertFalse(self.registry.values)
        unregister(self.exe,registry=self.registry)

    def test_chromium_identity_matches_bundled_public_key(self):
        path=Path(__file__).resolve().parents[1]/"extension"/"manifest.json"
        key=json.loads(path.read_text())["key"]
        digest=hashlib.sha256(base64.b64decode(key,validate=True)).digest()[:16].hex()
        identity="".join(chr(ord("a")+int(c,16)) for c in digest)
        self.assertEqual(identity,CHROMIUM_ID)

    def test_collision_is_rejected_before_any_browser_is_modified(self):
        specs=manifests(self.exe)
        key,path,_=specs["firefox"]
        self.registry.values[(key,64)]=str(path.with_name("other.json"))
        before=dict(self.registry.values)
        with self.assertRaises(FileExistsError):
            register(self.exe,registry=self.registry)
        self.assertEqual(self.registry.values,before)
        self.assertFalse(any(path.exists() for _,path,_ in specs.values()))

    def test_separate_install_cannot_replace_or_unregister_owned_browser_hosts(self):
        first = self.exe
        second = prepare(self)
        self.assertNotEqual(first.parent, second.parent)
        register(first, registry=self.registry)
        expected = dict(self.registry.values)
        first_manifests = manifests(first)
        second_manifests = manifests(second)
        with self.assertRaises(FileExistsError):
            register(second, registry=self.registry)
        self.assertEqual(self.registry.values, expected)
        self.assertTrue(all(path.is_file() for _, path, _ in first_manifests.values()))
        self.assertFalse(any(path.exists() for _, path, _ in second_manifests.values()))
        unregister(second, registry=self.registry)
        self.assertEqual(self.registry.values, expected)
        self.assertTrue(all(path.is_file() for _, path, _ in first_manifests.values()))
        unregister(first, registry=self.registry)
        self.assertFalse(self.registry.values)

    def test_registry_symlink_alias_cannot_claim_manifest_ownership(self):
        register(self.exe, registry=self.registry)
        key, path, value = manifests(self.exe)["edge"]
        alternate = path.with_name("foreign-alias.json")
        try:
            alternate.symlink_to(path)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation not permitted on this runner")
        location = self.registry.locations(key)[0]
        self.registry.values[location] = str(alternate)
        before = dict(self.registry.values)
        with self.assertRaises(FileExistsError):
            register(self.exe, registry=self.registry)
        self.assertEqual(self.registry.values, before)
        unregister(self.exe, registry=self.registry)
        self.assertEqual(self.registry.values, {location: str(alternate)})
        self.assertTrue(alternate.is_symlink())

    def test_uninstall_preserves_replaced_registration_and_modified_manifest(self):
        register(self.exe,registry=self.registry)
        key,path,value=manifests(self.exe)["edge"]
        other=str(path.with_name("other.json"))
        self.registry.values[(key,32)]=other
        path.write_text('{"other":true}')
        unregister(self.exe,registry=self.registry)
        self.assertEqual(self.registry.values,{(key,32):other})
        self.assertEqual(json.loads(path.read_text()),{"other":True})

    def test_upgrade_accepts_old_owned_chrome_description(self):
        _,path,value=manifests(self.exe)["chrome"]
        value["description"]="Rapido native messaging diagnostics"
        path.write_text(json.dumps(value))
        register(self.exe,registry=self.registry)
        unregister(self.exe,registry=self.registry)
        self.assertFalse(path.exists())

    def test_non_object_manifests_are_refused_without_breaking_other_cleanup(self):
        for content in ('null', '[]', '"foreign"', '42', 'true'):
            with self.subTest(content=content):
                exe = prepare(self)
                registry = FakeRegistry()
                register(exe, registry=registry)
                specs = manifests(exe)
                path = specs["chrome"][1]
                path.write_text(content, encoding="utf-8")
                before = dict(registry.values)
                with self.assertRaises(FileExistsError):
                    register(exe, registry=registry)
                self.assertEqual(registry.values, before)
                unregister(exe, registry=registry)
                self.assertFalse(registry.values)
                self.assertEqual(path.read_text(encoding="utf-8"), content)
                self.assertFalse(specs["edge"][1].exists())
                self.assertFalse(specs["firefox"][1].exists())

    def test_ambiguous_invalid_and_oversized_manifests_are_not_adopted_or_deleted(self):
        for kind in ("duplicate_path", "non_json_number", "oversized", "deep_json", "invalid_utf8"):
            with self.subTest(kind=kind):
                exe = prepare(self)
                registry = FakeRegistry()
                _, path, value = manifests(exe)["chrome"]
                content = json.dumps(value)
                if kind == "duplicate_path":
                    content = '{"path":"C:/foreign.exe",' + content[1:]
                elif kind == "non_json_number":
                    value["description"] = float("nan")
                    content = json.dumps(value)
                elif kind == "oversized":
                    value["description"] = "x" * 20000
                    content = json.dumps(value)
                elif kind == "deep_json":
                    content = "[" * 1100 + "]" * 1100
                raw = b"\xff" if kind == "invalid_utf8" else content.encode("utf-8")
                path.write_bytes(raw)
                with self.assertRaises(FileExistsError):
                    register(exe, registry=registry)
                self.assertFalse(registry.values)
                unregister(exe, registry=registry)
                self.assertEqual(path.read_bytes(), raw)

    def test_late_foreign_manifest_is_rejected_before_registry_writes(self):
        specs = manifests(self.exe)
        last_key, last_path, _ = specs["firefox"]
        last_location = self.registry.locations(last_key)[-1]
        original_read = self.registry.read
        injected = False
        def read(location):
            nonlocal injected
            value = original_read(location)
            if location == last_location and not injected:
                last_path.write_text('{"foreign":true}', encoding="utf-8")
                injected = True
            return value
        self.registry.read = read
        with self.assertRaises(FileExistsError):
            register(self.exe, registry=self.registry)
        self.assertFalse(self.registry.values)
        self.assertEqual(json.loads(last_path.read_text()), {"foreign": True})

    def test_late_foreign_registry_owner_is_not_overwritten(self):
        specs = manifests(self.exe)
        chrome_key, chrome_path, _ = specs["chrome"]
        victim = self.registry.locations(chrome_key)[0]
        last_key = specs["firefox"][0]
        last_location = self.registry.locations(last_key)[-1]
        original_read = self.registry.read
        foreign = str(chrome_path.with_name("foreign-owner.json"))
        injected = False
        def read(location):
            nonlocal injected
            value = original_read(location)
            if location == last_location and not injected:
                self.registry.values[victim] = foreign
                injected = True
            return value
        self.registry.read = read
        with self.assertRaises(FileExistsError):
            register(self.exe, registry=self.registry)
        self.assertEqual(self.registry.values, {victim: foreign})

    def test_linked_manifest_is_not_adopted_or_deleted(self):
        _,path,value=manifests(self.exe)["chrome"]
        target=path.with_name("external-manifest.json")
        target.write_text(json.dumps(value))
        try:
            path.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation not permitted on this runner")
        with self.assertRaises(FileExistsError):
            register(self.exe,registry=self.registry)
        self.assertFalse(self.registry.values)
        unregister(self.exe,registry=self.registry)
        self.assertTrue(path.is_symlink())
        self.assertEqual(json.loads(target.read_text()),value)

    def test_symlinked_install_directory_is_rejected(self):
        target = self.exe.parent
        alias = target.parent / ("rapido-link-" + uuid.uuid4().hex)
        try:
            alias.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Directory symlink creation not permitted")
        self.addCleanup(lambda: alias.unlink(missing_ok=True))
        with self.assertRaises(ValueError):
            manifests(alias / "RapidoNativeHost.exe")
        register(self.exe, registry=self.registry)
        key, path, _ = manifests(self.exe)["edge"]
        self.registry.values[self.registry.locations(key)[0]] = str(alias / path.name)
        with self.assertRaises(FileExistsError):
            register(self.exe, registry=self.registry)
        unregister(self.exe, registry=self.registry)
        self.assertEqual(self.registry.values,
                         {self.registry.locations(key)[0]: str(alias / path.name)})

    @unittest.skipUnless(os.name == "nt", "Real Windows junction")
    def test_real_junction_registration_rejected_without_registry_change(self):
        import subprocess
        target = self.exe.parent
        alias = target.parent / ("rapido-junction-" + uuid.uuid4().hex)
        created = subprocess.run(
            ["cmd", "/d", "/c", "mklink", "/J", str(alias), str(target)],
            capture_output=True, text=True, check=True,
        )
        self.assertTrue(alias.is_junction(), created.stdout)
        self.addCleanup(alias.rmdir)
        with self.assertRaises(ValueError):
            register(alias / "RapidoNativeHost.exe", registry=self.registry)
        self.assertFalse(self.registry.values)

        register(self.exe, registry=self.registry)
        key, path, _ = manifests(self.exe)["firefox"]
        location = self.registry.locations(key)[0]
        foreign_path = alias / path.name
        self.registry.values[location] = str(foreign_path)
        with self.assertRaises(FileExistsError):
            register(self.exe, registry=self.registry)
        unregister(self.exe, registry=self.registry)
        self.assertEqual(self.registry.values, {location: str(foreign_path)})
        self.assertTrue(alias.is_junction())

    @unittest.skipUnless(os.name == "nt", "Windows junction detection")
    def test_junction_install_directory_is_rejected(self):
        from unittest.mock import patch
        directory = self.exe.parent
        original = Path.is_junction

        def simulated_junction(path):
            return path == directory or original(path)

        with patch.object(Path, "is_junction", autospec=True,
                          side_effect=simulated_junction):
            with self.assertRaises(ValueError):
                manifests(self.exe)
            self.assertFalse(self.registry.values)
            with self.assertRaises(ValueError):
                register(self.exe, registry=self.registry)
            self.assertFalse(self.registry.values)

    @unittest.skipUnless(os.name == "nt", "Windows junction detection")
    def test_junction_registry_alias_preserves_foreign_registration(self):
        from unittest.mock import patch
        register(self.exe, registry=self.registry)
        key, path, _ = manifests(self.exe)["edge"]
        location = self.registry.locations(key)[0]
        alias_root = path.parent.parent / "junction-alias"
        foreign = alias_root / path.parent.name / path.name
        self.registry.values[location] = str(foreign)
        original = Path.is_junction

        def simulated_junction(candidate):
            return candidate == alias_root or original(candidate)

        with patch.object(Path, "is_junction", autospec=True,
                          side_effect=simulated_junction):
            with self.assertRaises(FileExistsError):
                register(self.exe, registry=self.registry)
            unregister(self.exe, registry=self.registry)
        self.assertEqual(self.registry.values, {location: str(foreign)})

    def test_linked_host_and_desktop_executables_are_rejected(self):
        target=self.exe.with_name("original-native-host.exe")
        target.touch()
        try:
            link=self.exe.with_name("linked-host.exe")
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation not permitted on this runner")
        # Exercise the exact packaged filename by replacing the fixture.
        self.exe.unlink()
        self.exe.symlink_to(target)
        with self.assertRaises(ValueError):
            manifests(self.exe)
        self.exe.unlink()
        self.exe.touch()
        desktop=self.exe.with_name("Rapido.exe")
        desktop.unlink()
        desktop.symlink_to(target)
        with self.assertRaises(ValueError):
            manifests(self.exe)

    def test_missing_desktop_and_foreign_manifest_are_refused(self):
        self.exe.with_name("Rapido.exe").unlink()
        with self.assertRaises(ValueError):
            register(self.exe,registry=self.registry)
        self.exe.with_name("Rapido.exe").touch()
        _,path,value=manifests(self.exe)["chrome"]
        value["allowed_origins"]=["chrome-extension://other/"]
        path.write_text(json.dumps(value))
        with self.assertRaises(FileExistsError):
            register(self.exe,registry=self.registry)
        self.assertFalse(self.registry.values)

def app_container():
    if os.name!="nt":
        return False
    import ctypes
    from ctypes import wintypes
    from windows_peer import _windows
    k,a=_windows()
    process=k.OpenProcess(0x1000,False,os.getpid())
    if not process:
        raise ctypes.WinError(ctypes.get_last_error())
    token=wintypes.HANDLE()
    try:
        if not a.OpenProcessToken(process,8,ctypes.byref(token)):
            raise ctypes.WinError(ctypes.get_last_error())
        value,size=wintypes.DWORD(),wintypes.DWORD()
        if not a.GetTokenInformation(token,29,ctypes.byref(value),4,ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return bool(value.value)
    finally:
        if token.value:
            k.CloseHandle(token)
        k.CloseHandle(process)

@unittest.skipIf(os.name!="nt" or app_container(),"Real desktop registry unavailable in AppContainer/non-Windows")
class RealRegistrationTests(unittest.TestCase):
    def test_real_registry_register_and_preserve_other_install(self):
        exe=prepare(self)
        registry=WindowsRegistry()
        name="com.rapido.test."+uuid.uuid4().hex
        specs=manifests(exe,name=name)
        try:
            register(exe,registry=registry,name=name)
            for key,path,value in specs.values():
                for location in registry.locations(key):
                    self.assertEqual(registry.read(location),str(path))
            key,path,_=specs["edge"]
            other=str(path.with_name("other-install.json"))
            registry.write(registry.locations(key)[0],other)
            corrupted = specs["chrome"][1]
            corrupted.write_text("null", encoding="utf-8")
            unregister(exe,registry=registry,name=name)
            self.assertEqual(registry.read(registry.locations(key)[0]),other)
            self.assertEqual(corrupted.read_text(encoding="utf-8"), "null")
            for browser in ("chrome", "firefox"):
                for location in registry.locations(specs[browser][0]):
                    self.assertIsNone(registry.read(location))
            self.assertFalse(specs["firefox"][1].exists())
        finally:
            import winreg
            for key,_,_ in specs.values():
                for location in registry.locations(key):
                    registry.remove(location)
                    try:
                        winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER,key,location[1],0)
                    except FileNotFoundError:
                        pass

if __name__=="__main__":
    unittest.main()
