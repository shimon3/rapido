"""Trust failure, exact signer and held-file regressions for the #26 primitive."""
import ctypes
import hashlib
import json
import os
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
        return 123

    def CloseHandle(self, handle):
        self.events.append(("handle-close", handle))
        return 1

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
