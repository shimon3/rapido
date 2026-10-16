"""Five downloader regressions: validators, If-Range, disk-full, 429/503."""
import asyncio
import errno
import functools
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import AsyncMock

import pytest
import httpx
import engine


def async_test(function):
    """Run the focused coroutines with stdlib asyncio, as the main suite does."""
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))
    return wrapped


def test_retry_after_bounds_and_formats():
    assert engine.retry_after_seconds("30") == 30
    assert engine.retry_after_seconds("99999") == 60
    assert engine.retry_after_seconds("-1") == 0
    assert engine.retry_after_seconds("NaN") == 0
    assert engine.retry_after_seconds("bad") == 0
    future = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=20))
    assert 0 < engine.retry_after_seconds(future) <= 20


class FakeStream:
    def __init__(self, *, status=206, headers=None, chunks=(b"hello",)):
        self.status_code = status
        self.headers = headers or {"content-range": "bytes 0-4/5"}
        self.chunks = chunks
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return False
    def raise_for_status(self):
        return None
    async def aiter_raw(self, chunk_size):
        for chunk in self.chunks:
            yield chunk


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.headers = None
    def stream(self, method, url, headers):
        self.headers = headers
        return self.response


class FakeFH:
    def seek(self, *args):
        pass
    def write(self, chunk):
        return len(chunk)


def make_manager(client):
    m = object.__new__(engine.Manager)
    m.client = client
    m.settings = {"speed_limit_kbps": 0}
    m._throttle = AsyncMock()
    m.save = lambda *args, **kwargs: None
    return m


def make_download(**kw):
    return engine.Download(id="abc", url="https://example.org/file.bin",
                           size=5, resumable=True, etag='"v1"',
                           segments=[engine.Segment(0, 4)], **kw)


@async_test
async def test_if_range_uses_probed_strong_etag():
    client = FakeClient(FakeStream(headers={"content-range": "bytes 0-4/5", "etag": '"v1"'}))
    dl = make_download()
    await make_manager(client)._segment_worker(dl, dl.segments[0], FakeFH())
    assert client.headers["If-Range"] == '"v1"'
    assert dl.downloaded == 5


@async_test
async def test_weak_etag_never_falls_back_to_last_modified_if_range():
    client = FakeClient(FakeStream(headers={"content-range": "bytes 0-4/5"}))
    dl = make_download()
    dl.etag = 'W/"v1"'
    dl.last_modified = "Wed, 21 Oct 2015 07:28:00 GMT"
    await make_manager(client)._segment_worker(dl, dl.segments[0], FakeFH())
    assert "If-Range" not in client.headers


@async_test
async def test_mismatched_etag_fails_without_writing():
    client = FakeClient(FakeStream(headers={"content-range": "bytes 0-4/5", "etag": '"v2"'}))
    dl = make_download()
    class NoWrite(FakeFH):
        def write(self, chunk):
            raise AssertionError("must reject changed file before writing")
    with pytest.raises(engine.ResourceChanged):
        await make_manager(client)._segment_worker(dl, dl.segments[0], NoWrite())
    assert dl.downloaded == 0


@async_test
async def test_disk_full_aborts_without_retry():
    client = FakeClient(FakeStream())
    dl = make_download()
    class Full(FakeFH):
        def write(self, chunk):
            raise OSError(errno.ENOSPC, "disk full")
    with pytest.raises(OSError) as exc:
        await make_manager(client)._segment_worker(dl, dl.segments[0], Full())
    assert exc.value.errno == errno.ENOSPC


@async_test
async def test_server_busy_uses_retry_after_and_retry_budget(monkeypatch):
    class Busy(FakeStream):
        def __init__(self):
            super().__init__(status=503, headers={"retry-after":"8"})
    client = FakeClient(Busy())
    dl = make_download()
    sleeps = []
    async def fake_sleep(n):
        sleeps.append(n)
    monkeypatch.setattr(engine.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(engine, "MAX_RETRIES", 1)
    with pytest.raises(engine.ServerBackoff):
        await make_manager(client)._segment_worker(dl, dl.segments[0], FakeFH())
    assert sleeps == [8]


@async_test
async def test_rejects_wrong_resource_total_in_content_range():
    client = FakeClient(FakeStream(headers={"content-range":"bytes 0-4/6", "etag": '"v1"'}))
    dl = make_download()
    with pytest.raises(IOError, match="Plage inattendue"):
        await make_manager(client)._segment_worker(dl, dl.segments[0], FakeFH())


@async_test
async def test_rejects_reversed_content_range():
    client = FakeClient(FakeStream(headers={"content-range":"bytes 0-0/5", "etag": '"v1"'}))
    dl = make_download()
    # Start offset for the next segment is one, but server responds with zero.
    dl.segments[0].done = 1
    with pytest.raises(IOError, match="Plage inattendue"):
        await make_manager(client)._segment_worker(dl, dl.segments[0], FakeFH())


@async_test
async def test_short_file_write_fails_and_does_not_advance_progress():
    client = FakeClient(FakeStream(headers={"content-range":"bytes 0-4/5", "etag": '"v1"'}))
    dl = make_download()
    class ShortWrite(FakeFH):
        def write(self, chunk):
            return len(chunk) - 1
    with pytest.raises(OSError):
        await make_manager(client)._segment_worker(dl, dl.segments[0], ShortWrite())
    assert dl.downloaded == 0


@async_test
async def test_range_fetch_requires_identity_encoding():
    client = FakeClient(FakeStream(headers={"content-range":"bytes 0-4/5", "etag": '"v1"'}))
    dl = make_download()
    await make_manager(client)._segment_worker(dl, dl.segments[0], FakeFH())
    assert client.headers["Accept-Encoding"] == "identity"


@async_test
async def test_response_cannot_write_past_its_declared_range():
    dl = make_download()
    client = FakeClient(FakeStream(headers={"content-range": "bytes 0-0/5"}, chunks=(b"hello",)))
    class NoWrite(FakeFH):
        def write(self, chunk):
            raise AssertionError("oversized response must be rejected before writing")
    with pytest.raises(engine.ResourceChanged):
        await make_manager(client)._segment_worker(dl, dl.segments[0], NoWrite())
    assert dl.downloaded == 0


@async_test
async def test_dynamic_split_after_request_keeps_original_response_bounds():
    dl = make_download()
    segment = dl.segments[0]
    written = []
    class SplitDuringRequest(FakeStream):
        async def __aenter__(self):
            segment.end = 1  # supervisor assigns the tail to another worker
            return self
    class RecordingFile(FakeFH):
        def write(self, chunk):
            written.append(chunk)
            return len(chunk)
    client = FakeClient(SplitDuringRequest())
    await make_manager(client)._segment_worker(dl, segment, RecordingFile())
    assert client.headers["Range"] == "bytes=0-4"
    assert written == [b"he"]
    assert segment.done == 2


@async_test
async def test_weak_validator_is_not_sent_as_if_range_without_timestamp():
    client = FakeClient(FakeStream(headers={"content-range":"bytes 0-4/5"}))
    dl = make_download()
    dl.etag = 'W/"v1"'
    await make_manager(client)._segment_worker(dl, dl.segments[0], FakeFH())
    assert "If-Range" not in client.headers


@async_test
async def test_empty_opaque_etag_is_a_valid_strong_validator():
    client = FakeClient(FakeStream(headers={"content-range": "bytes 0-4/5"}))
    dl = make_download()
    dl.etag = '""'
    await make_manager(client)._segment_worker(dl, dl.segments[0], FakeFH())
    assert client.headers["If-Range"] == '""'


def test_date_if_range_requires_no_etag_and_sixty_second_age():
    dl = make_download()
    dl.etag = ""
    dl.last_modified = "Wed, 21 Oct 2015 07:28:00 GMT"
    dl.validator_date = "Wed, 21 Oct 2015 07:29:00 GMT"
    assert engine.if_range_validator(dl) == dl.last_modified
    dl.validator_date = "Wed, 21 Oct 2015 07:28:59 GMT"
    assert engine.if_range_validator(dl) == ""
    dl.validator_date = "Wed, 21 Oct 2015 07:29:00 GMT"
    dl.etag = 'W/"v1"'
    assert engine.if_range_validator(dl) == ""
    dl.etag = '"invalid"embedded"'
    assert engine.if_range_validator(dl) == ""


def test_validators_survive_state_roundtrip_and_legacy_history_defaults():
    dl = make_download()
    dl.last_modified = "Wed, 21 Oct 2015 07:28:00 GMT"
    dl.validator_date = "Wed, 21 Oct 2015 07:29:00 GMT"
    restored = engine.Download.from_disk(dl.to_disk())
    assert (restored.etag, restored.last_modified, restored.validator_date) == (
        dl.etag, dl.last_modified, dl.validator_date)
    legacy = engine.Download.from_disk({"id": "legacy", "url": "https://example.org/a"})
    assert engine.if_range_validator(legacy) == ""


@pytest.mark.parametrize("new_etag,expected", [('"v1"', True), ('"v2"', False), (None, False)])
@async_test
async def test_refresh_same_size_partial_requires_same_validator_and_restores_on_rejection(new_etag, expected):
    requests = []

    def response(request):
        requests.append(request)
        headers = {"Content-Range": "bytes 0-0/5", "Last-Modified": "Wed, 21 Oct 2015 07:28:00 GMT",
                   "Date": "Wed, 21 Oct 2015 07:30:00 GMT"}
        if new_etag is not None:
            headers["ETag"] = new_etag
        return httpx.Response(206, headers=headers, content=b"h")

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        manager = make_manager(client)
        dl = make_download(status="downloading")
        dl.segments[0].done = 2
        old = (dl.url, dl.etag, dl.last_modified, dl.validator_date, dl.resumable)
        manager.downloads = {dl.id: dl}
        manager._cancel_task = AsyncMock()
        manager.wake = lambda: None
        url = "https://example.org/refreshed.bin"
        if expected:
            await manager.refresh_address(dl.id, url)
            assert dl.url == url
            assert dl.status == "queued"
        else:
            with pytest.raises(ValueError, match="Identite"):
                await manager.refresh_address(dl.id, url)
            assert (dl.url, dl.etag, dl.last_modified, dl.validator_date, dl.resumable) == old
            assert dl.status == "paused"
        assert dl.downloaded == 2
        assert requests[0].headers["accept-encoding"] == "identity"
        manager._cancel_task.assert_awaited_once_with(dl.id)


@async_test
async def test_refresh_temporarily_removes_queued_download_from_scheduler():
    dl = make_download(status="queued")
    dl.segments[0].done = 2
    manager = make_manager(None)
    manager.downloads = {dl.id: dl}
    manager._cancel_task = AsyncMock()
    manager.wake = lambda: None

    async def probe(current):
        await asyncio.sleep(0)
        assert current.status == "paused"
        return 5, True, "file.bin"

    manager._probe = probe
    await manager.refresh_address(dl.id, "https://example.org/refreshed.bin")
    assert dl.status == "queued"
    assert dl.downloaded == 2


@async_test
async def test_if_range_full_response_is_never_appended_to_partial_file(monkeypatch):
    dl = make_download()
    dl.segments[0].done = 2
    writes = []
    class RecordingFile(FakeFH):
        def write(self, chunk):
            writes.append(chunk)
            return len(chunk)
    client = FakeClient(FakeStream(status=200, headers={"etag": '"v2"'}))
    monkeypatch.setattr(engine, "MAX_RETRIES", 0)
    with pytest.raises(IOError):
        await make_manager(client)._segment_worker(dl, dl.segments[0], RecordingFile())
    assert not writes
    assert dl.downloaded == 2
