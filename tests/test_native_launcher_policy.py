"""Launcher origin, PID reuse and same-user peer checks."""
import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch
from windows_peer import ProcessIdentity
from native_launcher import trusted_launcher, valid_origin, CHROMIUM_ORIGIN, FIREFOX_ID, parent_pid

EXE=r"C:\Rapido\RapidoNativeHost.exe"
APP=r"C:\Rapido\Rapido.exe"
SID="S-1-5-21-111-222-333-1001"


class LauncherPolicyTests(unittest.TestCase):
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

    def run_chain(self, parent, args=None):
        child=ProcessIdentity(100,SID,r"c:\rapido\rapidonativehost.exe",200)
        @contextmanager
        def inspect(pid):
            yield child if pid==os.getpid() else parent
        with patch("native_launcher.inspect_process",inspect),patch("native_launcher.parent_pid",return_value=200):
            with trusted_launcher(EXE,args or []) as role:
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

    @unittest.skipUnless(os.name=="nt","Actual Windows parent PID")
    def test_parent_pid_is_kernel_derived(self):
        self.assertEqual(parent_pid(os.getpid()),os.getppid())


if __name__=="__main__":
    unittest.main()
