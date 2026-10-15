import unittest

from scripts.check_build_runtime import verify_runtime


class BuildRuntimeTests(unittest.TestCase):
    def test_real_openssl3_version_strings_and_newer_patch(self):
        for value in ('OpenSSL 3.5.9 29 Sep 2026', 'OpenSSL 3.5.10 1 Oct 2026', 'OpenSSL 3.6.0 1 Oct 2026'):
            with self.subTest(value=value):
                verify_runtime((3, 13, 16), value)

    def test_older_openssl_series_and_patch_fail(self):
        for value in ('OpenSSL 3.0.16 11 Feb 2025', 'OpenSSL 3.4.99 1 Oct 2026', 'OpenSSL 3.5.8 1 Sep 2026'):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'OpenSSL'):
                verify_runtime((3, 13, 16), value)

    def test_different_unknown_or_prerelease_implementations_fail(self):
        for value in ('LibreSSL 4.0.0', 'OpenSSL 3.5.9-dev 29 Sep 2026', 'unknown', ''):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'OpenSSL'):
                verify_runtime((3, 13, 16), value)

    def test_unreviewed_python_version_fails_even_with_new_openssl(self):
        for version in ((3, 12, 10), (3, 13, 15), (3, 14, 8)):
            with self.subTest(version=version), self.assertRaisesRegex(RuntimeError, 'Python'):
                verify_runtime(version, 'OpenSSL 3.5.9 29 Sep 2026')
