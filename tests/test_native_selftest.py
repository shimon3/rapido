"""Exercise the real stream client with disposable child interpreters."""
import json
import struct
import sys
import os
import time
import unittest

from native_selftest import NativeHostSession


class NativeSessionTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows bootloader process lifetime')
    def test_timeout_closes_descendants_holding_stdout(self):
        source = "import subprocess,sys,time;subprocess.Popen([sys.executable,'-c','import time;time.sleep(2)'],stdout=sys.stdout);time.sleep(2)"
        started = time.monotonic()
        with NativeHostSession(self.command(source), timeout=.2) as host:
            with self.assertRaises(TimeoutError):
                host.request({'type':'ping'})
        self.assertLess(time.monotonic()-started,1.5,'a surviving child kept stdout open past the deadline')

    def command(self, source):
        return [sys.executable, '-u', '-c', source]

    def test_successive_frames_use_one_process_and_eof_exits(self):
        source = '''
import os,sys
from native_host import read_message,write_message
while True:
    value=read_message(sys.stdin.buffer)
    if value is None:break
    write_message(sys.stdout.buffer,dict(pid=os.getpid(),sequence=value['sequence']))
'''
        with NativeHostSession(self.command(source)) as host:
            responses=[host.request({'sequence':n}) for n in range(7)]
            self.assertEqual([r['sequence'] for r in responses],list(range(7)))
            self.assertEqual({r['pid'] for r in responses},{host.process.pid})
        self.assertEqual(host.process.returncode,0)

    def test_truncated_reply_fails_and_reaps_host(self):
        with NativeHostSession(self.command("import sys;sys.stdout.buffer.write(b'\\x05\\0\\0\\0{}');sys.stdout.flush()")) as host:
            with self.assertRaisesRegex(RuntimeError,'Invalid packaged native reply'):
                host.request({'type':'ping'})
            self.assertIsNotNone(host.process.poll())

    def test_oversized_frame_rejected_without_reading_payload(self):
        source="import sys,struct,time;sys.stdout.buffer.write(struct.pack('<I',65537));sys.stdout.flush();time.sleep(30)"
        with NativeHostSession(self.command(source)) as host:
            with self.assertRaisesRegex(RuntimeError,'Invalid packaged native reply'):
                host.request({'type':'ping'})
            self.assertIsNotNone(host.process.poll())

    def test_reply_timeout_reaps_only_its_child_and_session_cannot_be_reused(self):
        with NativeHostSession(self.command('import time;time.sleep(30)'),timeout=.1) as host:
            with self.assertRaisesRegex(TimeoutError,'reply timed out'):
                host.request({'type':'ping'})
            self.assertIsNotNone(host.process.poll())
            with self.assertRaisesRegex(RuntimeError,'session is closed'):
                host.request({'type':'ping'})

    def test_timeout_also_bounds_a_writer_when_host_does_not_read(self):
        with NativeHostSession(self.command('import time;time.sleep(30)'),timeout=.1) as host:
            with self.assertRaises(TimeoutError):
                host.request({'payload':'x'*60000})
            self.assertIsNotNone(host.process.poll())
