"""Static contract checks for registered Rapido Chrome Native Messaging."""
import json
from pathlib import Path


def test_extension_native_messaging_permission_and_identity():
    manifest = json.loads(Path("extension/manifest.json").read_text("utf-8"))
    assert "nativeMessaging" in manifest["permissions"]
    assert manifest["background"]["service_worker"] == "background.js"
    background = Path("extension/background.js").read_text("utf-8")
    assert 'const NATIVE_HOST = "com.rapido.bridge";' in background
    assert 'sendNativeMessage(NATIVE_HOST, {type:"ping"})' in background


def test_installer_registers_only_specific_chrome_extension():
    iss = Path("packaging/rapido.iss").read_text("utf-8")
    assert "Chrome\\NativeMessagingHosts\\com.rapido.bridge" in iss
    assert "RapidoNativeHost.exe" in iss
    assert "hlpkfnodjoglfdiekijebbppfgkjkbmp/" in iss
    assert '"type":"stdio"' in iss


def test_native_host_does_not_support_download_or_cookie_commands():
    from native_host import handle_message
    for kind in ("capture", "download", "cookies", "execute", "token", "read_file"):
        assert handle_message({"type": kind})["code"] == "unsupported_message"
