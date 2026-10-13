"""Native Messaging feature discovery remains unprivileged."""
from native_host import handle_message


def test_native_capabilities_do_not_advertise_privileged_commands():
    assert handle_message({"type": "capabilities"}) == {
        "type": "capabilities", "protocol": 1, "features": ["ping", "capture_public"]
    }
    assert handle_message({"type": "capabilities", "cookies": True})["code"] == "unsupported_message"


def test_native_host_rejects_sensitive_commands():
    for command in ("capture", "download", "capture_video", "cookies", "auth", "execute"):
        assert handle_message({"type": command})["code"] == "unsupported_message"
