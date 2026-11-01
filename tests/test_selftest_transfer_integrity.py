"""Windows 10: accepted native captures stayed pending and cp1255 broke final output."""
import hashlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import desktop


class TransferIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'native-selftest.png'
        self.path.write_bytes(b'expected bytes')
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.completed = {'status': 'completed', 'path': str(self.path), 'size': self.path.stat().st_size}

    def test_pending_capture_is_confirmed_before_waiting_for_completed_bytes(self):
        calls = []
        replies = iter([{'status': 'pending'}, {}, {'status': 'queued'}, self.completed])
        def api(path, body=None):
            calls.append((path, body))
            return next(replies)
        with patch('desktop.api', side_effect=api), patch('desktop.time.sleep'):
            result = desktop.verify_selftest_download('fixture', self.digest, confirm=True)
        self.assertTrue(result['ok'])
        self.assertEqual(result['sha256'], self.digest)
        self.assertEqual(calls[1], ('/api/downloads/fixture/confirm', {}))

    def test_pending_capture_without_confirmation_never_counts_as_downloaded(self):
        with patch('desktop.api', return_value={'status': 'pending'}):
            result = desktop.verify_selftest_download('fixture', self.digest, timeout=0)
        self.assertFalse(result['ok'])
        self.assertIsNone(result['sha256'])

    def test_error_wrong_hash_missing_file_and_wrong_size_fail(self):
        for state, digest in [({**self.completed, 'status': 'error'}, self.digest),
                              (self.completed, '0' * 64),
                              ({**self.completed, 'path': str(self.path) + '.absent'}, self.digest),
                              ({**self.completed, 'size': 9999}, self.digest)]:
            with self.subTest(state=state, digest=digest), patch('desktop.api', return_value=state):
                result = desktop.verify_selftest_download('fixture', digest)
                self.assertFalse(result['ok'])

    def test_confirmation_rejects_unexpected_state(self):
        with patch('desktop.api', return_value={'status': 'handoff'}):
            with self.assertRaisesRegex(RuntimeError, 'Expected pending'):
                desktop.verify_selftest_download('fixture', self.digest, confirm=True)


class OutputAndShutdownTests(unittest.TestCase):
    def test_final_json_round_trips_french_hebrew_and_emoji_on_cp1255(self):
        buffer = io.BytesIO()
        output = io.TextIOWrapper(buffer, encoding='cp1255', errors='strict')
        result = {'ok': True, 'popup_title': 'Téléchargement terminé', 'other': 'שלום 🐈'}
        with patch('sys.stdout', output):
            desktop.print_selftest_result(result)
        self.assertEqual(json.loads(buffer.getvalue().decode('ascii')), result)

    def test_watchdog_stops_without_waiting_for_its_sleep_interval(self):
        posted = threading.Event()
        dog = desktop.UiWatchdog(lambda ack: posted.set(), lambda _: None, interval=60)
        worker = threading.Thread(target=dog.run)
        worker.start()
        try:
            self.assertTrue(posted.wait(2))
        finally:
            dog.stop()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        posted.clear()
        dog.tick()
        self.assertFalse(posted.is_set(), 'no CLR call after shutdown')


if __name__ == '__main__':
    unittest.main()
