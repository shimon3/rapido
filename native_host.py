"""Rapido Chrome Native Messaging protocol prototype (NOT YET REGISTERED).

Chrome launches the native host using its authorized extension manifest.
This minimal host deliberately accepts only a harmless 'ping' message.
No cookies, filesystem writes or download controls are supported yet.
"""
from __future__ import annotations

import json
import struct
import sys

MAX_MESSAGE_BYTES = 64 * 1024


def _read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining:
        part = stream.read(remaining)
        if not part:
            raise ValueError("Incomplete native messaging frame")
        chunks.append(part)
        remaining -= len(part)
    return b"".join(chunks)


def read_message(stream):
    first = stream.read(1)
    if not first:
        return None
    header = first + _read_exact(stream, 3)
    size = struct.unpack("<I", header)[0]
    if size < 1 or size > MAX_MESSAGE_BYTES:
        raise ValueError("Invalid native messaging message length")
    payload = _read_exact(stream, size)
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Expected object")
    if len(data) > 8 or any(not isinstance(key, str) for key in data):
        raise ValueError("Invalid native messaging object")
    return data


def write_message(stream, data):
    payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ValueError("Native messaging reply too long")
    stream.write(struct.pack("<I", len(payload)))
    stream.write(payload)
    stream.flush()


def handle_message(data):
    if data.get("type") == "ping" and set(data) == {"type"}:
        return {"type": "pong", "protocol": 1}
    return {"type": "error", "code": "unsupported_message"}


def main():
    while True:
        try:
            request = read_message(sys.stdin.buffer)
            if request is None:
                return 0
            write_message(sys.stdout.buffer, handle_message(request))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            # Never print request content, tokens or browser cookies to stderr.
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
