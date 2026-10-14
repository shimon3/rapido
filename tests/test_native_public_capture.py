"""Native capture validation: all browser data uses verified IPC, never HTTP."""
from unittest.mock import patch
from native_host import handle_message


def test_rejects_invalid_capture_before_ipc():
    base = {"type":"capture_public","url":"https://example.org/a.zip","referrer":None,"filename":"a.zip"}
    bad = [
        {**base,"url":"file:///tmp/x"},
        {**base,"url":"http://user:pass@example.com/a"},
        {**base,"url":"https://example.org:bad/a"},
        {**base,"url":"https://[broken/a"},
        {**base,"url":"https://example.org/a\r\nInjected"},
        {**base,"filename":"../evil"},
        {**base,"filename":"bad\tname"},
        {**base,"cookie":"secret"},
        {**base,"headers":{"Authorization":"secret"}},
        {**base,"referrer":"https://alice:secret@example.org/path"},
        {**base,"referrer":123},
    ]
    with patch("native_host._native_request") as rpc:
        for value in bad:
            assert handle_message(value) == {"type":"error","code":"invalid_capture"}
        rpc.assert_not_called()


def test_public_capture_uses_only_narrow_ipc_payload():
    request = {"type":"capture_public","url":"https://example.org/a.zip",
               "referrer":"https://example.org/page?token=secret#fragment","filename":"a.zip"}
    with patch("native_host._native_request",return_value={"type":"capture_result","ok":True}) as rpc:
        assert handle_message(request) == {"type":"capture_result","ok":True}
    sent = rpc.call_args.args[0]
    assert sent == {**request,"referrer":"https://example.org/page"}
    assert set(sent) == {"type","url","referrer","filename"}


def test_missing_or_untrusted_pipe_fails_without_http_fallback():
    request = {"type":"capture_public","url":"https://example.org/a.zip",
               "referrer":None,"filename":None}
    for error in (OSError("absent"),PermissionError("wrong peer"),TimeoutError("deadline")):
        with patch("native_host._native_request",side_effect=error):
            assert handle_message(request) == {"type":"error","code":"rapido_unavailable"}


def test_invalid_or_negative_capture_replies_fail_closed():
    request = {"type":"capture_public","url":"https://example.org/a.zip",
               "referrer":None,"filename":None}
    for reply in (None, [], "invalid", {"type":"capture_result","ok":False},
                  {"type":"capture_result","ok":1}, {"type":"error"}, {"id":"fake"}):
        with patch("native_host._native_request",return_value=reply):
            assert handle_message(request) == {"type":"error","code":"rapido_unavailable"}
