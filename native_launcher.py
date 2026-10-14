"""Authorize Native Messaging launchers using actual Windows parent processes.

Checks SID, full image path and creation order while keeping process handles
open. A copied helper run by an arbitrary local executable is not a browser.
Signing/injection/trusted-file tampering are outside this path allowlist policy.
"""
from contextlib import contextmanager, ExitStack
from ctypes import wintypes
import ctypes
import os
import ntpath
import re
from pathlib import Path
from windows_peer import inspect_process, canonical_image

CHROMIUM_ORIGIN = "chrome-extension://hlpkfnodjoglfdiekijebbppfgkjkbmp/"
FIREFOX_ID = "rapido-capture@rapido.local"


def parent_pid(pid):
    if os.name != "nt":
        raise OSError("Windows launcher verification requires Windows")
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    class Entry(ctypes.Structure):
        _fields_ = [("dwSize",wintypes.DWORD),("cntUsage",wintypes.DWORD),
            ("th32ProcessID",wintypes.DWORD),("th32DefaultHeapID",ctypes.c_size_t),
            ("th32ModuleID",wintypes.DWORD),("cntThreads",wintypes.DWORD),
            ("th32ParentProcessID",wintypes.DWORD),("pcPriClassBase",wintypes.LONG),
            ("dwFlags",wintypes.DWORD),("szExeFile",wintypes.WCHAR*260)]
    k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD,wintypes.DWORD]
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for name in ("Process32FirstW","Process32NextW"):
        f=getattr(k,name); f.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]; f.restype=wintypes.BOOL
    k.CloseHandle.argtypes=[wintypes.HANDLE]; k.CloseHandle.restype=wintypes.BOOL
    snapshot = k.CreateToolhelp32Snapshot(2,0)
    if snapshot is None or snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry=Entry(); entry.dwSize=ctypes.sizeof(Entry)
        ok=k.Process32FirstW(snapshot,ctypes.byref(entry))
        while ok:
            if entry.th32ProcessID==pid and entry.th32ParentProcessID:
                return int(entry.th32ParentProcessID)
            ok=k.Process32NextW(snapshot,ctypes.byref(entry))
        raise PermissionError("Launcher process disappeared")
    finally:
        k.CloseHandle(snapshot)


def _folder(csidl):
    shell = ctypes.WinDLL("shell32",use_last_error=True)
    f=shell.SHGetFolderPathW
    f.argtypes=[wintypes.HWND,ctypes.c_int,wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR]
    f.restype=ctypes.c_long
    result=ctypes.create_unicode_buffer(260)
    if f(None,csidl,None,0,result)!=0 or not result.value:
        raise OSError("Windows known folder unavailable")
    return Path(result.value)


def browser_images():
    # Resolve actual OS known folders, not caller-controlled environment strings.
    result={}
    for root in (_folder(0x26),_folder(0x2a)):
        for suffix,role in (
            (r"Google\Chrome\Application\chrome.exe","chromium"),
            (r"Microsoft\Edge\Application\msedge.exe","chromium"),
            (r"Mozilla Firefox\firefox.exe","firefox"),
            (r"Firefox Developer Edition\firefox.exe","firefox"),
            (r"Firefox Nightly\firefox.exe","firefox")):
            result[canonical_image(str(root/suffix))]=role
    result[canonical_image(str(_folder(0x1c)/r"Google\Chrome\Application\chrome.exe"))]="chromium"
    return result


def valid_origin(role, args, executable):
    if role=="desktop":
        return args==[]
    if role=="chromium":
        return (len(args) in (1,2) and args[0]==CHROMIUM_ORIGIN and
                (len(args)==1 or re.fullmatch(r"--parent-window=\d{1,20}",args[1]) is not None))
    if role=="firefox":
        if len(args)!=2 or args[1]!=FIREFOX_ID:
            return False
        try:
            # Refuse an explicitly linked manifest even if its lexical path matches.
            # This is defense-in-depth, not a solution for writable installation files.
            if Path(args[0]).is_symlink():
                return False
            manifest=canonical_image(args[0])
            expected=canonical_image(ntpath.join(ntpath.dirname(executable), "rapido-native-firefox.json"))
            return manifest==expected
        except ValueError:
            return False
    return False


@contextmanager
def trusted_launcher(executable, args, *, desktop_image=None):
    desktop = canonical_image(desktop_image or ntpath.join(ntpath.dirname(executable), "Rapido.exe"))
    helper = canonical_image(executable)
    with ExitStack() as stack:
        child=stack.enter_context(inspect_process(os.getpid()))
        for _ in range(3):  # one-file PyInstaller may insert a helper bootloader parent
            parent=stack.enter_context(inspect_process(parent_pid(child.pid)))
            if parent.user_sid!=child.user_sid or parent.creation_time>child.creation_time:
                raise PermissionError("Invalid launcher identity/creation order")
            if parent.image_path==desktop:
                role="desktop"
                break
            if parent.image_path==helper:
                child=parent
                continue
            role=browser_images().get(parent.image_path)
            if role is None:
                raise PermissionError("Untrusted Native Messaging launcher")
            break
        else:
            raise PermissionError("Unsupported helper parent chain")
        if not valid_origin(role,args,executable):
            raise PermissionError("Unexpected extension origin")
        yield role
