"""File names chosen for downloads: Windows-safe, short enough, extension kept."""
import unittest

import engine


class SafeFilenameTests(unittest.TestCase):
    def test_forbidden_characters_controls_and_bidi_overrides(self):
        self.assertEqual(engine.safe_filename('a<b>c:d"e/f\\g|h?i*j\x01.txt'), "a_b_c_d_e_f_g_h_i_j_.txt")
        self.assertEqual(engine.safe_filename("photo‮gpj.exe"), "photogpj.exe")

    def test_reserved_device_names_and_empty_names(self):
        self.assertEqual(engine.safe_filename("CON.txt"), "_CON.txt")
        self.assertEqual(engine.safe_filename("nul"), "_nul")
        self.assertEqual(engine.safe_filename(" . . "), "telechargement")

    def test_long_names_keep_their_extension(self):
        for name, suffix in (("a" * 190 + ".zip", ".zip"), ("Rapport " + "z" * 200 + ".tar.gz", ".tar.gz"),
                             ("x" * 300 + ".PDF", ".PDF")):
            with self.subTest(suffix=suffix):
                result = engine.safe_filename(name)
                self.assertLessEqual(len(result), 180)
                self.assertTrue(result.endswith(suffix), result[-20:])
                self.assertEqual(engine.category_for(result), engine.category_for("f" + suffix))

    def test_truncation_never_leaves_a_trailing_space_or_dot(self):
        # Windows silently drops them, so the name on disk would differ from the record.
        for name in ("b" * 179 + " .pdf" + "c" * 20, "c" * 178 + ". " + "d" * 40, "d" * 179 + " " + "e" * 9):
            with self.subTest(name=name[170:]):
                result = engine.safe_filename(name)
                self.assertLessEqual(len(result), 180)
                self.assertFalse(result.endswith((" ", ".")), repr(result[-6:]))

    def test_long_name_without_a_usable_extension_is_cut(self):
        self.assertEqual(engine.safe_filename("y" * 400), "y" * 180)
        result = engine.safe_filename("y" * 200 + ".this-is-not-an-extension")
        self.assertEqual(len(result), 180)

    def test_short_names_are_unchanged(self):
        for name in ("setup.exe", "Rapport 2026.pdf", "archive.tar.gz", "video (1).mp4"):
            self.assertEqual(engine.safe_filename(name), name)


if __name__ == "__main__":
    unittest.main()
