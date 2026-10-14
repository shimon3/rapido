"""Windows IPC security groundwork — intentionally not connected to Rapido.

A named-pipe endpoint requires an explicit Windows security descriptor and
client identity checks before it can carry a bearer secret. This module
validates naming and policy inputs only; it never creates a permissive pipe.
"""
from __future__ import annotations

import re

PIPE_PREFIX = r"\\.\pipe\Rapido-"


def validate_pipe_name(name: str) -> str:
    """Accept only a fixed, bounded local-pipe namespace."""
    if not isinstance(name, str):
        raise ValueError("Invalid pipe name")
    if not re.fullmatch(r"Rapido-[A-Za-z0-9_-]{16,64}", name):
        raise ValueError("Invalid pipe name")
    return "\\\\.\\pipe\\" + name


def require_windows_identity_policy(*, user_sid: str, process_id: int) -> None:
    """Fail closed on missing or malformed identity before native IPC setup.

    Parsing is NOT verification: Windows must subsequently obtain the SID
    and PID from the actual connected client and enforce an ACL.
    """
    if not isinstance(user_sid, str) or not re.fullmatch(r"S-1-5-(?:\d+-){1,14}\d+", user_sid):
        raise ValueError("Invalid Windows user SID")
    # Reject well-known service/group principals: a caller-supplied SID is
    # not evidence that it identifies an interactive user.
    if user_sid in {"S-1-5-18", "S-1-5-19", "S-1-5-20", "S-1-5-11",
                    "S-1-5-32-544", "S-1-5-32-545"} or user_sid.startswith("S-1-5-32-"):
        raise ValueError("Expected an individual Windows user SID")
    if not isinstance(process_id, int) or isinstance(process_id, bool) or process_id <= 0:
        raise ValueError("Invalid Windows process ID")


def open_authenticated_pipe(*args, **kwargs):
    """Do not create an IPC listener until ACL and impersonation are implemented."""
    raise NotImplementedError("Authenticated Windows named-pipe transport not yet implemented")


def pipe_security_sddl(user_sid: str) -> str:
    """Minimal explicit DACL candidate for a future Windows named pipe.

    Grants the specified user only read/write access, SYSTEM full control;
    does not grant Everyone, anonymous or administrators by default.
    This SDDL MUST still be attached to CreateNamedPipeW and client identity
    must be verified after connection. It does not authenticate by itself.
    """
    require_windows_identity_policy(user_sid=user_sid, process_id=1)
    return "D:P(A;;0x12019f;;;SY)(A;;0x12019f;;;" + user_sid + ")"


def create_restricted_pipe(name: str, user_sid: str):
    """Create a Windows named-pipe *listener handle* with explicit DACL.

    This is deliberately not an authenticated session: callers MUST NOT read
    requests or return secrets until connected-client identity verification
    and the application protocol are implemented. Returns an owned OS handle.
    """
    import os
    if os.name != "nt":
        raise OSError("Windows named pipes require Windows")
    import ctypes
    from ctypes import wintypes

    path = validate_pipe_name(name)
    sddl = pipe_security_sddl(user_sid)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    class SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("nLength", wintypes.DWORD),
                    ("lpSecurityDescriptor", wintypes.LPVOID),
                    ("bInheritHandle", wintypes.BOOL)]

    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                        ctypes.POINTER(wintypes.LPVOID), ctypes.POINTER(wintypes.DWORD)]
    convert.restype = wintypes.BOOL
    create = kernel.CreateNamedPipeW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                       wintypes.DWORD, ctypes.POINTER(SECURITY_ATTRIBUTES)]
    create.restype = wintypes.HANDLE
    free = kernel.LocalFree
    free.argtypes = [wintypes.HLOCAL]
    free.restype = wintypes.HLOCAL
    descriptor = wintypes.LPVOID()
    if not convert(sddl, 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attrs = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), descriptor, False)
        # PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED is unnecessary for this
        # single-instance, not-yet-connected listener. FILE_FLAG_FIRST_PIPE_INSTANCE
        # prevents silently opening a second server with this name.
        PIPE_ACCESS_DUPLEX = 0x00000003
        FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
        PIPE_TYPE_MESSAGE = 0x00000004
        PIPE_READMODE_MESSAGE = 0x00000002
        PIPE_WAIT = 0x00000000
        PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
        handle = create(path, PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE,
                        PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT |
                        PIPE_REJECT_REMOTE_CLIENTS,
                        1, 4096, 4096, 0, ctypes.byref(attrs))
        invalid = ctypes.c_void_p(-1).value
        if handle is None or handle == invalid:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle
    finally:
        free(descriptor)


def close_restricted_pipe(handle):
    """Release the handle returned by create_restricted_pipe."""
    import os
    if os.name != "nt":
        raise OSError("Windows named pipes require Windows")
    import ctypes
    if (not isinstance(handle, int) or isinstance(handle, bool) or
            handle <= 0 or handle == ctypes.c_void_p(-1).value):
        raise ValueError("Invalid named-pipe handle")
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    if not close(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def connected_client_pid(pipe_handle) -> int:
    """Ask Windows for the PID of the client connected to a named pipe.

    PID discovery alone is NOT authentication. Before granting any operation
    the server must validate the client's Windows token and process identity.
    """
    import os
    if os.name != "nt":
        raise OSError("Windows named pipes require Windows")
    import ctypes
    from ctypes import wintypes
    if (not isinstance(pipe_handle, int) or isinstance(pipe_handle, bool) or
            pipe_handle <= 0 or pipe_handle == ctypes.c_void_p(-1).value):
        raise ValueError("Invalid named-pipe handle")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    get_pid = kernel.GetNamedPipeClientProcessId
    get_pid.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]
    get_pid.restype = wintypes.BOOL
    pid = wintypes.ULONG()
    if not get_pid(pipe_handle, ctypes.byref(pid)):
        raise ctypes.WinError(ctypes.get_last_error())
    if pid.value == 0:
        raise ValueError("Missing client process ID")
    return int(pid.value)


def connected_client_matches_pid(pipe_handle, expected_pid: int) -> bool:
    """Fail closed unless Windows reports the expected connected client PID.

    This only binds a connection to a PID at query time. It does not prove the
    binary identity or protect against same-user attackers and PID reuse.
    """
    if not isinstance(expected_pid, int) or isinstance(expected_pid, bool) or expected_pid <= 0:
        raise ValueError("Invalid expected client PID")
    return connected_client_pid(pipe_handle) == expected_pid
