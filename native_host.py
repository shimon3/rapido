"""Rapido Native Messaging host: kernel-verified Windows IPC only.

Public capture never falls back to HTTP, and never forwards browser cookies
or authorization headers. The pipe server is verified before any URL is sent.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from native_protocol import public_capture
from native_pipe import _pairs
from native_diagnostics import event, trace

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
    data = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Invalid JSON number")))
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


def _native_request(data):
    if not getattr(sys, "frozen", False):
        raise OSError("Native IPC capture requires the packaged Windows host")
    from native_pipe import request
    from native_launcher import trusted_launcher
    with trace('host', 'launcher', operation=data.get('type')):
        with trusted_launcher(sys.executable, sys.argv[1:]):
            event('host', 'peer', operation=data.get('type'))
            return request(data, server_images=[str(Path(sys.executable).with_name("Rapido.exe"))],
                           timeout=5)


def _safe_public_capture(data):
    try:
        value = public_capture(data)
    except (ValueError, TypeError):
        return {"type":"error","code":"invalid_capture"}
    try:
        response = _native_request({"type":"capture_public", **value})
        if (isinstance(response, dict) and response.get("type") == "capture_result"
                and response.get("ok") is True):
            return {"type":"capture_result","ok":True}
    except (OSError, ValueError, TimeoutError):
        pass
    return {"type":"error","code":"rapido_unavailable"}


def handle_message(data):
    if data.get("type") == "ping" and set(data) == {"type"}:
        return {"type":"pong","protocol":1}
    if data.get("type") in ("capabilities","settings_public") and set(data) == {"type"}:
        try:
            response = _native_request(data)
            if data["type"] == "capabilities":
                if (response.get("type") == "capabilities" and response.get("protocol") == 1
                        and isinstance(response.get("features"), list)):
                    return {"type":"capabilities","protocol":1,
                            "features":[f for f in response["features"] if f in ("ping","capture_public","settings_public","capture_handoff")]}
            elif response.get("type") == "settings_public":
                return response
        except (OSError, ValueError, TimeoutError, AttributeError):
            pass
        if data["type"] == "capabilities":
            return {"type":"capabilities","protocol":1,"features":["ping"]}
        return {"type":"error","code":"rapido_unavailable"}
    if data.get("type") in ("capture_prepare","capture_commit","capture_abort"):
        from native_protocol import handoff_message as validate
        phase = 'validate'
        try:
            event('host', phase, operation=data.get('type'), outcome='begin')
            validate(data)
            phase = 'dispatch'
            response = _native_request(data)
            phase = 'reply'
            event('host', phase, operation=data.get('type'),
                  response_type=response.get('type') if isinstance(response, dict) else None,
                  response_code=response.get('code') if isinstance(response, dict) else None)
            if not isinstance(response,dict):
                raise ValueError("Invalid handoff response")
            if data["type"] == "capture_prepare":
                ticket=response.get("ticket")
                validate({"type":"capture_commit","ticket":ticket})
                if response.get("type")=="capture_prepared":
                    event('host', phase, operation=data.get('type'))
                    return {"type":"capture_prepared","ticket":ticket}
            elif response.get("type") == ("capture_result" if data["type"]=="capture_commit" else "capture_aborted") and response.get("ok") is True:
                return {"type":response["type"],"ok":True}
        except (OSError,ValueError,TypeError,TimeoutError) as error:
            event('host', phase, operation=data.get('type'), outcome='error', error=error)
        return {"type":"error","code":"handoff_unavailable"}
    if data.get("type") == "capture_public":
        return _safe_public_capture(data)
    return {"type":"error","code":"unsupported_message"}


def main():
    event('host', 'start')
    if sys.argv[1:] in (["--register-native-hosts"], ["--unregister-native-hosts"]):
        if not getattr(sys, "frozen", False) or sys.platform != "win32":
            return 2
        from native_registration import register, unregister
        operation = register if sys.argv[1] == "--register-native-hosts" else unregister
        try:
            operation(sys.executable)
        except (OSError, ValueError):
            return 1
        return 0
    sequence = 0
    while True:
        try:
            request = read_message(sys.stdin.buffer)
            if request is None:
                event('host', 'exit', sequence=sequence, returncode=0)
                return 0
            sequence += 1
            event('host', 'receive', operation=request.get('type'), sequence=sequence)
            write_message(sys.stdout.buffer, handle_message(request))
            event('host', 'send', operation=request.get('type'), sequence=sequence)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            event('host', 'exit', outcome='error', error=error, sequence=sequence, returncode=1)
            # Never print request content, tokens or browser cookies to stderr.
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
