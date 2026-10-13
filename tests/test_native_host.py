"""Regression tests for the isolated, unregistered native host prototype."""
import io
import json
import struct

import pytest

from native_host import MAX_MESSAGE_BYTES, handle_message, read_message, write_message


def test_ping_round_trip():
    out = io.BytesIO()
    write_message(out, {"type": "ping"})
    out.seek(0)
    assert read_message(out) == {"type": "ping"}
    assert handle_message({"type": "ping"}) == {"type": "pong", "protocol": 1}


def test_dangerous_messages_not_supported():
    for kind in ("download", "cookies", "run", "write_file", "pair", "token"):
        assert handle_message({"type": kind})["code"] == "unsupported_message"
    assert handle_message({"type": "ping", "token": "secret"})["code"] == "unsupported_message"


def test_reject_oversized_and_truncated_frames():
    with pytest.raises(ValueError):
        read_message(io.BytesIO(struct.pack("<I", MAX_MESSAGE_BYTES + 1)))
    with pytest.raises(ValueError):
        read_message(io.BytesIO(b"\x02\x00"))
    with pytest.raises(ValueError):
        read_message(io.BytesIO(struct.pack("<I", 20) + b"{}"))


def test_reject_invalid_payloads():
    invalid = [b"[]", b"null", b"{broken", b"\xff"]
    for payload in invalid:
        stream = io.BytesIO(struct.pack("<I", len(payload)) + payload)
        with pytest.raises((ValueError, UnicodeDecodeError, json.JSONDecodeError)):
            read_message(stream)
