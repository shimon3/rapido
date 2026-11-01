"""Opt-in numeric native diagnostics. Never log messages, URLs, paths or tickets."""
import json
import os
from pathlib import Path
import threading
import time
from contextlib import contextmanager

ENV = 'RAPIDO_NATIVE_DIAGNOSTICS'
_lock = threading.Lock()
_components = {'host', 'client', 'server', 'handoff', 'session', 'manager', 'dpapi'}
_phases = {'start', 'created', 'connect', 'peer', 'send', 'receive', 'ack', 'dispatch',
           'protect', 'persist', 'rollback', 'prepare', 'commit', 'abort', 'stop',
           'reply', 'validate', 'launcher', 'wait', 'loop', 'job', 'exit', 'ready',
           'parent', 'origin', 'paths', 'cancel', 'disconnect'}
_operations = {'capabilities', 'settings_public', 'capture_public', 'capture_prepare',
               'capture_commit', 'capture_abort', 'show', 'ping'}
_outcomes = {'begin', 'ok', 'error', 'closed', 'timeout', 'rollback', 'returned'}
_numbers = {'sequence', 'peer_pid', 'child_pid', 'returncode', 'elapsed_ms', 'remaining_ms',
            'records', 'prepared', 'attempt', 'errno', 'winerror', 'same_user', 'creation_order_ok'}
_error_types = {'OSError', 'PermissionError', 'TimeoutError', 'ValueError', 'TypeError',
                'RuntimeError', 'BrokenPipeError', 'ConnectionResetError', 'FileNotFoundError',
                'JSONDecodeError', 'ConnectionAbortedError', 'AttributeError'}


def event(component, phase, *, operation=None, outcome='ok', error=None, **numbers):
    folder = os.environ.get(ENV)
    if not folder:
        return False
    if component not in _components or phase not in _phases or outcome not in _outcomes:
        raise ValueError('Unknown diagnostic category')
    row = {'pid': os.getpid(), 'ppid': os.getppid(), 'thread': threading.get_ident(),
           'monotonic': time.monotonic(), 'component': component, 'phase': phase,
           'operation': operation if isinstance(operation, str) and operation in _operations else 'unknown', 'outcome': outcome}
    for key, value in numbers.items():
        if key in _numbers and (value is None or type(value) in (int, float)):
            row[key] = value
        elif key == 'response_type':
            row[key] = value if isinstance(value, str) and value in {
                'capabilities', 'settings_public', 'capture_prepared', 'capture_result',
                'capture_aborted', 'error', 'pong'} else 'unknown'
        elif key == 'response_code':
            row[key] = value if isinstance(value, str) and value in {
                'handoff_unavailable', 'rapido_unavailable', 'unknown_handoff',
                'already_committed', 'invalid_capture', 'unsupported_message'} else 'unknown'
        elif key == 'launcher_role':
            row[key] = value if isinstance(value, str) and value in {
                'desktop', 'helper', 'chromium', 'firefox', 'shell'} else 'unknown'
    if error is not None:
        name = type(error).__name__
        row['error_type'] = name if name in _error_types else 'OtherError'
        for key in ('errno', 'winerror'):
            value = getattr(error, key, None)
            if type(value) is int:
                row[key] = value
    try:
        with _lock:
            path = Path(folder)
            path.mkdir(parents=True, exist_ok=True)
            with (path / f'native-{os.getpid()}.jsonl').open('a', encoding='utf-8') as output:
                output.write(json.dumps(row, allow_nan=False) + '\n')
        return True
    except (OSError, ValueError):
        return False  # Diagnostics must not change IPC acceptance or deadlines.


@contextmanager
def trace(component, phase, *, operation=None, **numbers):
    started = time.monotonic()
    event(component, phase, operation=operation, outcome='begin', **numbers)
    try:
        yield
    except Exception as error:
        event(component, phase, operation=operation, outcome='error', error=error,
              elapsed_ms=(time.monotonic()-started)*1000, **numbers)
        raise
    else:
        event(component, phase, operation=operation, elapsed_ms=(time.monotonic()-started)*1000, **numbers)
