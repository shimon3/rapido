import asyncio
import ctypes
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import engine
import native_diagnostics as diagnostics
import native_handoff
import native_host
import native_pipe
from native_selftest import NativeHostSession

MESSAGE = {'type': 'capture_prepare', 'url': 'https://example.org/a?private=secret',
           'filename': 'a.zip', 'referrer': None}


class NativeDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.env = patch.dict(os.environ, {diagnostics.ENV: self.folder.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def rows(self):
        return [json.loads(line) for path in Path(self.folder.name).glob('*.jsonl')
                for line in path.read_text(encoding='utf-8').splitlines()]

    def test_logs_are_opt_in_and_contain_no_payload_error_message_or_unknown_values(self):
        error = OSError('secret-url Cookie=private')
        error.winerror = 5
        with patch.dict(os.environ, {diagnostics.ENV: ''}):
            self.assertFalse(diagnostics.event('host', 'start'))
        self.assertTrue(diagnostics.event('host', 'reply', operation={'private': 'secret'},
            outcome='error', error=error, url=MESSAGE['url'], ticket='secret-ticket',
            response_code='secret-code', response_type='secret-type'))
        row = self.rows()[0]
        self.assertEqual(row['winerror'], 5)
        self.assertEqual(row['operation'], 'unknown')
        self.assertEqual(row['response_code'], 'unknown')
        self.assertNotIn('secret', json.dumps(row))
        self.assertNotIn('url', row)
        self.assertNotIn('ticket', row)

    def test_prepare_preserves_real_protection_error_and_rolls_back_without_ack(self):
        manager = SimpleNamespace(downloads={}, settings={'connections': 4}, save=Mock())
        error = OSError('DPAPI private=secret')
        error.winerror = 13
        with patch.object(engine, 'IS_WINDOWS', True), patch.object(engine, 'protect', side_effect=error):
            with self.assertRaises(OSError) as raised:
                asyncio.run(native_handoff.dispatch(manager, MESSAGE))
        self.assertIs(raised.exception, error)
        self.assertEqual(manager.downloads, {})
        manager.save.assert_not_called()
        failures = [row for row in self.rows() if row['outcome'] == 'error']
        self.assertEqual(failures[0]['phase'], 'protect')
        self.assertEqual(failures[0]['winerror'], 13)
        self.assertNotIn('private=secret', json.dumps(self.rows()))

    def test_prepare_disk_failure_is_distinct_from_protection_failure(self):
        error = PermissionError('private=secret')
        error.winerror = 32
        manager = SimpleNamespace(downloads={}, settings={'connections': 4}, save=Mock(side_effect=error))
        with patch.object(engine, 'IS_WINDOWS', True), patch.object(engine, 'protect', return_value='sealed'):
            with self.assertRaises(PermissionError):
                asyncio.run(native_handoff.dispatch(manager, MESSAGE))
        self.assertEqual(manager.downloads, {})
        failures = [row for row in self.rows() if row['outcome'] == 'error']
        self.assertEqual(failures[0]['phase'], 'persist')
        self.assertEqual(failures[0]['winerror'], 32)

    def test_host_unavailable_retains_protocol_error_and_logs_original_numeric_cause(self):
        error = OSError('private=secret')
        error.winerror = 233
        with patch.object(native_host, '_native_request', side_effect=error):
            result = native_host.handle_message(MESSAGE)
        self.assertEqual(result, {'type': 'error', 'code': 'handoff_unavailable'})
        failure = [row for row in self.rows() if row['outcome'] == 'error'][0]
        self.assertEqual((failure['component'], failure['phase'], failure['winerror']), ('host', 'dispatch', 233))
        self.assertNotIn('private=secret', json.dumps(self.rows()))

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI error propagation')
    def test_dpapi_retains_actual_windows_error(self):
        def fail(*args):
            ctypes.set_last_error(5)
            return 0
        crypt = SimpleNamespace(CryptProtectData=Mock(side_effect=fail))
        kernel = SimpleNamespace(LocalFree=Mock())
        with patch('engine.ctypes.WinDLL', side_effect=[crypt, kernel]):
            with self.assertRaises(OSError) as raised:
                engine._dpapi(b'private=secret', True)
        self.assertEqual(raised.exception.winerror, 5)
        kernel.LocalFree.assert_not_called()

    def test_diagnostic_write_failure_does_not_change_the_original_exception(self):
        with patch('native_diagnostics.Path.mkdir', side_effect=PermissionError):
            self.assertFalse(diagnostics.event('host', 'start'))
            error = ValueError('private=secret')
            with self.assertRaises(ValueError) as raised:
                with diagnostics.trace('host', 'validate'):
                    raise error
        self.assertIs(raised.exception, error)

    def test_host_stdio_stays_framed_and_records_parent_child_lifetime(self):
        with NativeHostSession([sys.executable, '-u', '-c', 'import native_host; raise SystemExit(native_host.main())']) as host:
            reply = host.request({'type': 'ping'})
            child_pid = host.process.pid
            self.assertEqual(reply, {'type': 'pong', 'protocol': 1})
        rows = self.rows()
        self.assertTrue(any(row['component'] == 'host' and row['phase'] == 'start'
                            and row['pid'] == child_pid and row['ppid'] == os.getpid() for row in rows))
        self.assertTrue(any(row['component'] == 'session' and row['phase'] == 'exit'
                            and row['child_pid'] == child_pid and row['returncode'] == 0 for row in rows))

    @unittest.skipUnless(os.name == 'nt', 'Real authenticated Windows fixture pipe')
    def test_dispatch_failure_is_not_a_success_and_server_can_accept_next_request(self):
        def dispatch(_, value):
            if value['number'] == 0:
                error = OSError('private=secret')
                error.winerror = 5
                raise error
            return {'ok': True}
        server = native_pipe.PipeServer(dispatch, clients={sys.executable: 'native'},
            name='Rapido-'+secrets.token_hex(12), timeout=1).start()
        try:
            with self.assertRaises((ValueError, OSError)):
                native_pipe.request({'number': 0}, server_images=[sys.executable], name=server.name, timeout=2)
            self.assertEqual(native_pipe.request({'number': 1}, server_images=[sys.executable], name=server.name, timeout=2), {'ok': True})
        finally:
            server.stop()
        failures = [row for row in self.rows() if row['component'] == 'server' and row['phase'] == 'dispatch' and row['outcome'] == 'error']
        self.assertEqual(failures[0]['winerror'], 5)
        self.assertNotIn('private=secret', json.dumps(self.rows()))
