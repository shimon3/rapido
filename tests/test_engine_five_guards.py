"""Five downloader regressions: validators, If-Range, disk-full, 429/503."""
import asyncio
import errno
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import engine


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


@pytest.mark.asyncio
async def test_if_range_uses_probed_strong_etag():
    client = FakeClient(FakeStream(headers={"content-range": "bytes 0-4/5", "etag": '"v1"'}))
    dl = make_download()
    await make_manager(client)._segment_worker(dl, dl.segments[0], FakeFH())
    assert client.headers["If-Range"] == '"v1"'
    assert dl.downloaded == 5


@pytest.mark.asyncio
async def test_weak_etag_uses_last_modified_validator():
    client = FakeClient(FakeStream(headers={"content-range": "bytes 0-4/5"}))
    dl = make_download()
    dl.etag = 'W/"v1"'
    dl.last_modified = "Wed, 21 Oct 2015 07:28:00 GMT"
    await make_manager(client)._segment_worker(dl, dl.segments[0], FakeFH())
    assert client.headers["If-Range"] == dl.last_modified


@pytest.mark.asyncio
async def test_mismatched_etag_fails_without_writing():
    client = FakeClient(FakeStream(headers={"content-range": "bytes 0-4/5", "etag": '"v2"'}))
    dl = make_download()
    class NoWrite(FakeFH):
        def write(self, chunk):
            raise AssertionError("must reject changed file before writing")
    with pytest.raises(engine.ResourceChanged):
        await make_manager(client)._segment_worker(dl, dl.segments[0], NoWrite())
    assert dl.downloaded == 0


@pytest.mark.asyncio
async def test_disk_full_aborts_without_retry():
    client = FakeClient(FakeStream())
    dl = make_download()
    class Full(FakeFH):
        def write(self, chunk):
            raise OSError(errno.ENOSPC, "disk full")
    with pytest.raises(OSError) as exc:
        await make_manager(client)._segment_worker(dl, dl.segments[0], Full())
    assert exc.value.errno == errno.ENOSPC


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_rejects_wrong_resource_total_in_content_range():
    client = FakeClient(FakeStream(headers={"content-range":"bytes 0-4/6", "etag": '"v1"'}))
    dl = make_download()
    with pytest.raises(IOError, match="Plage inattendue"):
        await make_manager(client)._segment_worker(dl, dl.segments[0], FakeFH())


@pytest.mark.asyncio
async def test_rejects_reversed_content_range():
    client = FakeClient(FakeStream(headers={"content-range":"bytes 0-0/5", "etag": '"v1"'}))
    dl = make_download()
    # Start offset for the next segment is one, but server responds with zero.
    dl.segments[0].done = 1
    with pytest.raises(IOError, match="Plage inattendue"):
        await make_manager(client)._segment_worker(dl, dl.segments[0], FakeFH())


@pytest.mark.asyncio
async def test_short_file_write_fails_and_does_not_advance_progress():
    client = FakeClient(FakeStream(headers={"content-range":"bytes 0-4/5", "etag": '"v1"'}))
    dl = make_download()
    class ShortWrite(FakeFH):
        def write(self, chunk):
            return len(chunk) - 1
    with pytest.raises(OSError):
        await make_manager(client)._segment_worker(dl, dl.segments[0], ShortWrite())
    assert dl.downloaded == 0


@pytest.mark.asyncio
async def test_range_fetch_requires_identity_encoding():
    client = FakeClient(FakeStream(headers={"content-range":"bytes 0-4/5", "etag": '"v1"'}))
    dl = make_download()
    await make_manager(client)._segment_worker(dl, dl.segments[0], FakeFH())
    assert client.headers["Accept-Encoding"] == "identity"


@pytest.mark.asyncio
async def test_weak_validator_is_not_sent_as_if_range_without_timestamp():
    client = FakeClient(FakeStream(headers={"content-range":"bytes 0-4/5"}))
    dl = make_download()
    dl.etag = 'W/"v1"'
    await make_manager(client)._segment_worker(dl, dl.segments[0], FakeFH())
    assert "If-Range" not in client.headers
