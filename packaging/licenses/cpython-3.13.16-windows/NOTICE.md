# Python 3.13.16 Windows runtime — incorporated components

Rapido for Windows ships the Python 3.13.16 runtime from the official Windows
build (`python313.dll`, `*.pyd`, `sqlite3.dll`, `libcrypto-3.dll`,
`libssl-3.dll`, `libffi-8.dll`, Microsoft runtime DLLs). Its own `LICENSE.txt`
is shipped as `third-party/Python-LICENSE.txt` and covers the PSF license, the
Microsoft Distributable Code conditions, bzip2, libffi, OpenSSL (Apache-2.0)
and Tcl/Tk. It does not reproduce every incorporated component, so this folder
adds the upstream texts below.

Upstream tag `v3.13.16` (tag object `3b55c23ff4a6aa32f77be661802a3978d7324f88`),
commit `cbc944f4bc59639a444dd971c737788ba2283a91`:
https://github.com/python/cpython/tree/cbc944f4bc59639a444dd971c737788ba2283a91

- `license.rst`: verbatim `Doc/license.rst` at that commit, SHA-256
  `952ac05720d7f1dcb63589b35eb0931b1442eb250230a4ad31198eddf0ad6abc`.
  Its "Licenses and Acknowledgements for Incorporated Software" section
  includes expat (`pyexpat.pyd`), libffi, zlib, libmpdec (`_decimal.pyd`),
  mimalloc, OpenSSL and the other notices of the interpreter itself.
- `HACL-LICENSE.txt`: verbatim first 22 lines (MIT license header) of
  `Modules/_hacl/Hacl_Hash_SHA2.c` at that commit; the MD5, SHA1 and SHA3
  files carry the identical header (SHA-256
  `964361468338dbed9e90e896e2f6312140a0ad79ba503df884e0c7a2288b4087`). These
  hash implementations are compiled into `python313.dll`.

External libraries of the Windows build, from `PCbuild/get_externals.bat` at
the same commit: bzip2 1.0.8, libffi 3.4.4, OpenSSL 3.5.9, mpdecimal 4.0.0,
SQLite 3.50.4.0, xz 5.2.5, zlib 1.3.1 (Tcl/Tk 8.6.15 is not shipped by Rapido).
Sources of these exact versions are published by the CPython project at
https://github.com/python/cpython-source-deps, tags checked 2026-10-15:
`bzip2-1.0.8` 05301997b2f9590f49c672cf3dfd3d3dfa7ad521,
`libffi-3.4.4` 73b247f34ef3ae1859b8c2c34d321d34ebc5db15,
`openssl-3.5.9` 9781f5eb703412922b70d69b4f1e10e54e1bd303,
`mpdecimal-4.0.0` 780e21d43a92832d12c2add68fcc8e03cee38bcf,
`sqlite-3.50.4.0` c8123bc55da6467f4ef3e9b70cdb67cecf33b937,
`xz-5.2.5` c6bc0c612605622aaef101a33a751f9de2ecc193,
`zlib-1.3.1` 4dc98e1909830e2bdc2a9cc2236e3c5d5037335b.
SQLite is dedicated to the public domain by its authors; liblzma from xz 5.2.5
is in the public domain according to that release's `COPYING`.

Not established here:

- that each shipped binary was built from exactly these sources (selection is
  by interpreter version 3.13.16 only; Authenticode/VERSIONINFO not checked);
- the Microsoft redistribution terms for `VCRUNTIME140*.dll`, `ucrtbase.dll`
  and `api-ms-win-*.dll`, beyond the conditions quoted in `Python-LICENSE.txt`.

This file records evidence. It is not a legal opinion.
