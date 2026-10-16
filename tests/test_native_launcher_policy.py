"""Launcher origin, PID reuse and same-user peer checks."""
import os
import tempfile
import unittest
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch
from windows_peer import ProcessIdentity
from native_launcher import trusted_launcher, valid_origin, CHROMIUM_ORIGIN, FIREFOX_ID, parent_pid, browser_images

EXE=r"C:\Rapido\RapidoNativeHost.exe"
APP=r"C:\Rapido\Rapido.exe"
SID="S-1-5-21-111-222-333-1001"
CMD=r"c:\windows\system32\cmd.exe"
EDGE=r"c:\program files (x86)\microsoft\edge\application\msedge.exe"
FIREFOX=r"c:\program files\mozilla firefox\firefox.exe"


class LauncherPolicyTests(unittest.TestCase):
    def test_browser_allowlist_runs_known_folder_conversion(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from windows_peer import canonical_image
        def folder(hwnd, identifier, token, flags, output):
            output.value = r"C:\Users\fixture\AppData\Local" if identifier == 0x1c else r"C:\Program Files"
            return 0
        function = Mock(side_effect=folder)
        with patch("native_launcher.ctypes.WinDLL", create=True,
                   return_value=SimpleNamespace(SHGetFolderPathW=function)):
            images = browser_images()
        self.assertEqual(images[canonical_image(r"C:\Program Files\Mozilla Firefox\firefox.exe")], "firefox")
        self.assertEqual(images[canonical_image(r"C:\Users\fixture\AppData\Local\Google\Chrome\Application\chrome.exe")], "chromium")
        self.assertEqual([call.args[1] for call in function.call_args_list], [0x26, 0x2a, 0x1c])

    @unittest.skipUnless(os.name == "nt", "Actual Windows known folders")
    def test_real_windows_browser_allowlist_is_available_without_running_browsers(self):
        import ntpath
        images = browser_images()
        self.assertGreaterEqual(len(images), 6)
        self.assertEqual(set(images.values()), {"chromium", "firefox"})
        self.assertTrue(all(ntpath.isabs(path) for path in images))

    def test_chromium_and_firefox_origins_are_exact(self):
        self.assertTrue(valid_origin("chromium",[CHROMIUM_ORIGIN],EXE))
        self.assertTrue(valid_origin("chromium",[CHROMIUM_ORIGIN,"--parent-window=0"],EXE))
        for args in ([],["chrome-extension://wrong/"],[CHROMIUM_ORIGIN+"other"],
                     [CHROMIUM_ORIGIN,"--execute"],[CHROMIUM_ORIGIN,"--parent-window=invalid"]):
            self.assertFalse(valid_origin("chromium",args,EXE))
        # Path is a Windows path; native CI runs Windows, normalize fixture via Path.
        import ntpath
        if os.name=="nt":
            self.assertTrue(valid_origin("firefox",[r"C:\Rapido\rapido-native-firefox.json",FIREFOX_ID],EXE))
            self.assertFalse(valid_origin("firefox",[r"C:\Other\rapido-native-firefox.json",FIREFOX_ID],EXE))
        self.assertFalse(valid_origin("desktop",[CHROMIUM_ORIGIN],EXE))

    def test_firefox_rejects_linked_manifest_even_with_expected_path(self):
        # Link detection is independent of lexical manifest path validation.
        with patch("native_paths.Path.is_symlink", return_value=True):
            self.assertFalse(valid_origin("firefox", [r"C:\Rapido\rapido-native-firefox.json", FIREFOX_ID], EXE))

    def test_rejects_linked_native_helper_or_desktop_path(self):
        parent = ProcessIdentity(200, SID, r"c:\rapido\rapido.exe", 100)
        for linked in (EXE, APP):
            original = os.path.normcase(os.path.abspath(linked))
            def linked_path(path):
                return os.path.normcase(str(path)) == original
            with patch("native_paths.Path.is_symlink", autospec=True,
                       side_effect=linked_path):
                with self.assertRaises(PermissionError):
                    self.run_chain(parent)

    def run_chain(self, parent, args=None, executable=EXE, desktop_image=None):
        child=ProcessIdentity(100,SID,r"c:\rapido\rapidonativehost.exe",200)
        @contextmanager
        def inspect(pid):
            yield child if pid==os.getpid() else parent
        with patch("native_launcher.inspect_process",inspect),patch("native_launcher.parent_pid",return_value=200):
            with trusted_launcher(executable,args or [],desktop_image=desktop_image) as role:
                return role

    def test_trusted_desktop_parent(self):
        self.assertEqual(self.run_chain(ProcessIdentity(200,SID,r"c:\rapido\rapido.exe",100)),"desktop")

    def test_other_user_late_reused_pid_and_arbitrary_image_are_rejected(self):
        for parent in (ProcessIdentity(200,"S-1-5-21-1-2-3-1002",r"c:\rapido\rapido.exe",100),
                       ProcessIdentity(200,SID,r"c:\rapido\rapido.exe",300),
                       ProcessIdentity(200,SID,r"c:\malware\caller.exe",100)):
            with patch("native_launcher.browser_images",return_value={}):
                with self.assertRaises(PermissionError):
                    self.run_chain(parent)

    def test_linked_install_ancestor_denies_capture_before_pipe_request(self):
        import native_host
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            target = root / "target"
            target.mkdir()
            alias = root / "alias"
            try:
                alias.symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("Directory symlink creation not permitted")
            self.assertFalse((alias / "RapidoNativeHost.exe").is_symlink())
            with patch.object(native_host.sys, "frozen", True, create=True), \
                    patch.object(native_host.sys, "executable", str(alias / "RapidoNativeHost.exe")), \
                    patch("native_launcher.canonical_image", side_effect=lambda path: str(path).lower()), \
                    patch("native_launcher.inspect_process", side_effect=AssertionError("identity inspected before link refusal")) as inspect, \
                    patch("native_pipe.request") as request:
                self.assertEqual(native_host.handle_message({
                    "type": "capture_public", "url": "https://example.com/file",
                    "referrer": None, "filename": None,
                }), {"type": "error", "code": "rapido_unavailable"})
                inspect.assert_not_called()
                request.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Real Windows junctions")
    def test_real_junctions_rejected_for_helper_desktop_and_firefox_manifest(self):
        import subprocess
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            target = root / "target"
            target.mkdir()
            for name in ("RapidoNativeHost.exe", "Rapido.exe", "firefox.exe", "rapido-native-firefox.json"):
                (target / name).touch()
            alias = root / "alias"
            subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(alias), str(target)],
                           capture_output=True, text=True, check=True, timeout=10)
            try:
                self.assertTrue(alias.is_junction())
                self.assertFalse((alias / "Rapido.exe").is_symlink())
                for helper, desktop in (
                    (alias / "RapidoNativeHost.exe", target / "Rapido.exe"),
                    (target / "RapidoNativeHost.exe", alias / "Rapido.exe"),
                ):
                    with self.subTest(helper=helper, desktop=desktop), \
                            patch("native_launcher.inspect_process") as inspect:
                        with self.assertRaises(PermissionError):
                            with trusted_launcher(str(helper), [], desktop_image=str(desktop)):
                                self.fail("junction launcher admitted")
                        inspect.assert_not_called()
                self.assertFalse(valid_origin("firefox", [
                    str(alias / "rapido-native-firefox.json"), FIREFOX_ID,
                ], str(alias / "RapidoNativeHost.exe")))
                from windows_peer import canonical_image
                browser = canonical_image(str(alias / "firefox.exe"))
                with patch("native_launcher.browser_images", return_value={browser: "firefox"}):
                    with self.assertRaisesRegex(PermissionError, "Linked browser"):
                        self.run_chain(ProcessIdentity(200, SID, browser, 100),
                                       executable=str(target / "RapidoNativeHost.exe"),
                                       desktop_image=str(target / "Rapido.exe"))
            finally:
                alias.rmdir()

    def run_ancestry(self, ancestors, args, images=None):
        # ancestors: identities from the helper's parent upward (pid 200, 300, ...).
        chain=[ProcessIdentity(100,SID,r"c:\rapido\rapidonativehost.exe",500)]+list(ancestors)
        by_pid={item.pid:item for item in chain}
        @contextmanager
        def inspect(pid):
            yield chain[0] if pid==os.getpid() else by_pid[pid]
        def parent(pid):
            pid=chain[0].pid if pid==os.getpid() else pid
            index=[item.pid for item in chain].index(pid)
            if index+1>=len(chain):
                raise PermissionError("Launcher process disappeared")
            return chain[index+1].pid
        images=images or {EDGE:"chromium",FIREFOX:"firefox"}
        with patch("native_launcher.inspect_process",inspect),patch("native_launcher.parent_pid",parent), \
                patch("native_launcher.browser_images",return_value=images), \
                patch("native_launcher.command_shell_image",return_value=CMD):
            with trusted_launcher(EXE,args) as role:
                return role

    def test_chromium_cmd_relay_from_recognized_browser_is_admitted(self):
        # Observed on Windows 10 22H2 with Edge 155: msedge -> cmd /d /s /c -> bootloader -> helper.
        chain=[ProcessIdentity(200,SID,r"c:\rapido\rapidonativehost.exe",400),
               ProcessIdentity(300,SID,CMD,300),
               ProcessIdentity(400,SID,EDGE,100)]
        self.assertEqual(self.run_ancestry(chain,[CHROMIUM_ORIGIN,"--parent-window=0"]),"chromium")
        self.assertEqual(self.run_ancestry(chain[1:],[CHROMIUM_ORIGIN]),"chromium")

    def test_cmd_relay_is_rejected_outside_the_exact_chromium_shape(self):
        helper=ProcessIdentity(200,SID,r"c:\rapido\rapidonativehost.exe",400)
        shell=ProcessIdentity(300,SID,CMD,300)
        cases={
            "explorer above cmd":[helper,shell,ProcessIdentity(400,SID,r"c:\windows\explorer.exe",100)],
            "firefox above cmd":[helper,shell,ProcessIdentity(400,SID,FIREFOX,100)],
            "copied cmd":[helper,ProcessIdentity(300,SID,r"c:\users\fixture\cmd.exe",300),ProcessIdentity(400,SID,EDGE,100)],
            "two cmd relays":[helper,shell,ProcessIdentity(350,SID,CMD,200),ProcessIdentity(400,SID,EDGE,100)],
            "desktop above cmd":[helper,shell,ProcessIdentity(400,SID,r"c:\rapido\rapido.exe",100)],
            "helper above cmd":[helper,shell,ProcessIdentity(400,SID,r"c:\rapido\rapidonativehost.exe",100)],
            "other user cmd":[helper,ProcessIdentity(300,"S-1-5-21-1-2-3-1002",CMD,300),ProcessIdentity(400,SID,EDGE,100)],
            "cmd newer than child":[helper,ProcessIdentity(300,SID,CMD,450),ProcessIdentity(400,SID,EDGE,100)],
            "browser newer than cmd":[helper,shell,ProcessIdentity(400,SID,EDGE,350)],
            "cmd without browser":[helper,shell],
        }
        for name,chain in cases.items():
            with self.subTest(name), self.assertRaises(PermissionError):
                self.run_ancestry(chain,[CHROMIUM_ORIGIN])
        with self.assertRaises(PermissionError):
            self.run_ancestry([helper,shell,ProcessIdentity(400,SID,EDGE,100)],["chrome-extension://wrong/"])
        with self.assertRaises(PermissionError):
            self.run_ancestry([helper,shell,ProcessIdentity(400,SID,FIREFOX,100)],
                              [r"C:\Rapido\rapido-native-firefox.json",FIREFOX_ID])

    def test_unknown_command_shell_location_fails_closed(self):
        chain=[ProcessIdentity(300,SID,CMD,300),ProcessIdentity(400,SID,EDGE,100)]
        with patch("native_launcher.command_shell_image",side_effect=OSError("unavailable")):
            with self.assertRaises(PermissionError):
                child=ProcessIdentity(100,SID,r"c:\rapido\rapidonativehost.exe",500)
                by_pid={300:chain[0],400:chain[1]}
                @contextmanager
                def inspect(pid):
                    yield child if pid==os.getpid() else by_pid[pid]
                with patch("native_launcher.inspect_process",inspect), \
                        patch("native_launcher.parent_pid",side_effect=lambda pid: 300 if pid==100 else 400), \
                        patch("native_launcher.browser_images",return_value={EDGE:"chromium"}):
                    with trusted_launcher(EXE,[CHROMIUM_ORIGIN]):
                        self.fail("relay admitted without a known System32 path")

    @unittest.skipUnless(os.name == "nt", "Actual Windows System32 known folder")
    def test_real_command_shell_is_system32_cmd(self):
        import ntpath
        from native_launcher import command_shell_image
        shell = command_shell_image()
        self.assertTrue(ntpath.isabs(shell))
        self.assertEqual(ntpath.basename(shell), "cmd.exe")
        self.assertEqual(ntpath.basename(ntpath.dirname(shell)), "system32")
        self.assertTrue(os.path.isfile(shell))

    @unittest.skipUnless(os.name=="nt","Actual Windows parent PID")
    def test_parent_pid_is_kernel_derived(self):
        self.assertEqual(parent_pid(os.getpid()),os.getppid())


if __name__=="__main__":
    unittest.main()
