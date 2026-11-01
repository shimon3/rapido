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


class NativeHostSession:
    def __init__(self, command, timeout=8):
        self.timeout = timeout
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self._lock = threading.Lock()
        self._closed = False

    def __enter__(self):
        return self

    def request(self, value):
        with self._lock:
            if self._closed:
                raise RuntimeError('Native host session is closed')
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
                self.close(force=True)
                worker.join(timeout=2)
                raise TimeoutError('Packaged native reply timed out') from None
            if error is not None:
                self.close(force=True)
                raise RuntimeError('Invalid packaged native reply') from error
            return result

    def close(self, force=False):
        if self._closed:
            return
        self._closed = True
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
            self.process.kill()
            self.process.wait(timeout=2)
        self.process.stdout.close()

    def __exit__(self, kind, value, traceback):
        self.close(force=kind is not None)
