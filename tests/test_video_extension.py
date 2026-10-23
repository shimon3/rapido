"""Video extensions come from site metadata: they must never shape a path."""
import tempfile
import unittest
from pathlib import Path

import engine

HOSTILE = [r"mp4\..\..\evil","../x", "mp4:stream", "", None, "m" * 20, "exe "]


class VideoExtensionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(folder.cleanup)
        self.manager = engine.Manager(Path(folder.name), port=0)

    def formats(self, ext):
        return {"duration": 10, "ext": ext, "formats": [
            {"format_id": "18", "height": 360, "vcodec": "avc1", "acodec": "mp4a", "tbr": 500, "ext": ext},
            {"format_id": "140", "vcodec": "none", "acodec": "mp4a", "abr": 128, "ext": ext}]}

    def test_hostile_extensions_never_reach_the_filename(self):
        for ext in HOSTILE:
            with self.subTest(ext=ext):
                options = self.manager._build_formats(self.formats(ext))
                for option in options:
                    self.assertRegex(option["ext"], r"^[A-Za-z0-9]{1,8}$")
                dl = engine.Download(id="v", url="https://video.example/w", kind="video",
                                     filename="Titre.mp4", formats=options)
                for option in options:
                    self.manager.choose_format(dl, option["id"])
                    self.assertNotIn("\\", dl.filename)
                    self.assertNotIn("/", dl.filename)
                    self.assertNotIn("..", dl.filename)
                    self.assertEqual(Path(dl.filename).name, dl.filename)

    def test_normal_extensions_are_kept(self):
        from unittest.mock import patch
        # Without ffmpeg the progressive format keeps the site's own extension.
        with patch.object(self.manager, "ffmpeg", return_value=None):
            options = self.manager._build_formats(self.formats("webm"))
            self.assertEqual([o["ext"] for o in options if o["id"] == "v360"], ["webm"])
            options = self.manager._build_formats(self.formats("mp4"))
            self.assertEqual({o["ext"] for o in options}, {"mp4"})


if __name__ == "__main__":
    unittest.main()
