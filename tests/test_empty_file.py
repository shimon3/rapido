"""A 0-byte file: servers such as nginx answer the bytes=0-0 probe with 416 */0."""
import asyncio
import tempfile
import time
import unittest
from pathlib import Path

import httpx

import engine


def run(handler, url="https://files.example/empty.txt"):
    async def main():
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            data = Path(folder)
            m = engine.Manager(data, port=0)
            m.settings.update(download_dir=str(data / "dl"), show_complete_dialog=False, monitor_clipboard=False)
            await m.start()
            await m.client.aclose()
            m.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            dl = m.add(url, "empty.txt", connections=4)
            try:
                t0 = time.monotonic()
                while m.downloads[dl.id].status not in ("completed", "error"):
                    assert time.monotonic() - t0 < 10
                    await asyncio.sleep(0.02)
                d = m.downloads[dl.id]
                content = Path(d.path).read_bytes() if d.status == "completed" else None
                return d.status, d.error, d.size, content
            finally:
                await m.stop()
    return asyncio.run(main())


class EmptyFileTests(unittest.TestCase):
    def test_empty_file_answered_416_is_downloaded(self):
        def handler(request):
            if request.headers.get("range"):
                return httpx.Response(416, headers={"Content-Range": "bytes */0"})
            return httpx.Response(200, content=b"", headers={"Content-Length": "0"})
        status, error, size, content = run(handler)
        self.assertEqual((status, error), ("completed", ""))
        self.assertEqual((size, content), (0, b""))

    def test_other_416_answers_are_still_errors(self):
        def handler(request):
            return httpx.Response(416, headers={"Content-Range": "bytes */1000"})
        status, error, _, _ = run(handler)
        self.assertEqual(status, "error")
        self.assertIn("416", error)


if __name__ == "__main__":
    unittest.main()
