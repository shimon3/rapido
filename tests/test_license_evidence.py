"""License evidence must be reproducible, honest and confined to package roots."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
import unittest

from scripts.collect_license_evidence import collect


class Distribution:
    def __init__(self, root, name, files):
        self.root = root
        self.metadata = {"Name": name, "License-Expression": "MIT"}
        self.version = "1.2.3"
        self.files = [PurePosixPath(name) for name in files]

    def locate_file(self, relative):
        return self.root / relative


class LicenseEvidenceTests(unittest.TestCase):
    def test_copies_original_text_records_hashes_and_flags_missing_license(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            packages = root / "site-packages"
            license_file = packages / "demo.dist-info/licenses/LICENSE.txt"
            license_file.parent.mkdir(parents=True)
            text = b"Test attribution\r\nLicense terms\r\n"
            license_file.write_bytes(text)
            python_license = root / "python-license.txt"
            python_license.write_text("Python fixture notice")
            first = Distribution(packages, "Demo", ["demo.dist-info/licenses/LICENSE.txt"])
            missing = Distribution(packages, "NoText", [])
            output = root / "evidence"
            report = collect(output, distributions=[missing, first], python_license=python_license)
            self.assertEqual(report["scope"], "installed-build-environment")
            self.assertFalse(report["compliance_verified"])
            item = report["packages"][0]
            evidence = item["files"][0]
            self.assertEqual((output / evidence["path"]).read_bytes(), text)
            self.assertEqual(evidence["sha256"], hashlib.sha256(text).hexdigest())
            self.assertIn("license-text-not-collected", report["packages"][1]["problems"])
            self.assertTrue(report["python"]["license_collected"])
            self.assertEqual(json.loads((output / "inventory.json").read_text()), report)
            self.assertNotIn(str(root), (output / "inventory.json").read_text())

    def test_escaping_license_metadata_cannot_copy_an_external_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            packages = root / "site-packages"
            packages.mkdir()
            (root / "LICENSE-secret.txt").write_text("EXTERNAL_CONTENT_MUST_NOT_BE_EXPORTED")
            dist = Distribution(packages, "Unsafe", ["../LICENSE-secret.txt", "C:/LICENSE.txt"])
            class ResolvedOutside(Distribution):
                def locate_file(self, relative):
                    return self.root if not str(relative) else root / "LICENSE-secret.txt"
            redirected = ResolvedOutside(packages, "Redirected", ["LICENSE.txt"])
            output = root / "evidence"
            report = collect(output, distributions=[dist, redirected], python_license=root / "missing")
            self.assertFalse(report["python"]["license_collected"])
            items = {item["name"]: item for item in report["packages"]}
            self.assertFalse(items["Unsafe"]["files"])
            self.assertFalse(items["Redirected"]["files"])
            self.assertIn("unsafe-license-path", items["Unsafe"]["problems"])
            self.assertIn("unreadable-or-external-license-file", items["Redirected"]["problems"])
            self.assertNotIn("EXTERNAL_CONTENT", (output / "inventory.json").read_text())
            self.assertFalse((output / "packages").exists())

    def test_existing_output_and_ambiguous_packages_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / "evidence"
            output.mkdir()
            with self.assertRaises(FileExistsError):
                collect(output, distributions=[])
            a = Distribution(root, "Demo-pkg", [])
            b = Distribution(root, "Demo_pkg", [])
            with self.assertRaises(ValueError):
                collect(root / "duplicate", distributions=[a, b], python_license=root / "missing")
