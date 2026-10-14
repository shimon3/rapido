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


def test_pipe_dacl_grants_only_explicit_user_and_system():
    from windows_ipc import pipe_security_sddl
    sid = "S-1-5-21-111-222-333-1001"
    policy = pipe_security_sddl(sid)
    assert policy.startswith("D:P")
    assert policy.count("(A;;") == 2
    assert ";;;SY)" in policy
    assert ";;;" + sid + ")" in policy
    assert ";;;WD)" not in policy
    assert ";;;AN)" not in policy
    assert ";;;BA)" not in policy


def test_pipe_dacl_rejects_untrusted_sid_text():
    from windows_ipc import pipe_security_sddl
    for bad in ("", "WD", "S-1-5-21-1) (A;;GA;;;WD)", None):
        with pytest.raises(ValueError):
            pipe_security_sddl(bad)


def test_restricted_listener_rejects_invalid_namespace_and_sid():
    from windows_ipc import create_restricted_pipe
    import os
    if os.name != "nt":
        with pytest.raises(OSError):
            create_restricted_pipe("Rapido-1234567890abcdef", "S-1-5-21-111-222-333-1001")
        return
    with pytest.raises(ValueError):
        create_restricted_pipe("evil", "S-1-5-21-111-222-333-1001")
    with pytest.raises(ValueError):
        create_restricted_pipe("Rapido-1234567890abcdef", "WD")


def test_pipe_listener_is_not_mistaken_for_authenticated_session():
    from windows_ipc import open_authenticated_pipe
    with pytest.raises(NotImplementedError):
        open_authenticated_pipe()


def test_client_pid_discovery_refuses_non_windows_and_invalid_handles():
    import os
    from windows_ipc import connected_client_pid
    if os.name != "nt":
        with pytest.raises(OSError):
            connected_client_pid(1)
        return
    for invalid in (0, -1, True, None, "handle"):
        with pytest.raises(ValueError):
            connected_client_pid(invalid)


def test_client_pid_discovery_is_not_authentication():
    from windows_ipc import open_authenticated_pipe
    with pytest.raises(NotImplementedError):
        open_authenticated_pipe()


def test_connected_client_must_match_expected_pid(monkeypatch):
    import windows_ipc
    monkeypatch.setattr(windows_ipc, "connected_client_pid", lambda handle: 1234)
    assert windows_ipc.connected_client_matches_pid(99, 1234) is True
    assert windows_ipc.connected_client_matches_pid(99, 5678) is False
    for invalid in (0, -1, None, True, "1234"):
        with pytest.raises(ValueError):
            windows_ipc.connected_client_matches_pid(99, invalid)


def test_close_restricted_pipe_rejects_invalid_handle():
    import os
    from windows_ipc import close_restricted_pipe
    if os.name != "nt":
        with pytest.raises(OSError):
            close_restricted_pipe(1)
        return
    for bad in (None, False, True, 0, -1, "handle"):
        with pytest.raises(ValueError):
            close_restricted_pipe(bad)


def test_reject_well_known_service_and_group_sids():
    from windows_ipc import pipe_security_sddl
    for sid in ("S-1-5-18", "S-1-5-19", "S-1-5-20", "S-1-5-11",
                "S-1-5-32-544", "S-1-5-32-545", "S-1-5-32-551",
                "S-1-5-32-99999"):
        with pytest.raises(ValueError):
            require_windows_identity_policy(user_sid=sid, process_id=1234)
        with pytest.raises(ValueError):
            pipe_security_sddl(sid)
