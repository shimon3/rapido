# Licence obligations report — Rapido 1.3.0-beta.1 for Windows

Status date: 2026-10-18. Scope: the Windows installer and portable ZIP built by
`.github/workflows/windows.yml` from the pinned environment in
`packaging/constraints-windows-build.txt`.

This report separates **technical controls that CI enforces** from
**questions that need a qualified legal reviewer**. It is not a legal opinion
and does not declare Rapido legally compliant.

## 1. Technical controls enforced by every build

| Control | Where | Fails the build when |
| --- | --- | --- |
| Licence and notice files copied for every installed distribution | `scripts/collect_license_evidence.py` → `third-party/inventory.json` | Python licence or incorporated CPython notices missing or not matching the reviewed hashes |
| pystray 0.19.5 (LGPLv3): 13 installed source files compared with upstream commit `1907f868…` | same | any file differs, the version changes, or the source copy is missing |
| pystray source shipped as `third-party/source/pystray-0.19.5/` | same | no verified source files were copied |
| certifi 2026.7.22 (MPL-2.0): 7 files, including `cacert.pem`, compared with upstream commit `5379b709…` | same | any file differs, the version changes, or the source copy is missing |
| certifi Source Code Form shipped as `third-party/source/certifi-2026.7.22/` plus full `MPL-2.0.txt` | same | no verified source files were copied |
| proxy_tools 0.1.0: upstream BSD text supplied, MIT/BSD metadata discrepancy kept visible | same | the module or supplemental licence does not match the reviewed hash |
| WebView2 SDK binaries matched to NuGet 1.0.3856.49, LICENSE and NOTICE shipped | same | binary or text hash differs |
| Pillow, cffi/libffi, pydantic-core crates, pywebview interop DLLs: shipped binaries matched to official wheels | same | binary hash differs |
| PyInstaller bootloader: GPL-2.0-or-later text with the Bootloader Exception shipped | same | the copied PyInstaller licence lacks the exception |
| Bundle content inspected (modules, native libraries, archives); test frameworks forbidden | `scripts/collect_payload_evidence.py` | `pytest`/`_pytest` found in the bundle |
| PyPI advisory check for all 41 pinned distributions | `scripts/check_dependency_advisories.py` | a pinned version has an advisory or a response cannot be verified |

Evidence of the latest passing run before this change: CI #240
(https://github.com/shimon3/rapido/actions/runs/39120997040), 41 distributions
collected, 41/41 advisory responses verified.

## 2. Obligations per component and how the bundle addresses them

### pystray 0.19.5 — LGPL-3.0

- **Licence texts** (LGPLv3 §4(b)): `COPYING` (GPLv3) and `COPYING.LGPL`
  shipped in `third-party/packages/pystray/`.
- **Prominent notice that the library is used** (§4(a)): section in
  `THIRD-PARTY-NOTICES.md` shipped next to `Rapido.exe`.
- **Corresponding source of the library**: shipped byte-for-byte in
  `third-party/source/pystray-0.19.5/`, plus wheel and commit references in
  `SOURCE.md`.
- **Ability to recombine with a modified library** (§4(d)(0)): pystray is
  compiled into the PyInstaller archive inside `Rapido.exe`, so it cannot be
  swapped as a separate file. Rapido's complete application source, pinned
  build versions and build commands are public under MIT, and `SOURCE.md`
  explains how to rebuild with a modified pystray.
- **Installation Information** (§4(e)): Rapido is not shipped in or with a
  "User Product" device. However, Rapido's own Authenticode checks
  (`windows_signature.py`) may reject a rebuilt, differently signed native
  host in a fail-closed mode. A test must establish whether a user-rebuilt
  copy still works as a complete application, at least in developer mode
  (open question L1b).
- **Open legal question L1**: does rebuilding from public source satisfy
  §4(d)(0) for the exact tagged release? The release must keep the source of
  that tag permanently reachable, for example through the GitHub release
  source archive.

### certifi 2026.7.22 — MPL-2.0

- **Executable-form notice** (§3.2(a)): `THIRD-PARTY-NOTICES.md` and
  `SOURCE.md` say where the Source Code Form is; the form itself is shipped in
  `third-party/source/certifi-2026.7.22/`.
- **Licence text**: full `MPL-2.0.txt` shipped, since the package's own
  `LICENSE` only refers to it.
- **File-level copyleft**: Rapido does not modify certifi files, so it has no
  modified MPL files to publish.

### proxy_tools 0.1.0 — MIT metadata vs BSD text

- The build ships the upstream BSD text that matches the installed module and
  records the discrepancy. Both licences are permissive. Keeping the copyright
  notice satisfies either reading technically.
- **Open legal question L2**: does the reviewer accept shipping the BSD text
  without a separate MIT text? A reviewer may also ask for the MIT text from the
  package metadata as an extra precaution.

### PyInstaller 6.22.3 — GPL-2.0-or-later with the Bootloader Exception

- The bootloader is linked into both executables. The exception allows
  distributing it with non-GPL programs. The build now ships the licence text
  and refuses to build without the exception.
- **Open legal question L3**: confirm that the exception covers both the
  `--onedir` `Rapido.exe` and the `--onefile` `RapidoNativeHost.exe`.

### CPython 3.13.16 and its incorporated components

- PSF licence, Microsoft Distributable Code conditions, OpenSSL 3.5.9
  (Apache-2.0), libffi, bzip2, zlib, expat, mpdecimal, HACL\*, SQLite (public
  domain), and xz (public domain) are covered by `Python-LICENSE.txt` and
  `third-party/python/`.
- **Open legal question L4**: are the Microsoft redistribution terms for
  `VCRUNTIME140*.dll`, `ucrtbase.dll` and `api-ms-win-*.dll` satisfied by the
  conditions quoted in Python's licence?
- Apache-2.0 §4(d): OpenSSL 3.x ships no NOTICE file, so there is nothing more
  to reproduce. The reviewer should confirm this for 3.5.9.

### Pillow 12.3.0 and bundled native libraries

- Pillow's own `LICENSE` reproduces the licences of its bundled libraries.
  The FreeType FTL credit line is in `NOTICE.md`.
- **Open legal question L5**: FTL asks for the credit "in the documentation".
  Is the shipped notice enough, or must it also appear in the About dialog or
  the release notes?

### Microsoft WebView2 SDK 1.0.3856.49

- The SDK LICENSE and NOTICE are shipped. The WebView2 **Runtime** is not
  bundled; it is the copy installed on the system.
- **Open legal question L6**: the SDK licence limits redistribution to the
  "Distributable Code" it defines. The reviewer should confirm that the three
  `WebView2Loader.dll` architectures and the two managed DLLs are all
  Distributable Code.

### Other permissive components

fastapi, starlette, uvicorn, httpx, httpcore, anyio, h11, idna, pydantic,
typing extensions, click, colorama, bottle, pythonnet (`Python.Runtime.dll`),
clr_loader, cffi, pycparser, pywin32-ctypes, and yt-dlp (Unlicense). Their
licence files are copied by the generic collector. Attribution is satisfied by
shipping those files. Build-only tools in the inventory (pytest, iniconfig,
pluggy, Pygments, pefile, altgraph, setuptools, pip, packaging) are recorded,
but the payload inspection must confirm they are absent from the bundle.

### Components not bundled

FFmpeg and Deno are not copied into the build. Rapido offers to install them
through Windows Package Manager, under their own licences. Before publication,
`third-party/payload.json` of the exact candidate must confirm that they are
absent.

## 3. Remaining obligations before publication

| # | Obligation | Owner | Blocking |
| --- | --- | --- | --- |
| R1 | Keep the exact tagged source reachable for the life of the release (L1) | Owner at release time | Yes |
| R2 | Legal review of questions L1–L6 against the final `inventory.json` and `payload.json` | Qualified reviewer chosen by the owner | Yes |
| R3 | Confirm from `payload.json` that FFmpeg, Deno, pytest, private keys and signing fixtures are absent from the signed candidate | Maintainer (CI) | Yes |
| R4 | Decide on extra attribution: FreeType credit in the About dialog or release notes (L5), MIT text for proxy_tools (L2) | Owner after review | No, unless the reviewer requires it |
| R5 | Re-run the source comparisons whenever a pinned version changes; the build fails until this is done | Maintainer | Enforced automatically |

Do not describe Rapido as "licence compliant" until R1–R3 are closed and the
reviewer has answered L1–L6 in writing.
