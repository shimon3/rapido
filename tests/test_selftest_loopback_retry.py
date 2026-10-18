"""Self-test loopback denials must survive resets without weakening the guard."""
import unittest
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import desktop


class SelftestLoopbackRetryTests(unittest.TestCase):
    def setUp(self):
        self.request = urllib.request.Request(desktop.BASE_URL + "/api/settings")

    @staticmethod
    def http_error(code):
        return urllib.error.HTTPError(desktop.BASE_URL, code, "test", {}, None)

    def test_real_forbidden_response_passes_without_retry(self):
        with patch("desktop.urllib.request.urlopen", side_effect=self.http_error(403)) as opener, \
                patch("desktop.time.sleep") as sleep:
            self.assertTrue(desktop.forbidden_response(self.request, timeout=2))
        opener.assert_called_once_with(self.request, timeout=2)
        sleep.assert_not_called()

    def test_success_or_non_forbidden_response_fails(self):
        response = MagicMock()
        response.__enter__.return_value = response
        with patch("desktop.urllib.request.urlopen", return_value=response):
            self.assertFalse(desktop.forbidden_response(self.request, timeout=2))
        with patch("desktop.urllib.request.urlopen", side_effect=self.http_error(401)):
            self.assertFalse(desktop.forbidden_response(self.request, timeout=2))

    def test_transient_abort_retries_until_real_403(self):
        with patch("desktop.urllib.request.urlopen",
                   side_effect=[ConnectionAbortedError(10053, "aborted"), self.http_error(403)]) as opener, \
                patch("desktop.time.sleep") as sleep:
            self.assertTrue(desktop.forbidden_response(self.request, timeout=2))
        self.assertEqual(opener.call_count, 2)
        sleep.assert_called_once_with(.1)

    def test_persistent_transport_failure_never_counts_as_denial(self):
        with patch("desktop.urllib.request.urlopen", side_effect=TimeoutError("timeout")) as opener, \
                patch("desktop.time.sleep") as sleep:
            self.assertFalse(desktop.forbidden_response(self.request, timeout=2))
        self.assertEqual(opener.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_attempt_count_must_be_positive(self):
        with self.assertRaises(ValueError):
            desktop.forbidden_response(self.request, timeout=2, attempts=0)


if __name__ == "__main__":
    unittest.main()

