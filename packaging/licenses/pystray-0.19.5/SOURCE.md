# pystray 0.19.5 — source and replacement information

Rapido for Windows uses the unmodified library pystray 0.19.5 (system tray icon).
Its PyPI metadata declares the GNU Lesser General Public License v3 (LGPLv3).
The package's own `COPYING` (GNU GPL v3 text) and `COPYING.LGPL` (GNU LGPL v3
text) are shipped unchanged in `third-party/packages/pystray/`.

## Exact source

- PyPI publishes only a wheel for this version (no sdist). The wheel contains
  the complete Python source of the library:
  https://files.pythonhosted.org/packages/5c/64/927a4b9024196a4799eba0180e0ca31568426f258a4a5c90f87a97f51d28/pystray-0.19.5-py2.py3-none-any.whl
  SHA-256: `a0c2229d02cf87207297c22d86ffc57c86c227517b038c0d3c59df79295ac617`.
- Upstream repository tag `v0.19.5` (annotated tag object
  `c587fbe535610c177d49b585264762fa06abddca`), commit
  `1907f8681d6d421517c63d94f425f9cdd74d0034`:
  https://github.com/moses-palmer/pystray/tree/1907f8681d6d421517c63d94f425f9cdd74d0034

Checked on 2026-10-15: all 13 `pystray/` files of the wheel are byte-identical
(after CRLF/LF normalization) to `lib/pystray/` at that commit, and the wheel's
`COPYING.LGPL` matches the repository file. The build collector copies this
notice only when every installed `pystray/` source file matches those hashes.

## Replacing the library

The bundled copy is compiled Python bytecode inside the PyInstaller archive of
`Rapido.exe`. Rapido's own source code, its pinned build versions
(`packaging/constraints-windows-build.txt`) and its build commands
(`.github/workflows/windows.yml`, step "Build Rapido.exe (PyInstaller)") are
public in https://github.com/shimon3/rapido. To use a modified pystray, install
the modified library in the build environment instead of pystray 0.19.5 and
rebuild with those commands.

This file records evidence and instructions. It is not a legal opinion and does
not by itself establish that every LGPLv3 obligation is fulfilled.
