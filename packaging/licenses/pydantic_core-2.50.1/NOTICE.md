# pydantic_core 2.50.1 — Rust crates compiled into the native module

`pydantic_core/_pydantic_core.cp313-win_amd64.pyd` is compiled from Rust and
statically links third-party crates. The package's own `LICENSE` (MIT) does not
reproduce their licenses, so this folder adds them.

- The shipped `.pyd` (SHA-256
  `6c320aa8f5a182d815aeeef4332cd44a36cf1f3ca4a0653d33bc0079c4fb3f7c`) is
  byte-identical to the one in the official wheel
  https://files.pythonhosted.org/packages/2d/1f/323f78ddd9d9938aac420c1abb4e8ba799fc8bdab0acc67c0593b837c979/pydantic_core-2.50.1-cp313-cp313-win_amd64.whl
  (SHA-256 `7816e98acc08119dc0f340ab167048ecc54126316330c1f0caf7c6756c88e28f`).
- Crate list: `Cargo.lock` of the official sdist
  https://files.pythonhosted.org/packages/a6/24/af4ec4be49fbc810f35b0bdcacc3d433b56bbfa469fd3bfd4ae116cd9bf1/pydantic_core-2.50.1.tar.gz
  (SHA-256 `e50d7b94baac6c7d09927fa5ca5800a0c7ee5015c7fcff65beb3a1931b5a6e09`,
  lockfile SHA-256 `ac24753c2ed315f8dc22d6470fa868970e3705a0888d879704e872d53f21452d`).
- Each of the 99 crates.io packages in that lockfile was downloaded from
  `https://static.crates.io/crates/<name>/<name>-<version>.crate` on 2026-10-15;
  every archive matched the lockfile checksum. Its top-level
  LICENSE/COPYING/NOTICE/COPYRIGHT/UNLICENSE files are stored verbatim (CRLF
  normalized to LF) in `texts/`, named by SHA-256 and indexed per crate in
  `crates.json` with the license declared in the crate's `Cargo.toml`.

The list is a superset: it also contains build-time crates (procedural macros,
build scripts) and crates for other platforms that are not linked into the
Windows module. `r-efi 5.2.0` and `wit-bindgen-rt 0.39.0` (UEFI and WebAssembly
targets only) contain no license file in their published archives; their
declared licenses are listed in `crates.json`.

Not established here: that the official wheel was built from exactly this
lockfile (it is built by the upstream project), which crates are actually
linked, or which option of a dual license applies. This file records evidence.
It is not a legal opinion.
