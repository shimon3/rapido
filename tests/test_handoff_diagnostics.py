import json
from pathlib import Path
import tempfile
import unittest
from selftest_handoff import check_handoff
import engine


class HandoffDiagnosticsTests(unittest.TestCase):
    def exercise(self, lose_reply=False, extra_record=False):
        rows = {'original': {'status': 'completed', 'ticket': None}}
        counter = 0
        commit_count = 0
        def send(message):
            nonlocal counter, commit_count
            kind = message['type']
            if kind == 'capture_prepare':
                counter += 1
                ticket = 'private-ticket-' + str(counter)
                rows[str(counter)] = {'status': 'handoff', 'ticket': ticket}
                return {'type': 'capture_prepared', 'ticket': ticket}
            identifier = next(key for key, row in rows.items() if row['ticket'] == message['ticket'])
            if kind == 'capture_abort':
                del rows[identifier]
                return {'type': 'capture_aborted', 'ok': True}
            rows[identifier]['status'] = 'pending'
            commit_count += 1
            if extra_record:
                rows['duplicate'] = {'status': 'pending', 'ticket': message['ticket']}
            if lose_reply and commit_count == 2:
                return {'type': 'error', 'code': 'handoff_unavailable'}
            return {'type': 'capture_result', 'ok': True}
        def snapshot(ticket):
            return [dict(id=key, status=row['status'], matching_ticket=bool(ticket) and row['ticket'] == ticket)
                    for key, row in rows.items()]
        result = {}
        identifier = check_handoff(send, snapshot, result, 'http://127.0.0.1:9614/favicon.ico')
        return identifier, result

    def test_success_verifies_all_five_responses_and_state_transitions(self):
        identifier, result = self.exercise()
        self.assertEqual(identifier, '2')
        self.assertTrue(result['native_handoff'])
        self.assertEqual(len(result['handoff_steps']), 5)
        self.assertTrue(all(step['state_ok'] for step in result['handoff_steps']))
        self.assertNotIn('private-ticket', json.dumps(result))

    def test_failed_repeat_reply_remains_failure_but_accepted_file_can_be_checked(self):
        identifier, result = self.exercise(lose_reply=True)
        self.assertEqual(identifier, '2')
        self.assertFalse(result['native_handoff'])
        self.assertEqual(result['handoff_steps'][-1]['stage'], 'commit-repeat')
        self.assertEqual(result['handoff_steps'][-1]['code'], 'handoff_unavailable')
        self.assertNotIn('private-ticket', json.dumps(result))

    def test_duplicate_download_never_passes(self):
        identifier, result = self.exercise(extra_record=True)
        self.assertIsNone(identifier)
        self.assertFalse(result['native_handoff'])

    def test_prepare_failure_is_named_without_sending_invalid_ticket(self):
        calls = []
        result = {}
        def send(message):
            calls.append(message)
            return {'type': 'error', 'code': 'handoff_unavailable'}
        self.assertIsNone(check_handoff(send, lambda _: [], result, 'http://127.0.0.1:9614/favicon.ico'))
        self.assertEqual(len(calls), 1)
        self.assertEqual(result['handoff_steps'][0]['stage'], 'prepare-abort')
        self.assertFalse(result['native_handoff'])


class SettingsBomTests(unittest.TestCase):
    def test_windows_powershell_utf8_bom_settings_are_loaded_without_quarantine(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            path.write_text(json.dumps({'monitor_clipboard': False, 'show_capture_dialog': True}), encoding='utf-8-sig')
            manager = engine.Manager(Path(folder), 9614)
            self.assertIs(manager.settings['monitor_clipboard'], False)
            self.assertTrue(path.exists())
            self.assertEqual(list(Path(folder).glob('*.unreadable-*')), [])
