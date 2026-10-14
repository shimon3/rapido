"""Guard against global image-name kills in installer lifecycle hooks."""
from pathlib import Path
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / "packaging" / "rapido.iss"

class InstallerProcessScopeTests(unittest.TestCase):
    def test_installer_does_not_kill_every_rapido_process(self):
        source = INSTALLER.read_text(encoding="utf-8-sig")
        self.assertNotRegex(source.lower(), r"taskkill(?:\.exe)?")
        self.assertNotRegex(source.lower(), r"/im\s+rapido\.exe")
        self.assertNotIn("PrepareToInstall(", source)
    def test_installer_keeps_restart_manager_and_native_unregistration(self):
        source = INSTALLER.read_text(encoding="utf-8-sig")
        self.assertIn("CloseApplications=force", source)
        self.assertIn("RestartApplications=no", source)
        self.assertIn('--unregister-native-hosts', source)
        self.assertIn('--register-native-hosts', source)

if __name__ == "__main__":
    unittest.main()
