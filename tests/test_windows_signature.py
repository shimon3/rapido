"""Trust failure, exact signer and held-file regressions for the #26 primitive."""
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import windows_signature as signature

PATH = r"C:\Rapido\Rapido.exe"
PIN = hashlib.sha256(b"fixture DER").hexdigest()


class FakeAPI:
    def __init__(self, status=0, missing=None):
        self.status = status
        self.missing = missing
        self.events = []
        self.der = ctypes.create_string_buffer(b"fixture DER")
        self.context = signature._CertContext(1, ctypes.addressof(self.der), 11, None, None)
        self.cert = signature._ProviderCertPrefix(
            ctypes.sizeof(signature._ProviderCertPrefix), ctypes.pointer(self.context))

    def CreateFileW(self, path, access, share, security, disposition, flags, template):
        self.events.append(("open", path, access, share, disposition))
        self.open_flags = flags
        return 123

    def CloseHandle(self, handle):
        self.events.append(("handle-close", handle))
        return 1

    def GetFileType(self, handle):
        return 1

    def GetFileInformationByHandleEx(self, handle, info_class, raw, size):
        attributes = ctypes.cast(raw, ctypes.POINTER(signature._AttributeTagInfo)).contents
        attributes.FileAttributes = 0x80
        return 1

    def GetFinalPathNameByHandleW(self, handle, buffer, size, flags):
        buffer.value = "\\\\?\\" + PATH
        return len(buffer.value)

    def WinVerifyTrust(self, hwnd, action, raw):
        data = ctypes.cast(raw, ctypes.POINTER(signature._TrustData)).contents
        self.events.append(("trust", data.dwStateAction, data.dwProvFlags, data.dwUIChoice,
                            data.pFile.contents.hFile))
        data.hWVTStateData = 456
        return self.status if data.dwStateAction == 1 else 0

    def WTHelperProvDataFromStateData(self, state):
        self.events.append(("provider", state))
        return None if self.missing == "provider" else 11

    def WTHelperGetProvSignerFromChain(self, provider, index, countersigner, counterindex):
        self.events.append(("signer", index, countersigner))
        return None if self.missing == "signer" else 12

    def WTHelperGetProvCertFromChain(self, signer, index):
        return None if self.missing == "certificate" else ctypes.pointer(self.cert)


class SignaturePolicyTests(unittest.TestCase):
    def test_ambiguous_paths_and_pins_rejected_before_os_access(self):
        with patch.object(signature, "_libraries") as loader:
            for path in ("Rapido.exe", r"C:Rapido.exe", r"\Rapido.exe", r"\\host\file.exe",
                         r"\\?\C:\Rapido.exe", r"C:\a.exe:stream", "C:\\x\x00.exe",
                         r"C:\..\Rapido.exe", r"C:\a\..\Rapido.exe", r"C:\CON.txt",
                         r"C:\x \a.exe", r"C:\*.exe", "C:\\"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    with signature.verified_signed_file(path, certificate_sha256=[PIN]):
                        self.fail("invalid path admitted")
            for pins in (None, [], PIN, [""], ["ab"], [True], ["g" * 64]):
                with self.subTest(pins=pins), self.assertRaises(ValueError):
                    with signature.verified_signed_file(PATH, certificate_sha256=pins):
                        self.fail("invalid policy admitted")
            loader.assert_not_called()

    def test_no_windows_verification_on_other_platforms(self):
        with patch.object(signature.os, "name", "posix"), self.assertRaises(OSError):
            with signature.verified_signed_file(PATH, certificate_sha256=[PIN]):
                self.fail("non-Windows trusted")

    def test_trust_zero_and_exact_leaf_pin_required_and_file_held_through_use(self):
        api = FakeAPI()
        with patch.object(signature, "_libraries", return_value=(api, api)):
            with signature.verified_signed_file(PATH, certificate_sha256=[PIN.upper()]) as result:
                self.assertEqual(result.certificate_sha256, PIN)
                self.assertNotIn(("handle-close", 123), api.events)
                api.events.append(("use",))
        self.assertEqual(api.events[-2:], [("use",), ("handle-close", 123)])
        self.assertEqual(api.events[0], ("open", PATH, 0x80000000, 1, 3))
        self.assertEqual(api.open_flags, 0x00200080)
        self.assertEqual(api.events[1], ("trust", 1, 0x1080, 2, 123))
        self.assertIn(("signer", 0, False), api.events)
        self.assertIn(("trust", 2, 0x1080, 2, 123), api.events)

    def test_all_nonzero_statuses_deny_including_positive_warnings_and_cleanup(self):
        for status in (1, 0x800B0100, -2146762487, 0x80092013):
            api = FakeAPI(status=status)
            with self.subTest(status=status), patch.object(signature, "_libraries", return_value=(api, api)):
                with self.assertRaises(PermissionError):
                    with signature.verified_signed_file(PATH, certificate_sha256=[PIN]):
                        self.fail("nonzero trust result admitted")
            self.assertFalse(any(event[0] == "provider" for event in api.events))
            self.assertEqual(api.events[-1], ("handle-close", 123))
            self.assertIn(("trust", 2, 0x1080, 2, 123), api.events)

    def test_valid_signature_from_wrong_signer_is_denied(self):
        api = FakeAPI()
        with patch.object(signature, "_libraries", return_value=(api, api)), self.assertRaises(PermissionError):
            with signature.verified_signed_file(PATH, certificate_sha256=["0" * 64]):
                self.fail("wrong signer admitted")
        self.assertEqual(api.events[-1], ("handle-close", 123))

    def test_redirected_or_uninspectable_input_denied_before_trust(self):
        for failure in ("type", "attributes", "link", "directory", "path", "long", "redirect"):
            api = FakeAPI()
            original_attributes = api.GetFileInformationByHandleEx

            def attributes(handle, info_class, raw, size):
                original_attributes(handle, info_class, raw, size)
                info = ctypes.cast(raw, ctypes.POINTER(signature._AttributeTagInfo)).contents
                if failure == "link":
                    info.FileAttributes |= 0x400
                    info.ReparseTag = 0xA000000C
                elif failure == "directory":
                    info.FileAttributes |= 0x10
                return 0 if failure == "attributes" else 1

            def final_path(handle, buffer, size, flags):
                buffer.value = r"\\?\C:\Other\Rapido.exe" if failure == "redirect" else "\\\\?\\" + PATH
                return 0 if failure == "path" else size if failure == "long" else len(buffer.value)

            with self.subTest(failure=failure), \
                    patch.object(signature, "_libraries", return_value=(api, api)), \
                    patch.object(api, "GetFileType", return_value=2 if failure == "type" else 1), \
                    patch.object(api, "GetFileInformationByHandleEx", side_effect=attributes), \
                    patch.object(api, "GetFinalPathNameByHandleW", side_effect=final_path):
                with self.assertRaises(PermissionError):
                    with signature.verified_signed_file(PATH, certificate_sha256=[PIN]):
                        self.fail("redirected/uninspectable file admitted")
            self.assertFalse(any(event[0] == "trust" for event in api.events))
            self.assertEqual(api.events[-1], ("handle-close", 123))

    def test_path_change_during_trust_denies_admission_and_cleans_up(self):
        api = FakeAPI()
        original = api.GetFinalPathNameByHandleW
        calls = 0

        def final_path(handle, buffer, size, flags):
            nonlocal calls
            calls += 1
            if calls == 1:
                return original(handle, buffer, size, flags)
            buffer.value = r"\\?\C:\Changed\Rapido.exe"
            return len(buffer.value)

        with patch.object(signature, "_libraries", return_value=(api, api)), \
                patch.object(api, "GetFinalPathNameByHandleW", side_effect=final_path), \
                self.assertRaises(PermissionError):
            with signature.verified_signed_file(PATH, certificate_sha256=[PIN]):
                self.fail("changed path admitted")
        self.assertIn(("trust", 2, 0x1080, 2, 123), api.events)
        self.assertEqual(api.events[-1], ("handle-close", 123))

    def test_incomplete_provider_data_and_exceptions_deny_and_release_resources(self):
        for missing in ("provider", "signer", "certificate", "length", "encoding"):
            api = FakeAPI(missing=missing)
            if missing == "length":
                api.context.cbCertEncoded = 65537
            if missing == "encoding":
                api.context.pbCertEncoded = None
            with self.subTest(missing=missing), patch.object(signature, "_libraries", return_value=(api, api)):
                with self.assertRaises(PermissionError):
                    with signature.verified_signed_file(PATH, certificate_sha256=[PIN]):
                        self.fail("missing trust data admitted")
            self.assertEqual(api.events[-1], ("handle-close", 123))
            self.assertIn(("trust", 2, 0x1080, 2, 123), api.events)
        api = FakeAPI()
        with patch.object(signature, "_libraries", return_value=(api, api)), \
                patch.object(api, "WTHelperProvDataFromStateData", side_effect=OSError("fixture")):
            with self.assertRaises(OSError):
                with signature.verified_signed_file(PATH, certificate_sha256=[PIN]):
                    self.fail("OS error admitted")
        self.assertEqual(api.events[-1], ("handle-close", 123))
        self.assertIn(("trust", 2, 0x1080, 2, 123), api.events)

    def test_failed_open_never_calls_trust_and_consumer_exception_releases_file(self):
        api = FakeAPI()
        with patch.object(signature, "_libraries", return_value=(api, api)), \
                patch.object(api, "CreateFileW", return_value=ctypes.c_void_p(-1).value):
            with self.assertRaises(OSError):
                with signature.verified_signed_file(PATH, certificate_sha256=[PIN]):
                    self.fail("failed file open admitted")
        self.assertEqual(api.events, [])
        with patch.object(signature, "_libraries", return_value=(api, api)), self.assertRaises(RuntimeError):
            with signature.verified_signed_file(PATH, certificate_sha256=[PIN]):
                raise RuntimeError("consumer")
        self.assertEqual(api.events[-1], ("handle-close", 123))


@unittest.skipUnless(os.name == "nt", "Real Windows trust APIs")
class WindowsUnsignedTests(unittest.TestCase):
    def test_unsigned_file_rejected_without_signature_pin_bypass(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder).resolve() / "unsigned.ps1"
            path.write_text("# harmless unsigned fixture\n", encoding="utf-8")
            with self.assertRaises(PermissionError):
                with signature.verified_signed_file(path, certificate_sha256=["0" * 64]):
                    self.fail("unsigned file admitted")


@unittest.skipUnless(os.name == "nt" and os.environ.get("RAPIDO_SIGNATURE_FIXTURES"),
                     "Isolated signed fixtures require the GitHub-hosted Windows harness")
class WindowsSignedFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = Path(os.environ["RAPIDO_SIGNATURE_FIXTURES"])
        cls.pin = json.loads((cls.folder / "policy.json").read_text(encoding="utf-8-sig"))["pin"]

    def test_signed_pe_accepted_with_exact_pin_and_write_delete_locked(self):
        path = self.folder / "signed.exe"
        with signature.verified_signed_file(path, certificate_sha256=[self.pin]) as result:
            self.assertEqual(result.certificate_sha256, self.pin)
            with self.assertRaises(OSError):
                with path.open("r+b"):
                    self.fail("write open succeeded while file was held")
            with self.assertRaises(OSError):
                path.unlink()
        # The held handle must be released on exit.
        with path.open("r+b"):
            pass

    def test_trusted_different_publisher_and_tampered_pe_rejected(self):
        for name in ("other-signer.exe", "tampered.exe", "unsigned.exe"):
            with self.subTest(name=name), self.assertRaises(PermissionError):
                with signature.verified_signed_file(self.folder / name, certificate_sha256=[self.pin]):
                    self.fail("unauthorized image admitted")

    def test_other_process_cannot_replace_held_image_then_replacement_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=self.folder) as directory:
            path = Path(directory) / "Rapido.exe"
            replacement = Path(directory) / "replacement.exe"
            shutil.copyfile(self.folder / "signed.exe", path)
            shutil.copyfile(self.folder / "unsigned.exe", replacement)
            script = (
                "import os,sys\n"
                "try: os.replace(sys.argv[1],sys.argv[2])\n"
                "except OSError as error:\n"
                " print(error.winerror)\n"
                " sys.exit(0 if error.winerror == 32 else 2)\n"
                "sys.exit(3)\n"
            )
            with signature.verified_signed_file(path, certificate_sha256=[self.pin]):
                result = subprocess.run([sys.executable, "-c", script, str(replacement), str(path)],
                                        capture_output=True, text=True, timeout=10,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout.strip(), "32")
            os.replace(replacement, path)
            with self.assertRaises(PermissionError):
                with signature.verified_signed_file(path, certificate_sha256=[self.pin]):
                    self.fail("replacement between verifications admitted")

    def test_actual_junction_alias_to_valid_signed_file_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=self.folder) as directory:
            alias = Path(directory) / "junction"
            subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(alias), str(self.folder)],
                           capture_output=True, text=True, check=True, timeout=10)
            try:
                self.assertTrue(alias.is_junction())
                with self.assertRaises(PermissionError):
                    with signature.verified_signed_file(alias / "signed.exe", certificate_sha256=[self.pin]):
                        self.fail("junction alias admitted")
            finally:
                alias.rmdir()

    def test_actual_leaf_symlink_to_valid_signed_file_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=self.folder) as directory:
            alias = Path(directory) / "linked.exe"
            try:
                alias.symlink_to(self.folder / "signed.exe")
            except OSError as error:
                if getattr(error, "winerror", None) == 1314:
                    self.skipTest("Runner lacks symbolic-link privilege")
                raise
            with self.assertRaises(PermissionError):
                with signature.verified_signed_file(alias, certificate_sha256=[self.pin]):
                    self.fail("leaf symlink admitted")
