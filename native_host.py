"""Rapido Chrome Native Messaging host prototype.

Supports ping, capabilities and constrained public-download capture.
The public capture bridge still targets a legacy unauthenticated loopback API;
S2 authenticated IPC and protected mutation routes are NOT implemented.
Never forward browser cookies or other authentication credentials.
"""
from __future__ import annotations

import json
import struct
import sys
import urllib.request
import urllib.error
from urllib.parse import urlsplit

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


def _safe_public_capture(data):
    """Constrained Chrome->native->local API bridge; API S2 still needs authentication."""
    if set(data) != {"type", "url", "referrer", "filename"}:
        return {"type": "error", "code": "invalid_capture"}
    url = data.get("url")
    referrer = data.get("referrer")
    filename = data.get("filename")
    if not isinstance(url, str) or not url or len(url) > 4096 or any(ord(ch) < 32 or ord(ch) == 127 for ch in url):
        return {"type": "error", "code": "invalid_capture"}
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            return {"type": "error", "code": "invalid_capture"}
    except ValueError:
        return {"type": "error", "code": "invalid_capture"}
    if referrer is not None and (not isinstance(referrer, str) or len(referrer) > 4096 or
                                 any(ord(ch) < 32 or ord(ch) == 127 for ch in referrer)):
        return {"type": "error", "code": "invalid_capture"}
    if filename is not None and (not isinstance(filename, str) or len(filename) > 255 or
                                 any(ch in filename for ch in "/\\\\\r\n") or
                                 any(ord(ch) < 32 or ord(ch) == 127 for ch in filename)):
        return {"type": "error", "code": "invalid_capture"}
    headers = {}
    if referrer:
        try:
            parsed_ref = urlsplit(referrer)
            if (parsed_ref.scheme not in ("http", "https") or not parsed_ref.hostname or
                    parsed_ref.username or parsed_ref.password):
                return {"type": "error", "code": "invalid_capture"}
        except ValueError:
            return {"type": "error", "code": "invalid_capture"}
        # Defense in depth: no referrer query or fragment may cross loopback.
        headers["Referer"] = parsed_ref._replace(query="", fragment="").geturl()
    body = json.dumps({"url": url, "filename": filename, "headers": headers,
                       "open_window": True}).encode("utf-8")
    try:
        request = urllib.request.Request("http://127.0.0.1:9614/api/capture",
                                         data=body, headers={"Content-Type": "application/json"},
                                         method="POST")
        with urllib.request.urlopen(request, timeout=6) as response:
            if response.status != 200:
                return {"type": "error", "code": "rapido_unavailable"}
            # Bound untrusted loopback responses before decoding JSON.
            raw = response.read(65537)
            if len(raw) > 65536:
                return {"type": "error", "code": "rapido_unavailable"}
            result = json.loads(raw)
        return {"type": "capture_result", "ok": True} if isinstance(result, dict) and isinstance(result.get("id"), str) else {
            "type": "error", "code": "rapido_unavailable"}
    except (OSError, ValueError, urllib.error.URLError):
        return {"type": "error", "code": "rapido_unavailable"}


def handle_message(data):
    if data.get("type") == "ping" and set(data) == {"type"}:
        return {"type": "pong", "protocol": 1}
    if data.get("type") == "capabilities" and set(data) == {"type"}:
        return {"type": "capabilities", "protocol": 1, "features": ["ping", "capture_public"]}
    if data.get("type") == "capture_public":
        return _safe_public_capture(data)
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
