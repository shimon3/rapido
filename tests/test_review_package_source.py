"""Tests for the read-only source-review inventory; no network required."""
import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile

from scripts.review_package_source import inventory


class FakeDist:
    version = "2026.10.23"

    def __init__(self, directory, names):
        self.directory = Path(directory)
        self.files = [Path(name) for name in names]

    def locate_file(self, path):
        return self.directory / path


class SourceReviewTests(unittest.TestCase):
    def test_refuses_unapproved_name(self):
        with self.assertRaises(ValueError):
            inventory("random-unapproved-package")

    def test_reports_sha_without_local_absolute_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "certifi"
            path.mkdir()
            (path / "core.py").write_bytes(b"a\r\nb\r\n")
            dist = FakeDist(folder, ["certifi/core.py", "not-in-scope.txt"])
            with patch("scripts.review_package_source.metadata.distribution", return_value=dist):
                result = inventory("certifi")
            import hashlib
            self.assertEqual(result["files"], [{
                "path": "certifi/core.py",
                "sha256": hashlib.sha256(b"a\nb\n").hexdigest(),
                "mode": "lf-normalized",
            }])
            self.assertEqual(result["status"], "UNREVIEWED_CANDIDATE_ONLY")

    def test_refuses_symlink_member(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "certifi").mkdir()
            (root / "regular").write_bytes(b"x")
            link = root / "certifi" / "core.py"
            try:
                link.symlink_to(root / "regular")
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks not available")
            with patch("scripts.review_package_source.metadata.distribution",
                       return_value=FakeDist(folder, ["certifi/core.py"])):
                with self.assertRaises(ValueError):
                    inventory("certifi")


if __name__ == "__main__":
    unittest.main()
