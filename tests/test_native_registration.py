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
    exe=Path(temp.name)/"RapidoNativeHost.exe"
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
            unregister(exe,registry=registry,name=name)
            self.assertEqual(registry.read(registry.locations(key)[0]),other)
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
