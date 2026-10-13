"""S3 interim guard: browser cookies cannot be sent through loopback capture."""
from pathlib import Path

SOURCE = Path("extension/background.js").read_text("utf-8")


def test_no_cookie_forwarding_to_local_http():
    assert "cookieHeader(" not in SOURCE
    assert "h.Cookie" not in SOURCE
    assert "chrome.cookies.getAll" in SOURCE
    headers = SOURCE.split("async function buildHeaders(", 1)[1].split("async function needsBrowserSession(", 1)[0]
    assert "Cookie" not in headers


def test_guard_precedes_cancel_or_erase():
    body = SOURCE.split("async function handleDownload(", 1)[1].split("/* ---------- détection des flux vidéo", 1)[0]
    assert body.index("await needsBrowserSession(url)") < body.index("chrome.downloads.cancel(item.id)")
    assert body.index("await needsBrowserSession(url)") < body.index("chrome.downloads.erase({ id: item.id })")


def test_cookie_inspection_failure_does_not_intercept():
    body = SOURCE.split("async function needsBrowserSession(", 1)[1].split("async function post(", 1)[0]
    assert "catch { return true; }" in body


def test_video_capture_does_not_post_to_unauthenticated_loopback():
    body = SOURCE.split("async function captureVideo(", 1)[1].split("/* ---------- interception des téléchargements", 1)[0]
    assert 'post("/api/capture-video"' not in body
    assert "throw new Error" in body
    assert "S3" in body
