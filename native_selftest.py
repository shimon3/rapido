"""A bounded, persistent stdio session for the packaged-host self-test.

Browsers keep the host alive for successive messages. Do the same in the
self-test, rather than charging seven cold process starts to seven RPC budgets.
This changes only the test client, never the host's peer/origin policy.
"""
import os
import queue
import subprocess
import threading

from native_host import read_message, write_message
from native_diagnostics import event


class NativeHostSession:
    def __init__(self, command, timeout=8):
        self.timeout = timeout
        self._job = None
        if os.name == 'nt':
            from windows_job import _kernel, _create_job
            self._kernel = _kernel()
            self._job = _create_job(self._kernel)
        try:
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            event('session', 'created', child_pid=self.process.pid)
            if self._job is not None:
                handle = self._kernel.OpenProcess(0x0101, False, self.process.pid)
                try:
                    if not handle or not self._kernel.AssignProcessToJobObject(self._job, handle):
                        raise OSError('Cannot scope native selftest helper to its own Windows job')
                    event('session', 'job', child_pid=self.process.pid)
                finally:
                    if handle:
                        self._kernel.CloseHandle(handle)
        except Exception as error:
            event('session', 'job', outcome='error', error=error)
            self._close_job()
            if hasattr(self, 'process') and self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=2)
            raise
        self._lock = threading.Lock()
        self._closed = False
        self._sequence = 0

    def __enter__(self):
        return self

    def request(self, value):
        with self._lock:
            if self._closed:
                raise RuntimeError('Native host session is closed')
            self._sequence += 1
            operation = value.get('type')
            event('session', 'send', operation=operation, sequence=self._sequence,
                  child_pid=self.process.pid, returncode=self.process.poll())
            reply = queue.Queue(maxsize=1)

            def exchange():
                try:
                    write_message(self.process.stdin, value)
                    result = read_message(self.process.stdout)
                    if result is None:
                        raise RuntimeError('Native host closed before replying')
                    reply.put((result, None))
                except Exception as error:
                    reply.put((None, error))

            worker = threading.Thread(target=exchange, name='rapido-selftest-native', daemon=True)
            worker.start()
            try:
                result, error = reply.get(timeout=self.timeout)
            except queue.Empty:
                event('session', 'receive', operation=operation, outcome='timeout', sequence=self._sequence,
                      child_pid=self.process.pid, returncode=self.process.poll())
                self.close(force=True)
                worker.join(timeout=2)
                raise TimeoutError('Packaged native reply timed out') from None
            if error is not None:
                event('session', 'receive', operation=operation, outcome='error', error=error,
                      sequence=self._sequence, child_pid=self.process.pid, returncode=self.process.poll())
                self.close(force=True)
                raise RuntimeError('Invalid packaged native reply') from error
            event('session', 'receive', operation=operation,
                  outcome='error' if result.get('type') == 'error' else 'ok',
                  sequence=self._sequence, child_pid=self.process.pid, returncode=self.process.poll(),
                  response_type=result.get('type'), response_code=result.get('code'))
            return result

    def close(self, force=False):
        if self._closed:
            return
        self._closed = True
        if force:
            self._close_job()
        if force and self.process.poll() is None:
            self.process.kill()
        # Do not close stdin before killing a timed-out writer: BufferedWriter
        # holds its lock while WriteFile is blocked on a host that does not read.
        try:
            self.process.stdin.close()
        except OSError:
            # A killed host cannot consume BufferedWriter's pending bytes.
            # Keep the original timeout/protocol error as the failure reason.
            if not force:
                raise
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._close_job()
            self.process.kill()
            self.process.wait(timeout=2)
        self._close_job()
        self.process.stdout.close()
        event('session', 'exit', child_pid=self.process.pid, returncode=self.process.poll())

    def _close_job(self):
        if self._job is not None:
            # The onefile bootloader's child can inherit stdout. Killing only
            # the launcher would leave communicate/read blocked on that child.
            self._kernel.CloseHandle(self._job)
            self._job = None

    def __exit__(self, kind, value, traceback):
        self.close(force=kind is not None)
