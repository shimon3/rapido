"""Server behaviours seen in the wild, checked end to end with an in-memory transport.

Bodies are streamed: a Response built from bytes cannot be read with aiter_raw,
which the resumable path uses (that would test the mock, not Rapido).
"""
import asyncio
import hashlib
import os
import tempfile
import time
import unittest
from pathlib import Path

import httpx

import engine

DATA = os.urandom(700_000)


def streamed(data):
    async def gen():
        for i in range(0, len(data), 65536):
            yield data[i:i + 65536]
    return gen()


def ranged(request):
    a, b = request.headers["range"].split("=")[1].split("-")
    a, b = int(a), int(b) if b else len(DATA) - 1
    return httpx.Response(206, content=streamed(DATA[a:b + 1]),
                          headers={"Content-Range": f"bytes {a}-{b}/{len(DATA)}", "Content-Length": str(b - a + 1)})


def download(handler, url="https://a.example/file.bin"):
    async def main():
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            data = Path(folder)
            m = engine.Manager(data, port=0)
            m.settings.update(download_dir=str(data / "dl"), show_complete_dialog=False, monitor_clipboard=False)
            await m.start()
            await m.client.aclose()
            m.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
            dl = m.add(url, "file.bin", connections=4)
            try:
                t0 = time.monotonic()
                while m.downloads[dl.id].status not in ("completed", "error"):
                    assert time.monotonic() - t0 < 15, m.downloads[dl.id]
                    await asyncio.sleep(0.02)
                d = m.downloads[dl.id]
                digest = hashlib.sha256(Path(d.path).read_bytes()).digest() if d.status == "completed" else None
                return d, digest
            finally:
                await m.stop()
    return asyncio.run(main())


class HttpEdgeCaseTests(unittest.TestCase):
    expected = hashlib.sha256(DATA).digest()

    def test_unknown_size_chunked_without_range_support(self):
        d, digest = download(lambda request: httpx.Response(200, content=streamed(DATA)))
        self.assertEqual((d.status, d.resumable, digest), ("completed", False, self.expected))

    def test_content_range_with_unknown_total(self):
        def handler(request):
            if request.headers.get("range") == "bytes=0-0":
                return httpx.Response(206, content=streamed(DATA[:1]), headers={"Content-Range": "bytes 0-0/*"})
            return httpx.Response(200, content=streamed(DATA), headers={"Content-Length": str(len(DATA))})
        d, digest = download(handler)
        self.assertEqual((d.status, d.resumable, digest), ("completed", False, self.expected))

    def test_redirect_to_another_host_for_every_range(self):
        hosts = []

        def handler(request):
            hosts.append(request.url.host)
            if request.url.host == "a.example":
                return httpx.Response(302, headers={"Location": "https://b.example/real.bin"})
            return ranged(request)
        d, digest = download(handler)
        self.assertEqual((d.status, d.resumable, digest), ("completed", True, self.expected))
        self.assertIn("b.example", hosts)


if __name__ == "__main__":
    unittest.main()
