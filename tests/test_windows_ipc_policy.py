"""S2 Windows IPC policy must never silently create an unprotected endpoint."""
import pytest
from windows_ipc import validate_pipe_name, require_windows_identity_policy, open_authenticated_pipe


def test_pipe_names_are_bounded_and_local():
    assert validate_pipe_name("Rapido-1234567890abcdef") == r"\\.\pipe\Rapido-1234567890abcdef"
    for value in ("", "Rapido-short", r"\\server\pipe\Rapido-1234567890abcdef",
                  "Rapido-1234567890abcdef/other", "Other-1234567890abcdef", None):
        with pytest.raises(ValueError):
            validate_pipe_name(value)


def test_client_identity_inputs_are_required():
    require_windows_identity_policy(user_sid="S-1-5-21-111-222-333-1001", process_id=100)
    for sid, pid in (("", 100), ("everyone", 100), ("S-1-5-21-111", 0),
                     ("S-1-5-21-111", True), ("S-1-5-21-111", -1)):
        with pytest.raises(ValueError):
            require_windows_identity_policy(user_sid=sid, process_id=pid)


def test_incomplete_pipe_transport_refuses_to_start():
    with pytest.raises(NotImplementedError):
        open_authenticated_pipe()
