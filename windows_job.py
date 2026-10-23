"""Tie helper processes (yt-dlp workers) to Rapido's lifetime on Windows.

multiprocessing's daemon flag only works on a normal exit. When Rapido is
killed (crash, "End task", a hang closed by Windows), its workers kept running
and downloading. A job object created with KILL_ON_JOB_CLOSE is closed by the
kernel when Rapido's process ends, which terminates every process assigned to
it (and the processes they start, such as ffmpeg).

Only these workers are assigned: programs Rapido opens for the user (a
downloaded installer, Explorer, a browser) must survive Rapido.
"""
from __future__ import annotations

import ctypes
import os
import threading

_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001

_lock = threading.Lock()
_job = None


def _kernel():
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateJobObjectW.restype = wintypes.HANDLE
    k.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k.SetInformationJobObject.restype = wintypes.BOOL
    k.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.AssignProcessToJobObject.restype = wintypes.BOOL
    k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    return k


def _create_job(k):
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in
                    ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                     "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    job = k.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    info = ExtendedLimits()
    info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not k.SetInformationJobObject(job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                     ctypes.byref(info), ctypes.sizeof(info)):
        error = ctypes.get_last_error()
        k.CloseHandle(job)
        raise ctypes.WinError(error)
    # The handle stays open for Rapido's lifetime: the kernel closes it on exit.
    return job


def kill_with_this_process(pid: int) -> bool:
    """Terminate process `pid` (and what it starts) when this process ends.

    Best effort: returns False when not on Windows, or when the process is gone
    or cannot be assigned (for example inside a job that forbids it).
    """
    global _job
    if os.name != "nt" or not pid:
        return False
    try:
        k = _kernel()
        with _lock:
            if _job is None:
                _job = _create_job(k)
            job = _job
        handle = k.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, pid)
        if not handle:
            return False
        try:
            return bool(k.AssignProcessToJobObject(job, handle))
        finally:
            k.CloseHandle(handle)
    except OSError:
        return False
