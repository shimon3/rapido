"""Native Messaging framing survives partial pipe reads and fails closed."""
import io
import json
import struct

import pytest

from native_host import read_message


class ShortReadStream:
    def __init__(self, payload):
        self.stream = io.BytesIO(payload)

    def read(self, size):
        return self.stream.read(min(size, 2))


def test_partial_payload_reads_are_combined():
    payload = b'{"type":"ping"}'
    frame = struct.pack("<I", len(payload)) + payload
    assert read_message(ShortReadStream(frame)) == {"type": "ping"}


def test_truncated_payload_is_rejected():
    frame = struct.pack("<I", 12) + b'{"type":'
    with pytest.raises(ValueError):
        read_message(ShortReadStream(frame))


def test_unexpectedly_large_object_is_rejected():
    payload = json.dumps({str(i): i for i in range(9)}).encode("utf-8")
    frame = struct.pack("<I", len(payload)) + payload
    with pytest.raises(ValueError):
        read_message(io.BytesIO(frame))
