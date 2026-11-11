"""Offline synthetic-wheel tests: no dependency download or internet access."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.verify_pydantic_core_wheel import WHEEL, MODULE, inspect_wheel


class PydanticWheelAuditTests(unittest.TestCase):
    def create_wheel(self, folder, *, missing=False, extra=None):
        path = Path(folder) / WHEEL
        with zipfile.ZipFile(path, "w") as z:
            if not missing:
                z.writestr(MODULE, b"binary\x00\r\nsource")
            z.writestr("pydantic_core/__init__.py", b"test")
            if extra:
                z.writestr(extra, b"unexpected")
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_expected_wheel_and_raw_binary_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            path, sha = self.create_wheel(folder)
            result = inspect_wheel(path, expected_sha256=sha)
            self.assertEqual(result["native_modules"][0]["sha256"],
                             hashlib.sha256(b"binary\x00\r\nsource").hexdigest())
            self.assertEqual(result["status"], "REVIEW_CANDIDATE_ONLY")
            self.assertEqual(result["rust_crate_license_review"], "REQUIRED_BEFORE_APPROVAL")

    def test_rejects_untrusted_archive_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            path, sha = self.create_wheel(folder)
            self.assertNotEqual(sha, "e5c801bdf3cc92274b8fc2c7023c8751e5ae81260c009ac558ff55ce712a2d45")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                inspect_wheel(path)

    def test_rejects_missing_binary(self):
        with tempfile.TemporaryDirectory() as folder:
            path, sha = self.create_wheel(folder, missing=True)
            with self.assertRaisesRegex(ValueError, "missing"):
                inspect_wheel(path, expected_sha256=sha)

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            path, sha = self.create_wheel(folder, extra="../evil.bin")
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                inspect_wheel(path, expected_sha256=sha)

    def test_rejects_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / WHEEL
            with zipfile.ZipFile(path, "w") as z:
                z.writestr(MODULE, b"abc")
                z.writestr(MODULE, b"xyz")
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "duplicate"):
                inspect_wheel(path, expected_sha256=sha)


if __name__ == "__main__":
    unittest.main()
