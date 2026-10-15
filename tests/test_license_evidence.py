"""License evidence must be reproducible, honest and confined to package roots."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
import unittest
from unittest.mock import patch

from scripts import collect_license_evidence as evidence
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
    def test_webview_sdk_requires_every_binary_and_both_original_text_identities(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            carrier = root / "pywebview.dist-info/LICENSE"
            carrier.parent.mkdir()
            carrier.write_bytes(b"Carrier license")
            files = {"webview/lib/Core.dll": b"core fixture", "webview/lib/Loader.dll": b"loader fixture"}
            expected = {}
            for relative, data in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                expected[relative] = hashlib.sha256(data).hexdigest()
            dist = Distribution(root, "pywebview", ["pywebview.dist-info/LICENSE"])
            dist.version = "6.2.1"
            with patch.object(evidence, "WEBVIEW2_SDK_FILES", expected):
                report = collect(root / "accepted", distributions=[dist], python_license=root / "missing")
                item = report["packages"][0]
                self.assertEqual(len(item["files"]), 3)
                self.assertEqual(len(item["supplemental_components"][0]["matched_installed_files"]), 2)
                self.assertFalse(item["supplemental_components"][0]["complete_legal_review"])
                self.assertEqual({f["sha256"] for f in item["files"] if f.get("component")},
                                 set(evidence.WEBVIEW2_SDK_TEXTS.values()))
                (root / "webview/lib/Loader.dll").write_bytes(b"different loader")
                rejected = collect(root / "bad-binary", distributions=[dist], python_license=root / "missing")
                self.assertIn("webview2-sdk-notice-identity-unverified", rejected["packages"][0]["problems"])
                self.assertEqual(len(rejected["packages"][0]["files"]), 1)
                (root / "webview/lib/Loader.dll").write_bytes(files["webview/lib/Loader.dll"])
                with patch.dict(evidence.WEBVIEW2_SDK_TEXTS, {"NOTICE.txt": "0" * 64}):
                    rejected = collect(root / "bad-text", distributions=[dist], python_license=root / "missing")
                self.assertEqual(len(rejected["packages"][0]["files"]), 1)
                self.assertIn("webview2-sdk-notice-identity-unverified", rejected["packages"][0]["problems"])
                dist.version = "6.3.0"
                rejected = collect(root / "unreviewed-version", distributions=[dist], python_license=root / "missing")
                self.assertEqual(len(rejected["packages"][0]["files"]), 1)
                self.assertIn("webview2-sdk-notice-identity-unverified", rejected["packages"][0]["problems"])

    def test_copyleft_source_notices_require_exact_installed_source_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            module = root / "certifi/core.py"
            module.parent.mkdir()
            module.write_bytes(b"# synthetic module\r\n")
            dist = Distribution(root, "certifi", [])
            dist.version = "2026.7.22"
            reviewed = dict(evidence.SOURCE_NOTICES[("certifi", "2026.7.22")])
            reviewed["files"] = {"certifi/core.py": hashlib.sha256(b"# synthetic module\n").hexdigest()}
            with patch.dict(evidence.SOURCE_NOTICES, {("certifi", "2026.7.22"): reviewed}):
                report = collect(root / "accepted", distributions=[dist], python_license=root / "missing")
                item = report["packages"][0]
                notices = {f["path"].rsplit("/", 1)[1]: f for f in item["files"] if f.get("kind") == "source-notice"}
                self.assertEqual(set(notices), {"SOURCE.md", "MPL-2.0.txt"})
                self.assertEqual(notices["MPL-2.0.txt"]["sha256"], reviewed["texts"]["MPL-2.0.txt"])
                self.assertIn(b"5379b709be8a8595803a7bd907f87e302fc6ae1d",
                              (root / "accepted" / notices["SOURCE.md"]["path"]).read_bytes())
                self.assertFalse(item["source_notice"]["complete_legal_review"])
                self.assertNotIn("source-notice-identity-unverified", item["problems"])
                module.write_bytes(b"# modified module\n")
                rejected = collect(root / "modified", distributions=[dist], python_license=root / "missing")
                self.assertIn("source-notice-identity-unverified", rejected["packages"][0]["problems"])
                self.assertFalse([f for f in rejected["packages"][0]["files"] if f.get("kind")])
            dist.version = "2027.1.1"
            rejected = collect(root / "unreviewed", distributions=[dist], python_license=root / "missing")
            self.assertIn("source-notice-identity-unverified", rejected["packages"][0]["problems"])
            other = Distribution(root, "demo", [])
            unaffected = collect(root / "other", distributions=[other], python_license=root / "missing")
            self.assertNotIn("source-notice-identity-unverified", unaffected["packages"][0]["problems"])

    def test_binary_notice_hashes_raw_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            native = root / "PIL/_fixture.pyd"
            native.parent.mkdir()
            data = b"MZ\r\nnative fixture"
            native.write_bytes(data)
            dist = Distribution(root, "Pillow", [])
            dist.version = "12.3.0"
            reviewed = dict(evidence.SOURCE_NOTICES[("pillow", "12.3.0")])
            reviewed["files"] = {"PIL/_fixture.pyd": hashlib.sha256(data).hexdigest()}
            with patch.dict(evidence.SOURCE_NOTICES, {("pillow", "12.3.0"): reviewed}):
                item = collect(root / "raw", distributions=[dist], python_license=root / "missing")["packages"][0]
                self.assertEqual([f["path"] for f in item["files"] if f.get("kind")],
                                 ["packages/pillow/pillow-12.3.0/NOTICE.md"])
                reviewed["files"] = {"PIL/_fixture.pyd": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()}
                item = collect(root / "normalized", distributions=[dist], python_license=root / "missing")["packages"][0]
                self.assertIn("source-notice-identity-unverified", item["problems"])

    def test_crate_texts_must_match_names_and_index_exactly(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            native = root / "pydantic_core/_native.pyd"
            native.parent.mkdir()
            native.write_bytes(b"native fixture")
            licenses = root / "packaging/licenses"
            texts = licenses / "fixture/texts"
            texts.mkdir(parents=True)
            body = b"MIT fixture text\n"
            digest = hashlib.sha256(body).hexdigest()
            (texts / f"{digest}.txt").write_bytes(body)
            (licenses / "fixture/NOTICE.md").write_bytes(b"notice\n")
            index = {"crates": [{"name": "demo", "version": "1.0.0", "license_files": {"LICENSE": digest}}]}
            (licenses / "fixture/crates.json").write_text(json.dumps(index))
            dist = Distribution(root, "pydantic_core", [])
            dist.version = "2.50.1"
            reviewed = dict(evidence.SOURCE_NOTICES[("pydantic-core", "2.50.1")], folder="fixture",
                            files={"pydantic_core/_native.pyd": hashlib.sha256(b"native fixture").hexdigest()})
            # The collector reads notices relative to its own location.
            (root / "scripts").mkdir()
            with patch.dict(evidence.SOURCE_NOTICES, {("pydantic-core", "2.50.1"): reviewed}), \
                 patch.object(evidence, "__file__", str(root / "scripts/x.py")):
                item = collect(root / "ok", distributions=[dist], python_license=root / "missing")["packages"][0]
                paths = {f["path"] for f in item["files"] if f.get("kind")}
                self.assertIn(f"packages/pydantic-core/fixture/texts/{digest}.txt", paths)
                self.assertNotIn("source-notice-identity-unverified", item["problems"])
                (texts / "extra.txt").write_bytes(b"unexpected\n")
                item = collect(root / "extra", distributions=[dist], python_license=root / "missing")["packages"][0]
                self.assertIn("source-notice-identity-unverified", item["problems"])
                (texts / "extra.txt").unlink()
                (texts / f"{digest}.txt").write_bytes(b"tampered\n")
                item = collect(root / "tampered", distributions=[dist], python_license=root / "missing")["packages"][0]
                self.assertIn("source-notice-identity-unverified", item["problems"])
                self.assertFalse([f for f in item["files"] if f.get("kind")])

    def test_python_incorporated_notices_require_reviewed_version_and_texts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(evidence.platform, "python_version", return_value="3.13.16"):
                report = collect(root / "accepted", distributions=[], python_license=root / "missing")
            notices = report["python"]["incorporated_notices"]
            self.assertTrue(notices["collected"])
            self.assertFalse(notices["complete_legal_review"])
            names = {f["path"].rsplit("/", 1)[1]: f for f in notices["files"]}
            self.assertEqual(set(names), {"NOTICE.md", "license.rst", "HACL-LICENSE.txt"})
            self.assertIn(b"cbc944f4bc59639a444dd971c737788ba2283a91",
                          (root / "accepted" / names["NOTICE.md"]["path"]).read_bytes())
            with patch.object(evidence.platform, "python_version", return_value="3.13.17"):
                other = collect(root / "other", distributions=[], python_license=root / "missing")
            self.assertEqual(other["python"]["incorporated_notices"]["problem"],
                             "python-incorporated-notices-unreviewed-version")
            self.assertFalse((root / "other/python").exists())
            with patch.object(evidence.platform, "python_version", return_value="3.13.16"), \
                 patch.dict(evidence.PYTHON_NOTICE_TEXTS, {"license.rst": "0" * 64}):
                bad = collect(root / "bad", distributions=[], python_license=root / "missing")
            self.assertFalse(bad["python"]["incorporated_notices"]["collected"])
            self.assertFalse((root / "bad/python").exists())

    def test_reviewed_source_notice_texts_are_present_and_reference_exact_upstream(self):
        base = Path(evidence.__file__).resolve().parents[1] / "packaging/licenses"
        crates = json.loads((base / "pydantic_core-2.50.1/crates.json").read_text(encoding="utf-8"))
        self.assertEqual(len(crates["crates"]), 99)
        referenced = {d for c in crates["crates"] for d in c["license_files"].values()}
        stored = {p.stem for p in (base / "pydantic_core-2.50.1/texts").iterdir()}
        self.assertEqual(referenced, stored)
        expected = {"pystray": ("SOURCE.md", b"1907f8681d6d421517c63d94f425f9cdd74d0034"),
                    "certifi": ("SOURCE.md", b"5379b709be8a8595803a7bd907f87e302fc6ae1d"),
                    "pillow": ("NOTICE.md", b"1cca606cd25738df4ed873d5ad46bbdb3d83b5cbca291f6b4ff13a4df6b0bbe8"),
                    "pydantic-core": ("NOTICE.md", b"ac24753c2ed315f8dc22d6470fa868970e3705a0888d879704e872d53f21452d"),
                    "cffi": ("NOTICE.md", b"fd33e7700f0ebafe6f30bd5053f13327221b77a2"),
                    "pywebview": ("WEBBROWSERINTEROP.md", b"2fc63cd6a92b8630c14f6d4dd73f9691591f8eea")}
        for (name, _version), reviewed in evidence.SOURCE_NOTICES.items():
            for text, digest in reviewed["texts"].items():
                data = (base / reviewed["folder"] / text).read_bytes().replace(b"\r\n", b"\n")
                if digest is not None:
                    self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
            notice, reference = expected[name]
            self.assertIn(reference, (base / reviewed["folder"] / notice).read_bytes())
        self.assertIn("FreeType Project".encode(), (base / "pillow-12.3.0/NOTICE.md").read_bytes())
        libffi = (base / "cffi-2.1.1/LIBFFI-NOTICES.txt").read_bytes()
        self.assertEqual(libffi.count(b"===== src/c/libffi_x86_x64/"), 6)
        self.assertIn(b"Red Hat, Inc.", libffi)

    def test_supplement_requires_exact_module_identity_and_keeps_conflict_visible(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            module = root / "proxy_tools/__init__.py"
            module.parent.mkdir()
            module.write_bytes(b"# synthetic module\n")
            dist = Distribution(root, "proxy_tools", [])
            dist.version = "0.1.0"
            dist.metadata["License"] = "MIT"
            dist.metadata.pop("License-Expression")
            rejected = collect(root / "rejected", distributions=[dist], python_license=root / "missing")
            self.assertFalse(rejected["packages"][0]["files"])
            self.assertIn("supplemental-license-identity-unverified", rejected["packages"][0]["problems"])
            digest = hashlib.sha256(module.read_bytes()).hexdigest()
            with patch.object(evidence, "PROXY_TOOLS_MODULE_SHA256", digest):
                report = collect(root / "accepted", distributions=[dist], python_license=root / "missing")
            item = report["packages"][0]
            self.assertEqual(len(item["files"]), 1)
            self.assertEqual(item["files"][0]["sha256"], evidence.PROXY_TOOLS_LICENSE_SHA256)
            self.assertIn("upstream-BSD-text-supplemented-metadata-MIT-review-required", item["problems"])
            self.assertFalse(report["compliance_verified"])

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
