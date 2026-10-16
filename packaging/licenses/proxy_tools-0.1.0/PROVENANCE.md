# proxy_tools 0.1.0 — supplemental upstream license evidence

The published sdist is missing its license file. PyPI metadata/setup.py says
MIT, but `proxy_tools/__init__.py` attributes Armin Ronacher (2013), adapted by
Jonathan Tushman (2014), and says BSD with a reference to LICENSE.

Sources checked on 2026-10-15:

- [PyPI exact version metadata](https://pypi.org/pypi/proxy-tools/0.1.0/json)
- [Published sdist](https://files.pythonhosted.org/packages/f2/cf/77d3e19b7fabd03895caca7857ef51e4c409e0ca6b37ee6e9f7daa50b642/proxy_tools-0.1.0.tar.gz)
  SHA-256: `ccb3751f529c047e2d8a58440d86b205303cf0fe8146f784d1cbcd94f0a28010`.
- [Upstream license at immutable commit](https://github.com/jtushman/proxy_tools/blob/db43f1e35d4f90a65c5a4d56d9e9af88212ec6e6/LICENSE.txt)
  Git blob: `078411c7399fbc0454f36cbe8c8cdbaaba7ebc95`.
  License text SHA-256 (LF): `a428fb8a2e762af3eb0a6edbbb88e9b42ccfee80fd9b423958bcacf9b9abbfe4`.
- [Upstream module at the same commit](https://github.com/jtushman/proxy_tools/blob/db43f1e35d4f90a65c5a4d56d9e9af88212ec6e6/proxy_tools/__init__.py)
  matches the published module byte-for-byte after LF/CRLF normalization:
  SHA-256 `d1539d95e1a713c068ca81d42e047b2c76568964cf277596d4e19efb22f476be`.

LICENSE.txt is copied verbatim from that upstream commit. No copyright holder,
permission or legal conclusion has been invented. The build supplements the
text only for this exact installed version/module hash and preserves the
MIT/BSD discrepancy as a review problem in inventory.json. This is evidence,
not a determination that the distribution is legally compliant.
