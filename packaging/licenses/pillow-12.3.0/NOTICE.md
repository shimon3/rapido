# Pillow 12.3.0 — bundled native libraries

Pillow's own `LICENSE` (shipped in `third-party/packages/pillow/`) reproduces
the licenses of the libraries in its Windows wheels: brotli 1.2.0, FreeType
2.14.3, HarfBuzz 14.2.1, Little CMS 2.19.1, libavif 1.4.2, libjpeg-turbo
3.1.4.1, libpng 1.6.58, libwebp 1.6.0, OpenJPEG 2.5.4, LibTIFF 4.7.1, xz 5.8.3
and zlib-ng 2.3.3. These versions are as declared by Pillow. The 7 shipped
`PIL/*.pyd` files are byte-identical to those of the official wheel
https://files.pythonhosted.org/packages/a6/9b/7a58e61d62be561da3a356fe2384d4059a6345fc130e23ef1c36a5b81d24/pillow-12.3.0-cp313-cp313-win_amd64.whl
(SHA-256 `1cca606cd25738df4ed873d5ad46bbdb3d83b5cbca291f6b4ff13a4df6b0bbe8`,
checked 2026-10-15); they were not rebuilt or compared with each library's
source.

FreeType is distributed under a choice of the FreeType License (FTL) or GPLv2.
This notice uses the FTL option, which asks for the following credit in the
documentation:

Portions of this software are copyright © 1996-2026 The FreeType Project
(https://freetype.org). All rights reserved.

The year range is taken from `include/freetype/freetype.h` at FreeType tag
`VER-2-14-3` (commit `0a0221a1347e2f1e07c395263540026e9a0aa7c7`):
https://gitlab.freedesktop.org/freetype/freetype/-/blob/VER-2-14-3/include/freetype/freetype.h

This file records evidence. It is not a legal opinion.
