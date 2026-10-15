"""Payload review must reflect actual archives without treating matches as trust."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tempfile
from types import SimpleNamespace
import unittest
import zipfile

from scripts.collect_payload_evidence import collect, module_name, safe_relative
from tests.test_license_evidence import Distribution


class Archive:
    def __init__(self, path):
        self.toc = {'PYZ.pyz': (0, 0, 0, 0, 'z'),
                    'vendor\\native.dll': (0, 0, 3, 0, 'b')}

    def open_embedded_archive(self, name):
        assert name == 'PYZ.pyz'
        return SimpleNamespace(toc={'demo': (), 'demo.api': (), 'unknown': ()})

    def extract(self, name):
        assert name == 'vendor\\native.dll'
        return b'DLL'


class PayloadEvidenceTests(unittest.TestCase):
    def fixture(self, root):
        bundle = root / 'bundle'
        bundle.mkdir()
        (bundle / 'Rapido.exe').write_bytes(b'desktop fixture')
        (bundle / 'RapidoNativeHost.exe').write_bytes(b'host fixture')
        (bundle / '_internal').mkdir()
        (bundle / '_internal/native.dll').write_bytes(b'DLL')
        (bundle / '_internal/unknown.dll').write_bytes(b'???')
        (bundle / 'third-party').mkdir()
        (bundle / 'third-party/ignore.json').write_text('EVIDENCE_NOT_PAYLOAD')
        packages = root / 'site-packages'
        (packages / 'demo').mkdir(parents=True)
        (packages / 'demo/native.dll').write_bytes(b'DLL')
        dist = Distribution(packages, 'Demo', ['demo/__init__.py', 'demo/api.py', 'demo/native.dll'])
        return bundle, dist

    def test_exact_native_hash_candidates_and_record_module_candidates_remain_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, dist = self.fixture(root)
            report = collect(bundle, distributions=[dist], archive_factory=Archive)
            files = {p['path']: p for p in report['files']}
            self.assertEqual(len(files), 4)
            self.assertEqual(files['_internal/native.dll']['native_distribution_candidates_by_sha256'], ['Demo'])
            self.assertEqual(files['_internal/unknown.dll']['native_distribution_candidates_by_sha256'], [])
            self.assertEqual(files['Rapido.exe']['sha256'], hashlib.sha256(b'desktop fixture').hexdigest())
            for archive in report['archives']:
                modules = {m['name']: m['distribution_candidates_by_record_name'] for m in archive['modules']}
                self.assertEqual(modules, {'demo': ['Demo'], 'demo.api': ['Demo'], 'unknown': []})
                native = archive['embedded_native'][0]
                self.assertEqual(native['path'], 'vendor/native.dll')
                self.assertEqual(native['native_distribution_candidates_by_sha256'], ['Demo'])
            serialized = json.dumps(report)
            self.assertNotIn(str(root), serialized)
            self.assertNotIn('ignore.json', serialized)
            self.assertFalse(report['compliance_verified'])
            self.assertFalse(report['runtime_integrity_policy'])
            # Same filename and size must not establish ownership after a change.
            (dist.root / 'demo/native.dll').write_bytes(b'NEW')
            changed = collect(bundle, distributions=[dist], archive_factory=Archive)
            self.assertTrue(all(not n['native_distribution_candidates_by_sha256']
                                for a in changed['archives'] for n in a['embedded_native']))

    def test_both_standard_library_archives_are_listed_without_loading_code(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, dist = self.fixture(Path(directory))
            data = io.BytesIO()
            with zipfile.ZipFile(data, 'w') as z:
                z.writestr('encodings/__init__.pyc', b'NOT_EXECUTABLE')
            (bundle / '_internal/base_library.zip').write_bytes(data.getvalue())
            class WithStandardLibrary(Archive):
                def __init__(self, path):
                    super().__init__(path)
                    self.toc['base_library.zip'] = (0, 0, len(data.getvalue()), 0, 'b')
                def extract(self, name):
                    return data.getvalue() if name == 'base_library.zip' else super().extract(name)
            report = collect(bundle, distributions=[dist], archive_factory=WithStandardLibrary)
            stdlibs = [a for a in report['archives'] if a['format'] == 'stdlib-zip']
            self.assertEqual(len(stdlibs), 3)  # On disk and in each fixture executable.
            self.assertTrue(all(a['modules'][0]['name'] == 'encodings' for a in stdlibs))

    def test_ambiguous_candidates_remain_visible_and_external_records_are_not_used(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, dist = self.fixture(root)
            other = Distribution(dist.root, 'Other', ['demo/api.py', '../secret.dll'])
            report = collect(bundle, distributions=[dist, other], archive_factory=Archive)
            api = next(m for m in report['archives'][0]['modules'] if m['name'] == 'demo.api')
            self.assertEqual(api['distribution_candidates_by_record_name'], ['Demo', 'Other'])
            self.assertIn('external-or-unsafe-record', report['distributions'][1]['problems'])

    def test_missing_builds_and_unreadable_archives_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, dist = self.fixture(root)
            class NoPyz(Archive):
                def __init__(self, path): self.toc = {}
            with self.assertRaises(ValueError):
                collect(bundle, distributions=[], archive_factory=NoPyz)
            class Truncated(Archive):
                def extract(self, name): return b''
            with self.assertRaises(ValueError):
                collect(bundle, distributions=[], archive_factory=Truncated)
            (bundle / 'RapidoNativeHost.exe').unlink()
            with self.assertRaises(ValueError):
                collect(bundle, distributions=[], archive_factory=Archive)

    def test_external_payload_links_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, _ = self.fixture(root)
            try:
                (bundle / 'external.txt').symlink_to(root / 'secret')
            except OSError:
                self.skipTest('Runner does not permit creating a symlink')
            with self.assertRaises(ValueError):
                collect(bundle, distributions=[], archive_factory=Archive)

    def test_metadata_paths_and_extension_module_names(self):
        for path in ('../secret.py', 'C:\\secret.py', '/secret.py'):
            with self.assertRaises(ValueError): safe_relative(path)
        self.assertEqual(module_name('demo/native.cp312-win_amd64.pyd'), 'demo.native')
        self.assertEqual(module_name('demo/__init__.py'), 'demo')
        self.assertIsNone(module_name('demo.dist-info/METADATA'))
        self.assertIsNone(module_name('demo/__pycache__/mod.cpython-312.pyc'))
