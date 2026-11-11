# Dependency provenance review — certifi and pydantic-core (2026-11-11)

**Status: candidate evidence ONLY; upgrades not authorized.** No hash should be
accepted solely because it was produced by a newly installed package. This
document does not replace third-party licence review.

## Verified upstream release information

- certifi 2026.10.23: [PyPI release](https://pypi.org/project/certifi/2026.10.23/).
  - Official sdist SHA-256: `a9895e6e2758b371e0545e321a3a8fd1fcfd9829ada8824a936dfb16aaaf36cd`.
  - Official universal wheel SHA-256: `e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1`.
  - PyPI describes publication provenance from `certifi/python-certifi` commit `b60466c9f2882d9cf088943c650b0faac06c080c`, dated October 23, 2026.
  - These are **published upstream claims**; a local download and independent hash comparison have not yet been performed in this review.
- pydantic-core 2.50.2: [PyPI release](https://pypi.org/project/pydantic_core/2.50.2/).
  - A CPython 3.13 Windows x64 wheel exists, but PyPI labels the listed release files as **without provenance**. Independently review the upstream source, wheel identity and Rust crate licence payload before accepting a new binary hash.

## Offline certifi wheel verification (not admission)

The new `scripts/verify_certifi_wheel.py` accepts only the original wheel
`certifi-2026.10.23-py3-none-any.whl` downloaded independently from PyPI.
It compares the complete archive SHA-256 to the reviewed PyPI digest, rejects
unsafe member paths, symlinks and excess payload sizes, then emits LF-normalized
source-file SHA-256 values. Use an isolated offline reviewer machine:

```powershell
python -m scripts.verify_certifi_wheel .\\certifi-2026.10.23-py3-none-any.whl
```

Reject any verification failure, retain the archive and generated JSON as
review evidence, and independently compare the output with the upstream tagged
source. This tool **does not** approve `certifi` or modify `SOURCE_NOTICES`.
The unit tests use synthetic archives and do not prove verification of the
actual upstream wheel; a real-download checksum and upstream source review
remain pending.

## Read-only local inventory

On an isolated reviewer environment that has an explicitly chosen version
installed, run:

```powershell
python -m scripts.review_package_source certifi
python -m scripts.review_package_source pydantic-core
```

This outputs relative file paths and file digests only. It deliberately does
NOT modify `SOURCE_NOTICES`, the distribution lock, the collected notice text,
or any build/release policy.

## Required before admitting updated dependencies

1. Download the exact official PyPI wheel/sdist independently and verify full
   archive SHA-256 against the published PyPI digest.
2. Compare all shipped package files to the installed candidate, including
   `certifi/cacert.pem` and the exact Windows x64 `pydantic_core` extension.
   Review the correct normalization mode before comparing hashes.
3. For certifi, compare upstream source tag/commit to the wheel files and
   update the `packaging/licenses/certifi-<version>/SOURCE.md` file with exact
   verified identities; retain the complete MPL-2.0 text.
4. For pydantic-core, inspect the matching `.pyd`, embedded Rust crates,
   all relevant crate notices, and `crates.json`; update the versioned
   licence evidence only after independent validation.
5. Update the `SOURCE_NOTICES` exact-version table and related human report
   only after steps 1-4. Do not turn unknown hashes into trusted hashes
   automatically. Preserve fail-closed checks.
6. Apply the full mutually compatible `pydantic` + `pydantic-core` pins in
   a separate tested commit, then run Windows CI and the full licensing gate.

The current green CI baseline must remain available on the integration branch
until the review is complete. This document is not evidence that the upgraded
packages have passed Rapido CI.
