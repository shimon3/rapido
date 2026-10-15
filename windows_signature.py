"""Experimental Authenticode primitive for #26; NOT wired into runtime admission.

The caller must obtain certificate pins from an independently protected policy.
This verifies a held disk file, not a running process, deployment ACLs, browser
registration, Python payloads or protection against injection. Cached revocation
only: unavailable required trust information fails closed, with no network/UI.
"""
from __future__ import annotations

import ctypes
import hashlib
import ntpath
import os
import re
import uuid
from contextlib import contextmanager
from dataclasses import dataclass

DWORD = ctypes.c_uint32  # Windows widths also remain correct in portable tests.
PTR = ctypes.c_void_p


class _FileInfo(ctypes.Structure):
    _fields_ = [("cbStruct", DWORD), ("pcwszFilePath", ctypes.c_wchar_p),
                ("hFile", PTR), ("pgKnownSubject", PTR)]


class _TrustData(ctypes.Structure):
    _fields_ = [("cbStruct", DWORD), ("pPolicyCallbackData", PTR),
                ("pSIPClientData", PTR), ("dwUIChoice", DWORD),
                ("fdwRevocationChecks", DWORD), ("dwUnionChoice", DWORD),
                ("pFile", ctypes.POINTER(_FileInfo)), ("dwStateAction", DWORD),
                ("hWVTStateData", PTR), ("pwszURLReference", ctypes.c_wchar_p),
                ("dwProvFlags", DWORD), ("dwUIContext", DWORD),
                ("pSignatureSettings", PTR)]


class _CertContext(ctypes.Structure):
    _fields_ = [("dwCertEncodingType", DWORD), ("pbCertEncoded", PTR),
                ("cbCertEncoded", DWORD), ("pCertInfo", PTR), ("hCertStore", PTR)]


class _ProviderCertPrefix(ctypes.Structure):
    # Only these documented leading fields are read; the provider owns memory.
    _fields_ = [("cbStruct", DWORD), ("pCert", ctypes.POINTER(_CertContext))]


@dataclass(frozen=True)
class VerifiedSignature:
    path: str
    certificate_sha256: str


def _inputs(path, certificate_sha256):
    path = os.fspath(path)
    # Restrict this primitive to ordinary absolute local file paths. No device
    # namespace, UNC, ADS, drive-relative paths or implicit current directory.
    drive, tail = ntpath.splitdrive(path) if isinstance(path, str) else ("", "")
    parts = [part for part in re.split(r"[\\/]", tail) if part]
    if (not isinstance(path, str) or "\x00" in path or
            not re.fullmatch(r"[A-Za-z]:", drive) or not tail.startswith(("\\", "/")) or
            ":" in tail or not parts or len(path) > 32767 or
            any(re.search(r'[<>"|?*\x00-\x1f]', part) or part.endswith((".", " ")) or
                re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", part.split(".")[0])
                for part in parts)):
        raise ValueError("An ordinary absolute local Windows file path is required")
    if isinstance(certificate_sha256, (str, bytes)):
        raise ValueError("An explicit collection of SHA-256 certificate pins is required")
    try:
        pins = frozenset(certificate_sha256)
    except TypeError:
        raise ValueError("Invalid certificate pin collection") from None
    if not pins or any(not isinstance(pin, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", pin)
                       for pin in pins):
        raise ValueError("An explicit collection of SHA-256 certificate pins is required")
    return ntpath.normpath(path), frozenset(pin.lower() for pin in pins)


def _libraries():
    if os.name != "nt":
        raise OSError("Authenticode verification requires Windows")
    # LOAD_LIBRARY_SEARCH_SYSTEM32: never search a writable working directory.
    kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
    trust = ctypes.WinDLL("wintrust.dll", use_last_error=True, winmode=0x800)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, DWORD, DWORD, PTR, DWORD, DWORD, PTR]
    kernel.CreateFileW.restype = PTR
    kernel.CloseHandle.argtypes = [PTR]
    kernel.CloseHandle.restype = ctypes.c_int32
    trust.WinVerifyTrust.argtypes = [PTR, PTR, ctypes.POINTER(_TrustData)]
    trust.WinVerifyTrust.restype = ctypes.c_int32  # LONG, never HRESULT success rules.
    trust.WTHelperProvDataFromStateData.argtypes = [PTR]
    trust.WTHelperProvDataFromStateData.restype = PTR
    trust.WTHelperGetProvSignerFromChain.argtypes = [PTR, DWORD, ctypes.c_int32, DWORD]
    trust.WTHelperGetProvSignerFromChain.restype = PTR
    trust.WTHelperGetProvCertFromChain.argtypes = [PTR, DWORD]
    trust.WTHelperGetProvCertFromChain.restype = ctypes.POINTER(_ProviderCertPrefix)
    return kernel, trust


def _certificate(trust, state):
    provider = trust.WTHelperProvDataFromStateData(state)
    if not provider:
        raise PermissionError("Signature provider state is unavailable")
    signer = trust.WTHelperGetProvSignerFromChain(provider, 0, False, 0)
    if not signer:
        raise PermissionError("Signature signer is unavailable")
    cert = trust.WTHelperGetProvCertFromChain(signer, 0)
    if not cert or cert.contents.cbStruct < ctypes.sizeof(_ProviderCertPrefix) or not cert.contents.pCert:
        raise PermissionError("Signer certificate is unavailable")
    context = cert.contents.pCert.contents
    if not context.pbCertEncoded or not 0 < context.cbCertEncoded <= 65536:
        raise PermissionError("Invalid signer certificate")
    # Copy while the WinVerifyTrust state still owns the certificate context.
    return hashlib.sha256(ctypes.string_at(context.pbCertEncoded, context.cbCertEncoded)).hexdigest()


@contextmanager
def verified_signed_file(path, *, certificate_sha256):
    """Yield only a Windows-trusted file signed by an explicitly pinned leaf.

    Hold FILE_SHARE_READ only until the context exits: conflicting write/delete
    opens fail. This is not an atomic verify-and-execute primitive; ancestor
    directory changes, mapped writers and process identity need separate controls.
    No implicit signer discovery, developer bypass or trust-result downgrade.
    """
    path, pins = _inputs(path, certificate_sha256)
    kernel, trust = _libraries()
    handle = kernel.CreateFileW(path, 0x80000000, 1, None, 3, 0x80, None)
    if not handle or handle == ctypes.c_void_p(-1).value:
        raise OSError("Cannot hold signature input file")
    try:
        info = _FileInfo(ctypes.sizeof(_FileInfo), path, handle, None)
        data = _TrustData()
        data.cbStruct = ctypes.sizeof(data)
        data.dwUIChoice = 2  # WTD_UI_NONE
        data.dwUnionChoice = 1  # WTD_CHOICE_FILE
        data.pFile = ctypes.pointer(info)
        data.dwStateAction = 1  # WTD_STATEACTION_VERIFY
        # Check cached revocation for the chain excluding the root. Do not set
        # REVOCATION_CHECK_NONE or HASH_ONLY. Missing required data is a failure.
        data.dwProvFlags = 0x80 | 0x1000  # CHAIN_EXCLUDE_ROOT | CACHE_ONLY_URL_RETRIEVAL
        action = ctypes.create_string_buffer(
            uuid.UUID("00aac56b-cd44-11d0-8cc2-00c04fc295ee").bytes_le, 16)
        try:
            status = trust.WinVerifyTrust(ctypes.c_void_p(-1), action, ctypes.byref(data))
            if status != 0:
                raise PermissionError(f"Signature trust verification failed (0x{status & 0xffffffff:08x})")
            fingerprint = _certificate(trust, data.hWVTStateData)
            if fingerprint not in pins:
                raise PermissionError("Signature publisher is not authorized")
        finally:
            # Required even when VERIFY fails or signer extraction raises.
            data.dwStateAction = 2  # WTD_STATEACTION_CLOSE
            trust.WinVerifyTrust(ctypes.c_void_p(-1), action, ctypes.byref(data))
        yield VerifiedSignature(path, fingerprint)
    finally:
        kernel.CloseHandle(handle)
