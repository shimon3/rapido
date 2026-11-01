import os
import unittest
import ctypes
from unittest.mock import Mock
import native_pipe
from pipe_idle_fixture import exercise


@unittest.skipUnless(os.name == 'nt', 'Real authenticated Windows pipe')
class IdleConnectRaceTests(unittest.TestCase):
    def test_completed_connect_is_not_discarded_when_cancel_loses_race(self):
        result = exercise(native_pipe, 'completed-before-cancel')
        self.assertTrue(result['wait_timeout'])
        self.assertTrue(result['drain_completed'])
        self.assertIsNone(result['client_error'], result)
        self.assertEqual(result['reply'], {'number': 1})
        self.assertEqual(result['dispatched'], [{'number': 1}], 'never replay the mutation')

    def test_idle_cancel_does_not_disconnect_a_new_client_before_next_accept(self):
        result = exercise(native_pipe, 'arrived-after-cancel')
        self.assertTrue(result['wait_timeout'])
        self.assertFalse(result['drain_completed'])
        self.assertEqual(result['drain_winerror'], 995)
        self.assertIsNone(result['client_error'], result)
        self.assertEqual(result['reply'], {'number': 1})
        self.assertEqual(result['dispatched'], [{'number': 1}])

    def test_shutdown_still_rejects_a_client_at_the_same_boundary(self):
        result = exercise(native_pipe, 'completed-before-cancel', stop_on_connection=True)
        self.assertIsNone(result['reply'])
        self.assertIsNotNone(result['client_error'])
        self.assertEqual(result['dispatched'], [])
        self.assertTrue(result['server_stopped'])


@unittest.skipUnless(os.name == 'nt', 'Windows overlapped completion semantics')
class CompletionStatusTests(unittest.TestCase):
    def kernel(self, *, completed, completion_error=995, wait_result=258, wait_error=0):
        class Kernel:
            CreateEventW = Mock(return_value=1)
            CloseHandle = Mock(return_value=True)
            def pending(self, *args):
                ctypes.set_last_error(997)
                return False
            ConnectNamedPipe = pending
            def ReadFile(self, *args):
                return self.pending(*args)
            def WaitForSingleObject(self, *args):
                ctypes.set_last_error(wait_error)
                return wait_result
            def CancelIoEx(self, *args):
                ctypes.set_last_error(1168)
                return False
            def GetOverlappedResult(self, *args):
                ctypes.set_last_error(0 if completed else completion_error)
                return completed
        return Kernel()

    def test_actual_rpc_read_deadline_is_not_relaxed_by_late_success(self):
        kernel = self.kernel(completed=True)
        with self.assertRaises(TimeoutError):
            native_pipe._operation(kernel, 1, native_pipe._deadline(.1), kernel.ReadFile)

    def test_idle_connect_uses_completion_even_when_cancel_request_was_accepted(self):
        kernel = self.kernel(completed=True)
        kernel.CancelIoEx = Mock(return_value=True)
        self.assertEqual(native_pipe._operation(kernel, 1, native_pipe._deadline(.1), kernel.ConnectNamedPipe), 0)

    def test_real_io_failure_is_preserved_instead_of_masked_as_timeout(self):
        kernel = self.kernel(completed=False, completion_error=233)
        with self.assertRaises(OSError) as error:
            native_pipe._operation(kernel, 1, native_pipe._deadline(.1), kernel.ConnectNamedPipe)
        self.assertEqual(error.exception.winerror, 233)

    def test_wait_failure_keeps_its_own_error_not_the_cancellation_error(self):
        kernel = self.kernel(completed=False, wait_result=0xffffffff, wait_error=6)
        with self.assertRaises(OSError) as error:
            native_pipe._operation(kernel, 1, native_pipe._deadline(.1), kernel.ConnectNamedPipe)
        self.assertEqual(error.exception.winerror, 6)
