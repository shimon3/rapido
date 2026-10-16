# cffi 2.1.1 — libffi compiled into the Windows module

`_cffi_backend.cp313-win_amd64.pyd` (SHA-256
`21b7160d4a6da9590794fdb38718982060b5c92d56fb0e441fc8b62ee789be8d`) is
byte-identical to the one in the official wheel
https://files.pythonhosted.org/packages/60/a6/8b149b2c3f2e11aaa1618ef64500b45f50f22c57a977a4dff1aff1f91042/cffi-2.1.1-cp313-cp313-win_amd64.whl
(SHA-256 `1aa5645c30469b09530c4ebca77ebf8f17618293c58f8549cb1a543a50236e7d`).
It imports no libffi DLL: on Windows x64, cffi's `setup.py` compiles the old
libffi copy in `src/c/libffi_x86_x64` (`ffi.c`, `prep_cif.c`, `types.c` and
headers; `win32.c` is excluded) and links its prebuilt `win64.obj`.

cffi's own `LICENSE` (MIT No Attribution) defers to the notices at the
beginning of each file. Those libffi files carry Red Hat and contributor
copyrights with an MIT-style permission notice that must accompany copies.
`LIBFFI-NOTICES.txt` reproduces verbatim the leading comment of each compiled
C file and header (CRLF normalized to LF).

Sources checked on 2026-10-15:

- sdist https://files.pythonhosted.org/packages/9e/ef/008a1939e372c06329a3fce4279c02f328488f3526744906eeec3da7ad5f/cffi-2.1.1.tar.gz
  (SHA-256 `dd31f52ea1086513bb9df30f8fcee9b8918323ae067a3d5b78bc826a000712be`);
- upstream tag `v2.1.1`, commit `fd33e7700f0ebafe6f30bd5053f13327221b77a2`:
  https://github.com/python-cffi/cffi/tree/fd33e7700f0ebafe6f30bd5053f13327221b77a2/src/c/libffi_x86_x64
  All 10 files of that directory, and `LICENSE`, are identical in the sdist
  and at that commit.

`win64.asm`/`win64.obj` carry no notice; the precise libffi release they come
from is not established (setup.py says "from the CPython distribution"), nor
that the official wheel was built from exactly these files. This file records
evidence. It is not a legal opinion.
