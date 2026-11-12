"""Hermetic checks for exact-wheel candidate verifier."""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from scripts.verify_certifi_wheel import EXPECTED_WHEEL, SOURCE_MEMBERS, verify_wheel


class WheelAuditTests(unittest.TestCase):
    def _archive(self, folder, *, missing=None, extra=None):
        path = Path(folder) / EXPECTED_WHEEL
        members = sorted(SOURCE_MEMBERS - ({missing} if missing else set()))
        with zipfile.ZipFile(path, "w") as z:
            for m in members:
                z.writestr(m, b"line1\r\nline2\r\n")
            if extra:
                z.writestr(extra, b"text")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        return path, sha

    def test_verifies_exact_archive_and_normalized_members(self):
        with TemporaryDirectory() as folder:
            path, digest = self._archive(folder)
            result = verify_wheel(path, expected_sha256=digest)
            self.assertEqual(len(result["source_files"]), 5)
            self.assertEqual(result["status"], "REVIEW_CANDIDATE_ONLY")
            expected = hashlib.sha256(b"line1\nline2\n").hexdigest()
            self.assertTrue(all(x["sha256_lf"] == expected
                                for x in result["source_files"]))

    def test_rejects_wrong_archive_digest(self):
        with TemporaryDirectory() as folder:
            path, _ = self._archive(folder)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                verify_wheel(path)

    def test_rejects_missing_source(self):
        with TemporaryDirectory() as folder:
            path, digest = self._archive(folder, missing="certifi/cacert.pem")
            with self.assertRaisesRegex(ValueError, "Missing"):
                verify_wheel(path, expected_sha256=digest)

    def test_rejects_path_traversal(self):
        with TemporaryDirectory() as folder:
            path, digest = self._archive(folder, extra="../escape.txt")
            with self.assertRaisesRegex(ValueError, "Invalid"):
                verify_wheel(path, expected_sha256=digest)

    def test_rejects_symlink_archive(self):
        with TemporaryDirectory() as folder:
            path, digest = self._archive(folder)
            link = Path(folder) / "linked.whl"
            try:
                link.symlink_to(path)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable")
            with self.assertRaises(ValueError):
                verify_wheel(link, expected_sha256=digest)


if __name__ == "__main__":
    unittest.main()
