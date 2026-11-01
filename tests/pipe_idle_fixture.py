"""Real Windows pipe: place a client in either edge of the idle-cancel race."""
import ctypes
import secrets
import sys
import threading
from unittest.mock import patch


def exercise(pipe, edge, *, stop_on_connection=False):
    gate = threading.Event()
    sent = threading.Event()
    observed = {'edge': edge, 'wait_timeout': False, 'dispatched': [], 'reply': None,
                'client_error': None, 'drain_completed': None, 'drain_winerror': None}
    real_kernel = pipe._kernel
    original_send = pipe._send

    class ServerKernel:
        def __init__(self):
            self.real = real_kernel()
            self.armed = True
            self.draining = False

        def __getattr__(self, name):
            return getattr(self.real, name)

        def WaitForSingleObject(self, event, timeout):
            result = self.real.WaitForSingleObject(event, timeout)
            if result == 258 and self.armed:
                self.armed = False
                observed['wait_timeout'] = True
                if edge == 'completed-before-cancel':
                    gate.set()
                    if not sent.wait(3):
                        raise AssertionError('Fixture client did not send')
                    if stop_on_connection:
                        server._stop.set()
            return result

        def CancelIoEx(self, handle, overlapped):
            self.draining = True
            return self.real.CancelIoEx(handle, overlapped)

        def GetOverlappedResult(self, handle, overlapped, count, wait):
            result = self.real.GetOverlappedResult(handle, overlapped, count, wait)
            error = ctypes.get_last_error()
            if wait and self.draining and observed['drain_completed'] is None:
                observed['drain_completed'] = bool(result)
                observed['drain_winerror'] = None if result else error
                if edge == 'arrived-after-cancel':
                    gate.set()
                    if not sent.wait(3):
                        raise AssertionError('Fixture client did not send')
                    if stop_on_connection:
                        server._stop.set()
            ctypes.set_last_error(error)
            return result

    def kernel():
        return ServerKernel() if threading.current_thread().name == 'rapido-native-pipe' else real_kernel()

    def send(k, handle, value, deadline):
        original_send(k, handle, value, deadline)
        if threading.current_thread().name != 'rapido-native-pipe' and value == {'number': 1}:
            sent.set()

    def handler(_, value):
        observed['dispatched'].append(value)
        return value

    with patch.object(pipe, '_kernel', side_effect=kernel), patch.object(pipe, '_send', side_effect=send):
        server = pipe.PipeServer(handler, clients={sys.executable: 'native'},
                                 name='Rapido-'+secrets.token_hex(12), timeout=1).start()
        try:
            if not gate.wait(3):
                raise AssertionError('Fixture did not reach idle cancellation boundary')
            try:
                observed['reply'] = pipe.request({'number': 1}, server_images=[sys.executable],
                                                  name=server.name, timeout=3)
            except (OSError, ValueError) as error:
                observed['client_error'] = {'type': type(error).__name__,
                    'winerror': getattr(error, 'winerror', None), 'errno': getattr(error, 'errno', None)}
        finally:
            sent.set()
            server.stop()
    observed['server_stopped'] = not server._thread.is_alive()
    return observed
