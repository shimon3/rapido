# Pillow 13.0.0 — bundled native libraries

Pillow's own `LICENSE` (shipped in `third-party/packages/pillow/`) reproduces
the licenses of the libraries in its Windows wheels: brotli 1.2.0, FreeType
2.14.3, HarfBuzz 14.5.0, Little CMS 2.19.1, libavif 1.4.2, libjpeg-turbo
3.2.0, libpng 1.6.58, libwebp 1.6.0, OpenJPEG 2.5.4, LibTIFF 4.7.2, xz 5.8.4
and zlib-ng 2.3.3. These versions are as declared by Pillow in the wheel's
`LICENSE` (SHA-256 `988ffe8ab3480b0f4e9a0ab2702bffd73d9fb6b47198043fb3ba101a62fac236`).
The 7 shipped `PIL/*.pyd` files are byte-identical to those of the official wheel
https://files.pythonhosted.org/packages/d7/ed/1b16fb66a37e1b9e41370b93b2c614c7da761a5b2a41dc333f7af4639962/pillow-13.0.0-cp313-cp313-win_amd64.whl
(SHA-256 `9dda0788a9932776a75d8bcc020076edc308ce2508b51f6739a45e3158b3fc42`,
as published by PyPI, checked 2026-10-23); they were not rebuilt or compared
with each library's source.

FreeType is distributed under a choice of the FreeType License (FTL) or GPLv2.
This notice uses the FTL option, which asks for the following credit in the
documentation:

Portions of this software are copyright © 1996-2026 The FreeType Project
(https://freetype.org). All rights reserved.

The year range is taken from `include/freetype/freetype.h` at FreeType tag
`VER-2-14-3` (commit `0a0221a1347e2f1e07c395263540026e9a0aa7c7`):
https://gitlab.freedesktop.org/freetype/freetype/-/blob/VER-2-14-3/include/freetype/freetype.h

This file records evidence. It is not a legal opinion.
