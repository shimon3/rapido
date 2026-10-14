"""Kernel-verified, pinned Windows process identities for named-pipe peers.

An executable path is an allowlist, not an Authenticode signature. This rejects
different executables/users; it does not protect against code injection or
replacement of trusted files by a compromised account. No bearer is returned.
"""
from __future__ import annotations

import ctypes
import ntpath
import os
from contextlib import contextmanager
from dataclasses import dataclass
from ctypes import wintypes


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    user_sid: str
    image_path: str
    creation_time: int


def _windows():
    if os.name != "nt":
        raise OSError("Windows process identity requires Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.GetProcessTimes.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME)]
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel.LocalFree.restype = wintypes.HLOCAL
    advapi.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.OpenProcessToken.restype = wintypes.BOOL
    advapi.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD)]
    advapi.GetTokenInformation.restype = wintypes.BOOL
    advapi.ConvertSidToStringSidW.argtypes = [wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR)]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    return kernel, advapi


def canonical_image(path: str) -> str:
    if not isinstance(path, str) or not path or "\x00" in path or not ntpath.isabs(path):
        raise ValueError("An absolute Windows image path is required")
    if path.startswith("\\\\?\\"):
        path = path[4:]
    return ntpath.normcase(ntpath.normpath(path))


def _pid(value):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= 0xffffffff:
        raise ValueError("Invalid process ID")
    return value


def _identity(handle, pid, kernel, advapi):
    if kernel.WaitForSingleObject(handle, 0) != 258:  # WAIT_TIMEOUT: still alive
        raise PermissionError("Peer process is no longer running")
    image = ctypes.create_unicode_buffer(32768)
    size = wintypes.DWORD(len(image))
    if not kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    created, exited, system, user = (wintypes.FILETIME() for _ in range(4))
    if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                  ctypes.byref(system), ctypes.byref(user)):
        raise ctypes.WinError(ctypes.get_last_error())
    token = wintypes.HANDLE()
    if not advapi.OpenProcessToken(handle, 8, ctypes.byref(token)):  # TOKEN_QUERY only
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        needed = wintypes.DWORD()
        ok = advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
        if ok or ctypes.get_last_error() != 122 or not 0 < needed.value <= 65536:
            raise PermissionError("Cannot inspect peer token")
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi.GetTokenInformation(token, 1, buffer, len(buffer), ctypes.byref(needed)):
            raise ctypes.WinError(ctypes.get_last_error())
        # TOKEN_USER begins with SID_AND_ATTRIBUTES; its first field is PSID.
        sid_ptr = ctypes.cast(buffer, ctypes.POINTER(wintypes.LPVOID)).contents
        sid_text = wintypes.LPWSTR()
        if not advapi.ConvertSidToStringSidW(sid_ptr, ctypes.byref(sid_text)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            sid = sid_text.value
        finally:
            kernel.LocalFree(ctypes.cast(sid_text, wintypes.HLOCAL))
    finally:
        kernel.CloseHandle(token)
    stamp = (created.dwHighDateTime << 32) | created.dwLowDateTime
    if not sid or not stamp:
        raise PermissionError("Incomplete peer identity")
    return ProcessIdentity(pid, sid, canonical_image(image.value), stamp)


@contextmanager
def inspect_process(pid: int):
    """Hold one process handle throughout inspection/use; never re-open by PID."""
    pid = _pid(pid)
    kernel, advapi = _windows()
    handle = kernel.OpenProcess(0x1000 | 0x100000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        identity = _identity(handle, pid, kernel, advapi)
        yield identity
        # A caller must not accept a response from an exited peer.
        if kernel.WaitForSingleObject(handle, 0) != 258:
            raise PermissionError("Peer exited during operation")
    finally:
        kernel.CloseHandle(handle)


@contextmanager
def verified_process(pid: int, *, user_sid: str, image_paths):
    """Require both kernel SID and a full image path, while pinning the process."""
    from windows_ipc import require_windows_identity_policy
    require_windows_identity_policy(user_sid=user_sid, process_id=_pid(pid))
    if isinstance(image_paths, (str, bytes)) or not image_paths:
        raise ValueError("An explicit image allowlist is required")
    allowed = frozenset(canonical_image(path) for path in image_paths)
    if not allowed:
        raise ValueError("An explicit image allowlist is required")
    with inspect_process(pid) as identity:
        if identity.user_sid != user_sid or identity.image_path not in allowed:
            raise PermissionError("Peer identity is not authorized")
        yield identity


def pipe_peer_pid(handle, *, server: bool) -> int:
    """server=True obtains the pipe server PID; False obtains its client PID."""
    if not isinstance(server, bool):
        raise ValueError("Specify a pipe side")
    if not isinstance(handle, int) or isinstance(handle, bool) or handle <= 0 or handle == ctypes.c_void_p(-1).value:
        raise ValueError("Invalid pipe handle")
    kernel, _ = _windows()
    name = "GetNamedPipeServerProcessId" if server else "GetNamedPipeClientProcessId"
    function = getattr(kernel, name)
    function.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]
    function.restype = wintypes.BOOL
    value = wintypes.ULONG()
    if not function(handle, ctypes.byref(value)):
        raise ctypes.WinError(ctypes.get_last_error())
    return _pid(value.value)


@contextmanager
def verified_pipe_peer(handle, *, server: bool, user_sid: str, image_paths):
    """Verify actual connected OS peer before reading/writing a pipe payload."""
    pid = pipe_peer_pid(handle, server=server)
    with verified_process(pid, user_sid=user_sid, image_paths=image_paths) as identity:
        if pipe_peer_pid(handle, server=server) != pid:
            raise PermissionError("Connected pipe peer changed")
        yield identity
        if pipe_peer_pid(handle, server=server) != pid:
            raise PermissionError("Connected pipe peer changed")
