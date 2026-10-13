"""Static regression checks for temporary S3 browser-cookie containment.

These checks do NOT demonstrate that the local API is authenticated. They only
guard against accidentally restoring direct cookie forwarding in the extension.
End-to-end Chrome/Windows tests remain required.
"""
from pathlib import Path
import re

SOURCE = (Path(__file__).resolve().parents[1] / "extension" / "background.js").read_text(encoding="utf-8")


def _function_body(name: str) -> str:
    start = re.search(r"async function " + re.escape(name) + r"\([^)]*\)\s*\{", SOURCE)
    assert start, f"{name} missing"
    # Stop before the next top-level function declaration.
    return SOURCE[start.end():].split("\nasync function ", 1)[0]


def test_s3_headers_do_not_contain_chrome_cookies():
    headers = _function_body("buildHeaders")
    assert "chrome.cookies" not in headers
    assert "Cookie" not in headers
    assert "cookieHeader" not in SOURCE


def test_s3_cookie_backed_downloads_stay_in_chrome():
    handler = _function_body("handleDownload")
    guard = "if (await needsBrowserSession(url)) return;"
    assert guard in handler
    assert handler.index(guard) < handler.index("chrome.downloads.cancel(item.id)")
    assert handler.index(guard) < handler.index("chrome.downloads.erase({ id: item.id })")


def test_s3_unavailable_cookie_api_fails_closed():
    fn = _function_body("needsBrowserSession")
    assert "chrome.cookies.getAll({ url })" in fn
    assert re.search(r"catch\s*\{\s*return true;", fn)


def test_s3_video_capture_does_not_attach_cookies():
    for name in ("captureFile", "captureVideo"):
        fn = _function_body(name)
        assert "headers: await buildHeaders(" in fn
        assert "cookieHeader" not in fn
