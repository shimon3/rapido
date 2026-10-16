# certifi 2026.7.22 — source information

Rapido for Windows uses the unmodified package certifi 2026.7.22 (Mozilla CA
certificate bundle). Its PyPI metadata declares the Mozilla Public License 2.0
(MPL-2.0). The package's own `LICENSE` notice is shipped unchanged in
`third-party/packages/certifi/`; it refers to the MPL-2.0 without including
it, so the full license text is shipped next to this file as `MPL-2.0.txt`.

## Exact Source Code Form

- PyPI sdist:
  https://files.pythonhosted.org/packages/a3/c2/24167ea9858356b47a87a50d39908bfdb72ceeefe0041586e704e5376b3a/certifi-2026.7.22.tar.gz
  SHA-256: `741e2c3b351ddf169a738da9f2c048608ff7f2c5cc02f1ebc6b118bb090d5d55`.
- PyPI wheel used by the build:
  https://files.pythonhosted.org/packages/0b/a7/71ac2cff56fec219ed242bb11b8efb69fcc4bec75db06fb7bfe35de520e6/certifi-2026.7.22-py3-none-any.whl
  SHA-256: `62f22742b58a1a33014a2b6b706588a8d7e2a88ae7bd1a6ebe8c992928483775`.
- Upstream repository tag `2026.07.22`, commit
  `5379b709be8a8595803a7bd907f87e302fc6ae1d`:
  https://github.com/certifi/python-certifi/tree/5379b709be8a8595803a7bd907f87e302fc6ae1d

Checked on 2026-10-15: all 7 `certifi/` files of the wheel, including
`cacert.pem`, are byte-identical (after CRLF/LF normalization) to the same
paths at that commit. The build collector copies this notice only when every
installed `certifi/` file matches those hashes.

## MPL-2.0 text

`MPL-2.0.txt` is the verbatim text from https://www.mozilla.org/media/MPL/2.0/index.txt
(downloaded 2026-10-15), SHA-256
`3f3d9e0024b1921b067d6f7f88deb4a60cbe7a78e76c64e3f1d7fc3b779b9d04`.

This file records evidence and source locations. It is not a legal opinion and
does not by itself establish that every MPL-2.0 obligation is fulfilled.
