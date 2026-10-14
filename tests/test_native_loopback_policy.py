"""The native host has no unauthenticated loopback HTTP fallback."""
from pathlib import Path
from unittest.mock import patch
import native_host


def test_native_host_does_not_import_or_call_http_clients():
    source = Path("native_host.py").read_text("utf-8")
    for name in ("urllib.request","urlopen","LOCAL_CAPTURE_URL","_open_loopback"):
        assert name not in source


def test_source_host_does_not_bypass_packaged_peer_identity():
    with patch.object(native_host.sys,"frozen",False,create=True):
        with patch("native_pipe.request") as rpc:
            try:
                native_host._native_request({"type":"capture_public"})
            except OSError:
                pass
            else:
                raise AssertionError("Source host cannot claim packaged identity")
            rpc.assert_not_called()


def test_packaged_host_pins_the_adjacent_desktop_server_image():
    from pathlib import Path
    with patch.object(native_host.sys,"frozen",True,create=True):
        with patch("native_launcher.trusted_launcher"):
            with patch("native_pipe.request",return_value={"ok":True}) as rpc:
                assert native_host._native_request({"type":"capabilities"}) == {"ok":True}
    assert rpc.call_args.kwargs["server_images"] == [
        str(Path(native_host.sys.executable).with_name("Rapido.exe"))]
    assert rpc.call_args.kwargs["timeout"] == 5
