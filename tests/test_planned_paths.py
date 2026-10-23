"""Two downloads must never be given the same planned path.

yt-dlp creates its .part files seconds after the name is chosen (process start),
so checking only the disk let two same-titled videos share one name.
"""
import tempfile
import unittest
from pathlib import Path

import engine


class PlannedPathTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.manager = engine.Manager(self.root, port=0)

    def video(self, title):
        dl = engine.Download(id=title + str(len(self.manager.downloads)), url="https://v.example/w",
                             kind="video", filename=title + ".mp4", status="downloading")
        self.manager.downloads[dl.id] = dl
        return dl

    def test_same_title_videos_get_different_paths_before_any_file_exists(self):
        first, second = self.video("Titre"), self.video("Titre")
        folder = self.root / "dl"
        first.path = str(self.manager._unused_path(folder, first.filename, first))
        second.path = str(self.manager._unused_path(folder, second.filename, second))
        self.assertNotEqual(first.path, second.path)
        self.assertEqual(Path(second.path).name, "Titre (1).mp4")

    def test_completed_downloads_do_not_reserve_their_name(self):
        done = self.video("Fini")
        done.status, done.path = "completed", str(self.root / "dl" / "Fini.mp4")
        # The file itself is gone (deleted by the user): the name is free again.
        fresh = self.video("Fini")
        self.assertEqual(Path(self.manager._unused_path(self.root / "dl", "Fini.mp4", fresh)).name, "Fini.mp4")

    def test_own_path_is_not_a_conflict(self):
        dl = self.video("Moi")
        dl.path = str(self.root / "dl" / "Moi.mp4")
        self.assertEqual(Path(self.manager._unused_path(self.root / "dl", "Moi.mp4", dl)).name, "Moi.mp4")


if __name__ == "__main__":
    unittest.main()
