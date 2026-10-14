"""Capture capabilities require the verified desktop pipe, not a ping."""
from unittest.mock import patch
from native_host import handle_message


def test_native_capabilities_require_verified_transport():
    with patch("native_host._native_request",side_effect=OSError("absent")):
        assert handle_message({"type":"capabilities"}) == {
            "type":"capabilities","protocol":1,"features":["ping"]}
    with patch("native_host._native_request",return_value={
        "type":"capabilities","protocol":1,"features":["ping","capture_public","delete","settings_public"]}):
        assert handle_message({"type":"capabilities"})["features"] == ["ping","capture_public","settings_public"]
    assert handle_message({"type":"capabilities","cookies":True})["code"] == "unsupported_message"


def test_native_host_rejects_sensitive_commands():
    for command in ("capture","download","capture_video","cookies","auth","execute"):
        assert handle_message({"type":command})["code"] == "unsupported_message"
