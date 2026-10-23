"""Every Python file compiles without warnings (invalid escapes become errors in future Pythons)."""
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = sorted([*ROOT.glob("*.py"), *ROOT.glob("scripts/*.py"), *ROOT.glob("tests/*.py"),
                  *ROOT.glob("packaging/*.py")])


class SourceHygieneTests(unittest.TestCase):
    def test_sources_compile_without_warnings(self):
        self.assertGreater(len(SOURCES), 50)
        for path in SOURCES:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                with warnings.catch_warnings():
                    warnings.simplefilter("error")
                    compile(path.read_text(encoding="utf-8"), str(path), "exec")


if __name__ == "__main__":
    unittest.main()
