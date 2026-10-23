# Rapido — third-party notices and source information

Rapido's own source code is licensed under the MIT License in `LICENSE`.
The Windows installer and portable archive also contain third-party software
under its own terms. Rapido's MIT License does not replace those terms.

Every official Windows build includes a `third-party` directory next to
`Rapido.exe`:

- `third-party/inventory.json` records the exact build-environment package
  versions, declared license metadata, copied license/notice files, SHA-256
  hashes, and unresolved review flags.
- `third-party/payload.json` records inspected files and native payload
  evidence from the built application.
- `third-party/packages/` contains license texts and component-specific
  notices collected from the reviewed build environment.
- `third-party/source/` contains the exact source files of the LGPL and MPL
  components below, copied only after they match the reviewed hashes.
- `third-party/python/` and `third-party/Python-LICENSE.txt` contain the
  CPython license and incorporated-component notices.
- `third-party/packages/pywebview/Microsoft.Web.WebView2-1.0.3856.49/`
  contains the reviewed Microsoft WebView2 SDK LICENSE and NOTICE files.

## Components requiring prominent source or replacement information

### pystray 0.19.5 — LGPLv3

Rapido uses the unmodified `pystray` Python package for its notification-area
icon. The distributed evidence includes `COPYING`, `COPYING.LGPL`, and
`SOURCE.md`. `SOURCE.md` identifies the exact wheel and upstream commit,
records the reviewed source-file hashes, and explains how to rebuild Rapido
with a modified copy. The 13 verified source files are shipped in
`third-party/source/pystray-0.19.5/`.

### certifi 2026.10.19 — MPL-2.0

Rapido uses the unmodified `certifi` certificate bundle. The distributed
evidence includes the package notice, the complete MPL-2.0 text, and
`SOURCE.md` with the exact wheel, source archive, upstream commit, and
reviewed file hashes. The 5 verified package files, including `cacert.pem`,
are shipped as the Source Code Form in `third-party/source/certifi-2026.10.19/`.

### proxy_tools 0.1.0 — upstream BSD text; metadata discrepancy

The published package metadata says MIT while the installed module identifies
BSD and refers to an omitted license file. For the exact reviewed module hash,
Rapido distributes `UPSTREAM-LICENSE.txt`, copied verbatim from the matching
immutable upstream commit, and records the discrepancy in
`third-party/inventory.json`. This evidence does not silently choose a
different license or erase the discrepancy.

### PyInstaller bootloader — GPL-2.0-or-later with the Bootloader Exception

`Rapido.exe` and `RapidoNativeHost.exe` are produced by PyInstaller and each
contains its bootloader. PyInstaller is licensed under the GPL version 2 or
later with an exception that permits distributing the bootloader with programs
under other licenses. The build copies PyInstaller's own license text into
`third-party/packages/pyinstaller/` and stops when that text does not contain
the Bootloader Exception. Whether the exception covers this exact use is part
of the human legal review.

## Other material

The evidence bundle also preserves notices for CPython, Pillow and its native
libraries, cffi/libffi, pydantic-core's Rust crates, pywebview's interop
assemblies, the WebView2 SDK, pythonnet (`Python.Runtime.dll`), yt-dlp, and the
remaining installed Python distributions.

FFmpeg and Deno are not intentionally copied into the Rapido build by the
current workflow. Rapido may offer to install them separately through Windows
Package Manager; those separately installed products retain their own license
terms. The final release artifact must still be inspected before claiming they
are absent from the bundle.

## Verification boundary

The build fails when required reviewed source notices, Python incorporated
notices, or WebView2 SDK notices do not match the pinned identities. That is a
reproducible evidence gate, not a legal opinion or a blanket compatibility
verdict. Before a public release, review `third-party/inventory.json`,
`third-party/payload.json`, and every reported problem against the exact
artifact being published.
