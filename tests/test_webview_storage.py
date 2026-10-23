r"""WebView2 data goes to one fixed Rapido folder instead of a new %TEMP%\tmp*\EBWebView.

Without storage_path, pywebview 6.2.1 gives every start a fresh temporary
folder and often fails to delete it (dozens of folders, hundreds of MB, on a test PC).
"""
import inspect
import os
import tempfile
import unittest
from pathlib import Path

import desktop


class WebViewStorageTests(unittest.TestCase):
    def test_storage_is_a_dedicated_child_of_the_rapido_data_folder(self):
        data = Path(tempfile.gettempdir()) / "rapido-data-example"
        storage = Path(desktop.webview_storage(data))
        self.assertEqual(storage.parent, data)
        self.assertNotEqual(storage, data, "pywebview deletes this folder when Rapido closes")
        self.assertEqual(storage.name, "WebView2")

    def test_same_folder_every_start(self):
        data = Path("C:/Users/someone/.rapido")
        self.assertEqual(desktop.webview_storage(data), desktop.webview_storage(Path(str(data))))

    def test_desktop_starts_webview_private_with_that_folder(self):
        source = inspect.getsource(desktop.main)
        self.assertIn("webview.start(on_start, private_mode=True, storage_path=webview_storage(data_dir))", source)
        self.assertNotIn("webview.start(on_start, private_mode=True)\n", source)


if __name__ == "__main__":
    unittest.main()
