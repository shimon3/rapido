"""Native public capture security regression tests. S2 auth is NOT implemented."""
from unittest.mock import patch
import io
import json

from native_host import handle_message


def test_rejects_invalid_capture_before_http():
    bad = [
        {"type": "capture_public", "url": "file:///tmp/x", "referrer": None, "filename": "x"},
        {"type": "capture_public", "url": "http://user:pass@example.com/x", "referrer": None, "filename": "x"},
        {"type": "capture_public", "url": "https://example.org/a", "referrer": None, "filename": "../evil"},
        {"type": "capture_public", "url": "https://example.org/a", "referrer": None, "filename": "ok", "cookie": "secret"},
        {"type": "capture_public", "url": "https://example.org/a", "referrer": 123, "filename": "ok"},
    ]
    with patch("native_host.urllib.request.urlopen") as network:
        for payload in bad:
            assert handle_message(payload)["code"] == "invalid_capture"
        network.assert_not_called()


def test_valid_public_capture_uses_fixed_loopback_endpoint_without_cookie():
    payload = {"type": "capture_public", "url": "https://example.org/a.zip",
               "referrer": "https://example.org/", "filename": "a.zip"}

    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args): return b'{"id":"abcdef12"}'

    with patch("native_host.urllib.request.urlopen", return_value=Response()) as network:
        result = handle_message(payload)
    assert result == {"type": "capture_result", "ok": True}
    req = network.call_args.args[0]
    assert req.full_url == "http://127.0.0.1:9614/api/capture"
    body = json.loads(req.data)
    assert body["url"] == payload["url"]
    assert body["open_window"] is True
    assert body["headers"] == {"Referer": payload["referrer"]}
    assert not any(k.lower() == "cookie" for k in body["headers"])


def test_local_api_unavailable_returns_error_without_success():
    payload = {"type": "capture_public", "url": "https://example.org/a.zip",
               "referrer": None, "filename": None}
    with patch("native_host.urllib.request.urlopen", side_effect=OSError("offline")):
        assert handle_message(payload) == {"type": "error", "code": "rapido_unavailable"}



def test_referrer_credentials_are_rejected_without_http_call():
    payload = {"type": "capture_public", "url": "https://example.org/a.zip",
               "referrer": "https://alice:secret@example.org/path", "filename": None}
    with patch("native_host.urllib.request.urlopen") as network:
        assert handle_message(payload) == {"type": "error", "code": "invalid_capture"}
        network.assert_not_called()


def test_native_host_strips_referrer_query_and_fragment():
    payload = {"type": "capture_public", "url": "https://example.org/a.zip",
               "referrer": "https://example.org/page?token=secret#private", "filename": None}

    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args): return b'{"id":"abcdef12"}'

    with patch("native_host.urllib.request.urlopen", return_value=Response()) as network:
        assert handle_message(payload) == {"type": "capture_result", "ok": True}
    body = json.loads(network.call_args.args[0].data)
    assert body["headers"]["Referer"] == "https://example.org/page"
    assert "secret" not in json.dumps(body["headers"])
