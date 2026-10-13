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
