"""Exercise real urllib dispatch with simulated HTTP responses and no sockets."""
import io
import http.client
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
import native_host


class LoopbackPolicyTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        calls = self.calls
        class FakeSocket:
            def __init__(self, wire):
                self.wire = wire
            def makefile(self, *args, **kwargs):
                return io.BytesIO(self.wire)
        class Connection(http.client.HTTPConnection):
            sock = None
            def __init__(self, host, **kwargs):
                self.host = host
                self.path = ""
            def set_debuglevel(self, level):
                pass
            def request(self, method, path, body, headers, **kwargs):
                self.path = path
                calls.append((self.host, method, path, body))
            def getresponse(self):
                if self.path.startswith("/redirect/"):
                    code = self.path.rsplit("/", 1)[1]
                    wire = ("HTTP/1.1 "+code+" Redirect\r\nLocation: http://other.example/sink\r\nContent-Length: 0\r\n\r\n").encode()
                else:
                    body = b'{"id":"abcdef12"}'
                    wire = b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
                response = http.client.HTTPResponse(FakeSocket(wire))
                response.begin()
                return response
            def close(self):
                pass
        self.connection = patch("http.client.HTTPConnection", Connection)
        self.connection.start()
        self.addCleanup(self.connection.stop)

    def test_all_redirect_statuses_are_rejected_without_followup(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                req = urllib.request.Request("http://127.0.0.1:9614/redirect/"+str(status),
                                             data=b'{"url":"private"}', method="POST")
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    native_host._loopback_opener().open(req, timeout=2)
                self.assertEqual(caught.exception.code, status)
                caught.exception.close()
        self.assertEqual(len(self.calls), 5)
        self.assertTrue(all(host == "127.0.0.1:9614" for host, *_ in self.calls))

    def test_system_proxy_settings_are_not_read(self):
        with patch("urllib.request.getproxies", return_value={"http":"http://proxy.example:9999"}) as proxies:
            req = urllib.request.Request(native_host.LOCAL_CAPTURE_URL, data=b"{}", method="POST")
            with native_host._open_loopback(req, timeout=2) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b'{"id":"abcdef12"}')
            proxies.assert_not_called()
        self.assertEqual(self.calls, [("127.0.0.1:9614","POST","/api/capture",b"{}")])

    def test_public_helper_rejects_other_destinations_and_methods(self):
        for url, method in (("http://other.example/api/capture","POST"),
                            (native_host.LOCAL_CAPTURE_URL+"?token=x","POST"),
                            (native_host.LOCAL_CAPTURE_URL,"GET")):
            with patch("native_host._loopback_opener") as opener:
                with self.assertRaises(ValueError):
                    native_host._open_loopback(urllib.request.Request(url, method=method), timeout=2)
                opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
