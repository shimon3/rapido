# certifi 2026.10.19 — source information

Rapido for Windows uses the unmodified package certifi 2026.10.19 (Mozilla CA
certificate bundle). Its PyPI metadata declares the Mozilla Public License 2.0
(MPL-2.0). The package's own `LICENSE` notice is shipped unchanged in
`third-party/packages/certifi/`; it refers to the MPL-2.0 without including
it, so the full license text is shipped next to this file as `MPL-2.0.txt`.

## Exact Source Code Form

- PyPI sdist:
  https://files.pythonhosted.org/packages/a6/bd/1436c50cc46699de0230fbaacc1d1de7bfec413176099949e9d5112e88f2/certifi-2026.10.19.tar.gz
  SHA-256: `035c1e85572b141bf1c3a3eff0e33a8eb74917522f2559075ff8d2fea780a1ae`.
- PyPI wheel used by the build:
  https://files.pythonhosted.org/packages/c4/51/29046e48f693c54e5b7412216d447a1d8362c9653148d98c02cdf65fa733/certifi-2026.10.19-py3-none-any.whl
  SHA-256: `42d35340cc5b9ba78e818ddbff0c5b1c2b779de448a340fd1b989f5fa8670e1b`.
- Upstream repository tag `2026.10.19` (tag object
  `39e296825d323aa1c8e998ffd9cc57fe22514a24`), commit
  `662df63d7906df66f1f07c0751a3dfe9da14d914`:
  https://github.com/certifi/python-certifi/tree/662df63d7906df66f1f07c0751a3dfe9da14d914

Checked on 2026-10-23: both PyPI files match the SHA-256 published by PyPI, and
all 7 `certifi/` files of the wheel, including `cacert.pem`, are byte-identical
(after CRLF/LF normalization) to the same paths at that commit. The build
collector copies this notice only when every reviewed installed `certifi/` file
matches the hashes in `scripts/collect_license_evidence.py`.

## Shipped copy of the Source Code Form

The build copies the 5 reviewed `certifi/` package files (the wheel's 2 test
files are not part of the reviewed set), byte for byte as installed,
into `third-party/source/certifi-2026.10.19/`. Their SHA-256 values are listed in
`third-party/inventory.json` (`kind` `verified-source`). The copy is made only
when every file matches the reviewed hashes above.

## MPL-2.0 text

`MPL-2.0.txt` is the verbatim text from https://www.mozilla.org/media/MPL/2.0/index.txt
(downloaded 2026-10-15), SHA-256
`3f3d9e0024b1921b067d6f7f88deb4a60cbe7a78e76c64e3f1d7fc3b779b9d04`.

This file records evidence and source locations. It is not a legal opinion and
does not by itself establish that every MPL-2.0 obligation is fulfilled.
