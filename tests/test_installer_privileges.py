"""The installer must stay a per-user install that never asks for elevation.

A Windows 10 run showed a UAC prompt (docs/private-beta/validation-win10-20261018.md,
check B1). The cause is not established; these checks keep the script itself
from being the cause.
"""
from pathlib import Path
import re
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / "packaging" / "rapido.iss"


def _source():
    return INSTALLER.read_text(encoding="utf-8-sig")


def _setup_directives(source):
    section = re.search(r"(?ms)^\[Setup\]\s*$(.*?)^\[", source).group(1)
    result = {}
    for line in section.splitlines():
        line = line.strip()
        if line and not line.startswith(";") and "=" in line:
            key, value = line.split("=", 1)
            result[key.strip().lower()] = value.strip()
    return result


class InstallerPrivilegeTests(unittest.TestCase):
    def test_per_user_install_without_elevation_or_override(self):
        setup = _setup_directives(_source())
        self.assertEqual(setup.get("privilegesrequired"), "lowest")
        # An override would let Setup offer or perform an all-users (elevated) install.
        self.assertNotIn("privilegesrequiredoverridesallowed", setup)
        self.assertTrue(setup["defaultdirname"].startswith("{localappdata}\\"))
        self.assertNotIn("usedpreviousprivileges", setup)

    def test_no_machine_wide_locations_or_registry(self):
        source = _source().lower()
        for constant in ("{pf}", "{pf32}", "{pf64}", "{commonpf", "{commonappdata}", "{sys}",
                         "{syswow64}", "{win}", "{commonstartup}", "{commondesktop}",
                         "{commonprograms}", "{group}\\..", "{autopf}"):
            self.assertNotIn(constant, source, constant)
        self.assertNotRegex(source, r"root:\s*hk(lm|cr|u64|lm32|lm64|a)\b")
        self.assertNotIn("hkey_local_machine", source)
        self.assertNotRegex(source, r"\bregwrite\w*\(\s*hklm")

    def test_post_install_launch_runs_as_the_original_user(self):
        source = _source()
        run = re.search(r"(?ms)^\[Run\]\s*$(.*?)^\[", source).group(1)
        self.assertIn("postinstall", run)
        # postinstall entries default to runasoriginaluser; never override it.
        self.assertNotIn("runascurrentuser", source.lower())
        self.assertNotIn("shellexec", run.lower())


if __name__ == "__main__":
    unittest.main()
