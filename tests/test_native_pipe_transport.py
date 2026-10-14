"""Named-pipe tests: real IPC requires an unrestricted Windows token.

AppContainer-only LOCAL pipes cannot validate the ordinary desktop channel.
Do not expand the production DACL merely to accommodate the test sandbox.
"""
import ctypes
import os
import secrets
import struct
import sys
import time
import unittest
from unittest.mock import patch
import native_pipe


def _appcontainer():
    if os.name != "nt":
        return False
    from ctypes import wintypes
    from windows_peer import _windows
    k, a = _windows()
    process = k.OpenProcess(0x1000, False, os.getpid())
    if not process:
        raise ctypes.WinError(ctypes.get_last_error())
    token = wintypes.HANDLE()
    try:
        if not a.OpenProcessToken(process, 8, ctypes.byref(token)):
            raise ctypes.WinError(ctypes.get_last_error())
        value, size = wintypes.DWORD(), wintypes.DWORD()
        if not a.GetTokenInformation(token, 29, ctypes.byref(value), 4, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return bool(value.value)
    finally:
        if token.value:
            k.CloseHandle(token)
        k.CloseHandle(process)


class FramePolicyTests(unittest.TestCase):
    def test_timeout_limits(self):
        for value in (0, -1, 16, True, None, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                native_pipe._deadline(value)
        self.assertGreater(native_pipe._deadline(1), time.monotonic())

    def test_invalid_frames_reject_before_reading_payload(self):
        for size in (0, native_pipe.MAX_FRAME + 1):
            with patch("native_pipe._read", return_value=struct.pack("<I", size)) as reader:
                with self.assertRaises(ValueError):
                    native_pipe._receive(None, None, 0)
                self.assertEqual(reader.call_count, 1)

    def test_duplicate_keys_constants_and_non_objects_rejected(self):
        for payload in (b'{"type":"ping","type":"capture_public"}',
                        b'{"number":NaN}', b'[]', b'null', b'{"x":Infinity}'):
            with patch("native_pipe._read", side_effect=[struct.pack("<I",len(payload)),payload]):
                with self.assertRaises(ValueError):
                    native_pipe._receive(None, None, 0)

    def test_valid_json_frame(self):
        payload = b'{"type":"ping"}'
        with patch("native_pipe._read", side_effect=[struct.pack("<I",len(payload)),payload]):
            self.assertEqual(native_pipe._receive(None, None, 0), {"type":"ping"})

    def test_invalid_roles_and_client_paths_fail_closed(self):
        for clients in ({}, {"Rapido.exe":"native"}, {r"C:\Rapido.exe":""}):
            with self.assertRaises(ValueError):
                native_pipe.PipeServer(lambda *_: {}, clients=clients)


@unittest.skipUnless(os.name == "nt" and not _appcontainer(),
                     "Ordinary Windows named pipes require a non-AppContainer runner")
class RealWindowsPipeTests(unittest.TestCase):
    def server(self, handler=None, clients=None, timeout=1):
        server = native_pipe.PipeServer(handler or (lambda role, message: {"role":role,"value":message}),
            clients=clients or {sys.executable:"native"}, name="Rapido-"+secrets.token_hex(12),
            timeout=timeout).start()
        self.addCleanup(server.stop)
        return server

    def test_authenticated_roundtrip_and_reconnection(self):
        server = self.server()
        for number in range(3):
            result = native_pipe.request({"number":number}, server_images=[sys.executable],
                                          name=server.name, timeout=3)
            self.assertEqual(result, {"role":"native","value":{"number":number}})

    def test_untrusted_server_is_rejected_before_payload(self):
        received = []
        server = self.server(lambda role, msg: received.append(msg) or {"ok":True})
        with self.assertRaises(PermissionError):
            native_pipe.request({"url":"https://example.org/private-token"},
                server_images=[r"C:\NotRapido.exe"], name=server.name, timeout=2)
        self.assertEqual(received, [])

    def test_untrusted_client_never_dispatches(self):
        received = []
        server = self.server(lambda role, msg: received.append(msg) or {"ok":True},
                             clients={r"C:\NotRapido.exe":"native"})
        with self.assertRaises((OSError, TimeoutError, ValueError)):
            native_pipe.request({"type":"capture_public"}, server_images=[sys.executable],
                                name=server.name, timeout=2)
        self.assertEqual(received, [])

    def test_first_instance_collision_does_not_replace_server(self):
        server = self.server()
        collision = native_pipe.PipeServer(lambda *_: {"fake":True},
            clients={sys.executable:"native"}, name=server.name)
        with self.assertRaises(OSError):
            collision.start()
        result = native_pipe.request({"type":"ping"}, server_images=[sys.executable],
                                      name=server.name, timeout=3)
        self.assertEqual(result["role"], "native")

    def test_missing_server_is_bounded(self):
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            native_pipe.request({}, server_images=[sys.executable],
                                name="Rapido-"+secrets.token_hex(12), timeout=.1)
        self.assertLess(time.monotonic()-started, 1)

    def test_idle_connection_does_not_permanently_block_server(self):
        server = self.server(timeout=.2)
        k = native_pipe._kernel()
        handle = k.CreateFileW(native_pipe.validate_pipe_name(server.name), 0x100003, 0,
                               None, 3, 0x40000000 | 0x100000 | 0x10000, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            time.sleep(.4)
        finally:
            k.CloseHandle(handle)
        result = native_pipe.request({"type":"ping"}, server_images=[sys.executable],
                                      name=server.name, timeout=3)
        self.assertEqual(result["role"], "native")


if __name__ == "__main__":
    unittest.main()
