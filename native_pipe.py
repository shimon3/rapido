"""Bounded Windows named-pipe RPC with kernel-verified peers and explicit DACL.

No bearer secret is exchanged. Caller authority is an executable/SID allowlist.
Trusted-file replacement and process injection require a separate signing policy.
"""
from __future__ import annotations
import ctypes
import hashlib
import json
import os
import struct
import threading
import time
from ctypes import wintypes
from windows_ipc import validate_pipe_name, require_windows_identity_policy
from windows_peer import inspect_process, verified_pipe_peer, canonical_image

MAX_FRAME = 65536


class _Overlapped(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t),
                ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD),
                ("hEvent", wintypes.HANDLE)]


def _kernel():
    if os.name != "nt":
        raise OSError("Windows named pipes require Windows")
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    declarations = {
        "CreateNamedPipeW": ([wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                            wintypes.DWORD, wintypes.LPVOID], wintypes.HANDLE),
        "CreateFileW": ([wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                        wintypes.HANDLE], wintypes.HANDLE),
        "CreateEventW": ([wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
        "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        "LocalFree": ([wintypes.HLOCAL], wintypes.HLOCAL),
        "ConnectNamedPipe": ([wintypes.HANDLE, ctypes.POINTER(_Overlapped)], wintypes.BOOL),
        "DisconnectNamedPipe": ([wintypes.HANDLE], wintypes.BOOL),
        "CancelIoEx": ([wintypes.HANDLE, ctypes.POINTER(_Overlapped)], wintypes.BOOL),
        "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
        "GetOverlappedResult": ([wintypes.HANDLE, ctypes.POINTER(_Overlapped),
                                 ctypes.POINTER(wintypes.DWORD), wintypes.BOOL], wintypes.BOOL),
        "ReadFile": ([wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                      ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(_Overlapped)], wintypes.BOOL),
        "WriteFile": ([wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                       ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(_Overlapped)], wintypes.BOOL),
    }
    for name, (args, result) in declarations.items():
        function = getattr(k, name)
        function.argtypes, function.restype = args, result
    return k


def current_sid():
    with inspect_process(os.getpid()) as identity:
        return identity.user_sid


def channel_name(sid):
    require_windows_identity_policy(user_sid=sid, process_id=1)
    return "Rapido-" + hashlib.sha256(sid.encode("ascii")).hexdigest()[:32]


def _deadline(timeout):
    if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not 0 < timeout <= 15:
        raise ValueError("Pipe timeout must be between zero and 15 seconds")
    return time.monotonic() + timeout


def _operation(k, handle, deadline, function, *args):
    event = k.CreateEventW(None, True, False, None)
    if not event:
        raise ctypes.WinError(ctypes.get_last_error())
    ov = _Overlapped()
    ov.hEvent = event
    try:
        ctypes.set_last_error(0)
        success = function(handle, *args, ctypes.byref(ov))
        error = 0 if success else ctypes.get_last_error()
        if function == k.ConnectNamedPipe and error == 535:  # already connected
            return 0
        if error not in (0, 997):  # ERROR_IO_PENDING
            raise ctypes.WinError(error)
        if error == 997:
            remaining = max(0, int((deadline - time.monotonic()) * 1000))
            outcome = k.WaitForSingleObject(event, remaining)
            if outcome != 0:
                k.CancelIoEx(handle, ctypes.byref(ov))
                # Drain cancellation before freeing the OVERLAPPED/buffer.
                ignored = wintypes.DWORD()
                k.GetOverlappedResult(handle, ctypes.byref(ov), ctypes.byref(ignored), True)
                if outcome == 258:
                    raise TimeoutError("Named-pipe operation timed out")
                raise ctypes.WinError(ctypes.get_last_error())
        transferred = wintypes.DWORD()
        if not k.GetOverlappedResult(handle, ctypes.byref(ov), ctypes.byref(transferred), False):
            raise ctypes.WinError(ctypes.get_last_error())
        return transferred.value
    finally:
        k.CloseHandle(event)


def _read(k, handle, size, deadline):
    result = []
    while size:
        buffer = ctypes.create_string_buffer(size)
        transferred = wintypes.DWORD()
        got = _operation(k, handle, deadline, k.ReadFile, buffer, size, ctypes.byref(transferred))
        if got <= 0 or got > size:
            raise ValueError("Truncated pipe frame")
        result.append(buffer.raw[:got])
        size -= got
    return b"".join(result)


def _pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _receive(k, handle, deadline):
    size = struct.unpack("<I", _read(k, handle, 4, deadline))[0]
    if not 0 < size <= MAX_FRAME:
        raise ValueError("Pipe frame too large")
    value = json.loads(_read(k, handle, size, deadline).decode("utf-8"), object_pairs_hook=_pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Invalid JSON number")))
    if not isinstance(value, dict) or len(value) > 8:
        raise ValueError("Expected a bounded JSON object")
    return value


def _send(k, handle, value, deadline):
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    payload = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode()
    if not 0 < len(payload) <= MAX_FRAME:
        raise ValueError("Pipe frame too large")
    frame = struct.pack("<I", len(payload)) + payload
    offset = 0
    while offset < len(frame):
        buffer = ctypes.create_string_buffer(frame[offset:])
        transferred = wintypes.DWORD()
        count = _operation(k, handle, deadline, k.WriteFile, buffer, len(frame) - offset,
                           ctypes.byref(transferred))
        if count <= 0 or count > len(frame) - offset:
            raise ValueError("Incomplete pipe write")
        offset += count


def _create(k, name, sid):
    path = validate_pipe_name(name)
    require_windows_identity_policy(user_sid=sid, process_id=1)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.LPVOID),
                        ctypes.POINTER(wintypes.DWORD)]
    convert.restype = wintypes.BOOL
    class Attributes(ctypes.Structure):
        _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", wintypes.LPVOID),
                    ("bInheritHandle", wintypes.BOOL)]
    descriptor = wintypes.LPVOID()
    # Exclude FILE_CREATE_PIPE_INSTANCE (0x4), including from the user ACE.
    sddl = "D:P(A;;GA;;;SY)(A;;0x12019b;;;" + sid + ")"
    if not convert(sddl, 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attrs = Attributes(ctypes.sizeof(Attributes), descriptor, False)
        # Duplex, overlapped, first instance; byte stream, remote clients rejected.
        handle = k.CreateNamedPipeW(path, 3 | 0x40000000 | 0x80000, 8,
                                     1, MAX_FRAME + 4, MAX_FRAME + 4, 0, ctypes.byref(attrs))
        if handle is None or handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle
    finally:
        k.LocalFree(descriptor)


class PipeServer:
    def __init__(self, handler, *, clients, sid=None, name=None, timeout=5):
        if not callable(handler) or not isinstance(clients, dict) or not clients:
            raise ValueError("Explicit handler and client image roles are required")
        self._clients = {canonical_image(p): role for p, role in clients.items()}
        if any(not isinstance(role, str) or not role for role in self._clients.values()):
            raise ValueError("Invalid peer role")
        self._handler = handler
        self._sid = sid or current_sid()
        self.name = name or channel_name(self._sid)
        validate_pipe_name(self.name)
        _deadline(timeout)
        self._timeout = timeout
        self._stop = threading.Event()
        self._thread = None
        self._handle = None

    def start(self):
        if self._thread is not None:
            raise RuntimeError("Pipe server already started")
        k = _kernel()
        self._handle = _create(k, self.name, self._sid)
        self._thread = threading.Thread(target=self._run, name="rapido-native-pipe", daemon=True)
        self._thread.start()
        return self

    def _run(self):
        k = _kernel()
        handle = self._handle
        try:
            while not self._stop.is_set():
                try:
                    _operation(k, handle, _deadline(.25), k.ConnectNamedPipe)
                    if self._stop.is_set():
                        break
                    with verified_pipe_peer(handle, server=False, user_sid=self._sid,
                                            image_paths=list(self._clients)) as peer:
                        deadline = _deadline(self._timeout)
                        request = _receive(k, handle, deadline)
                        response = self._handler(self._clients[peer.image_path], request)
                        _send(k, handle, response, deadline)
                        if _receive(k, handle, deadline) != {"ack": True}:
                            raise ValueError("Invalid reply acknowledgement")
                except (OSError, ValueError, TimeoutError):
                    pass  # Refuse silently: never log request contents or credentials.
                finally:
                    k.DisconnectNamedPipe(handle)
        finally:
            k.CloseHandle(handle)

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            k = _kernel()
            k.CancelIoEx(self._handle, None)
            self._thread.join(timeout=self._timeout + 1)
            if self._thread.is_alive():
                raise TimeoutError("Native pipe server did not stop")


def request(value, *, server_images, sid=None, name=None, timeout=5):
    """Verify the real server BEFORE transmitting any browser URL/metadata."""
    deadline = _deadline(timeout)
    sid = sid or current_sid()
    path = validate_pipe_name(name or channel_name(sid))
    k = _kernel()
    handle = None
    while time.monotonic() < deadline:
        # Only read/write data + SYNCHRONIZE: do not request pipe creation rights.
        handle = k.CreateFileW(path, 0x100003, 0, None, 3,
                              0x40000000 | 0x100000 | 0x10000, None)
        if handle is not None and handle != ctypes.c_void_p(-1).value:
            break
        error = ctypes.get_last_error()
        if error not in (2, 231):
            raise ctypes.WinError(error)
        time.sleep(.02)
    else:
        raise TimeoutError("Native pipe is unavailable")
    try:
        with verified_pipe_peer(handle, server=True, user_sid=sid, image_paths=server_images):
            _send(k, handle, value, deadline)
            result = _receive(k, handle, deadline)
        # The server retains the connection until the response has been consumed.
        _send(k, handle, {"ack": True}, deadline)
        return result
    finally:
        k.CloseHandle(handle)
