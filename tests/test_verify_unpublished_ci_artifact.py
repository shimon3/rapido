"""Synthetic unpublished-artifact integrity scenarios; no installation or execution."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.verify_unpublished_ci_artifact import verify

RUN = 123456789
COMMIT = "a" * 40


class UnpublishedArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.installer = self.root / "Rapido-Setup-1.3.0-beta.2.exe"
        self.portable = self.root / "Rapido-1.3.0-beta.2-portable.zip"
        self.installer.write_bytes(b"sample-installer")
        with zipfile.ZipFile(self.portable, "w") as z:
            z.writestr("Rapido/Rapido.exe", b"desktop")
            z.writestr("Rapido/RapidoNativeHost.exe", b"native")
        for name in ("signing-plan.json", "signing-rehearsal.json"):
            (self.root / name).write_text("{}", encoding="utf-8")
        self.write_provenance()
        self.write_hashes()

    def write_provenance(self, **changes):
        info = dict(official_release=False, production_signed=False,
                    workflow_run_id=str(RUN), head_commit=COMMIT)
        info.update(changes)
        (self.root / "ci-artifact-provenance.json").write_text(json.dumps(info), encoding="utf-8")

    def write_hashes(self):
        def digest(data):
            return hashlib.sha256(data).hexdigest()
        lines = [
            f"{digest(self.installer.read_bytes())}  {self.installer.name}",
            f"{digest(self.portable.read_bytes())}  {self.portable.name}",
            f"{digest(b'desktop')}  Rapido.exe",
            f"{digest(b'native')}  RapidoNativeHost.exe",
        ]
        (self.root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="ascii")

    def test_valid_fixture_is_only_private_unsigned_integrity_evidence(self):
        result = verify(self.root, RUN, COMMIT)
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["production_signed"])
        self.assertEqual(len(result["verified_sha256_entries"]), 4)

    def test_tampered_installer_rejected(self):
        self.installer.write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "Distributable SHA-256 mismatch"):
            verify(self.root, RUN, COMMIT)

    def test_portable_binary_mismatch_rejected_even_if_zip_sum_updated(self):
        with zipfile.ZipFile(self.portable, "w") as z:
            z.writestr("Rapido/Rapido.exe", b"modified desktop")
            z.writestr("Rapido/RapidoNativeHost.exe", b"native")
        self.write_hashes()
        # Tampered zipped binary must differ from independently recorded source binary hash.
        text = (self.root / "SHA256SUMS.txt").read_text()
        text = text.replace(hashlib.sha256(b"desktop").hexdigest(),
                            hashlib.sha256(b"original-desktop").hexdigest())
        (self.root / "SHA256SUMS.txt").write_text(text)
        with self.assertRaisesRegex(ValueError, "Portable executable SHA-256 mismatch"):
            verify(self.root, RUN, COMMIT)

    def test_other_run_or_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Wrong workflow run"):
            verify(self.root, RUN + 1, COMMIT)
        with self.assertRaisesRegex(ValueError, "Wrong tested checkout commit"):
            verify(self.root, RUN, "b" * 40)

    def test_claim_of_official_release_rejected(self):
        self.write_provenance(official_release=True)
        with self.assertRaisesRegex(ValueError, "Not an unpublished"):
            verify(self.root, RUN, COMMIT)

    def test_unknown_extra_file_rejected(self):
        (self.root / "unexpected.exe").write_bytes(b"x")
        with self.assertRaisesRegex(ValueError, "Unexpected missing or extra"):
            verify(self.root, RUN, COMMIT)

    def test_zip_traversal_rejected(self):
        with zipfile.ZipFile(self.portable, "w") as z:
            z.writestr("Rapido/Rapido.exe", b"desktop")
            z.writestr("Rapido/RapidoNativeHost.exe", b"native")
            z.writestr("../bad.txt", b"x")
        self.write_hashes()
        with self.assertRaisesRegex(ValueError, "Unsafe or duplicate"):
            verify(self.root, RUN, COMMIT)


if __name__ == "__main__":
    unittest.main()
