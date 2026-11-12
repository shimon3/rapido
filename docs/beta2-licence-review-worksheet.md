# Human third-party licence review worksheet — Rapido 1.3.0-beta.2

**Status: PENDING HUMAN REVIEW — not legal clearance.**

Source checklist: [license-obligations-report.md](license-obligations-report.md).
Keep the signed review outside the release payload where appropriate. Copy a
sanitized decision summary into the final release dossier only after written
review by a qualified reviewer. Do not paste private personal or contract data.

## Exact candidate identity

- Final signed candidate source commit: **NOT YET CREATED**
- Windows CI reference (unsigned test only):
  `bbe3925a35b380b0a754d1b7eb0733dd4ce94947`
- Signed artifact installer SHA-256: **PENDING**
- Signed portable ZIP SHA-256: **PENDING**
- Generated third-party inventory SHA-256: **PENDING**
- Generated third-party payload manifest SHA-256: **PENDING**
- Reviewer and review date: **PENDING**

## Mandatory reviewer findings

| ID | Precise review question | Evidence to inspect | Result |
| --- | --- | --- | --- |
| L1a | Is pystray LGPLv3 static PyInstaller bundling adequately handled by complete app/source and rebuild instructions? | `third-party/source/pystray-0.19.5/`, pystray source notice, exact public tag archive, release build instructions | PENDING |
| L1b | Can recipients actually rebuild and run the app with a modified pystray without prohibited signature restrictions? | Developer build/launch proof, native-host policy, FAQ, independent rebuilt executable | PENDING |
| L2 | Are the proxy_tools BSD/MIT metadata discrepancy and attribution properly fulfilled? | Original proxy_tools module, bundled BSD text, metadata, notices | PENDING |
| L3 | Does the PyInstaller Bootloader Exception cover both the desktop onedir and onefile native host? | Exact installed PyInstaller licence/exception, built artifacts | PENDING |
| L4 | Are Microsoft Windows runtime redistribution conditions and OpenSSL notices satisfied? | CPython licence, Microsoft Distributable Code terms, installed runtime DLL list, OpenSSL 3.5.9 notices | PENDING |
| L5 | Is the FreeType/FTL credit sufficiently prominent (notices vs About dialog/release notes)? | Pillow LICENSE, current NOTICE.md, actual About dialog | PENDING |
| L6 | Are all bundled WebView2Loader and managed SDK DLLs within the permitted Distributable Code list? | WebView2 SDK NuGet 1.0.3856.49 LICENSE, NOTICE and native payload list | PENDING |

## Candidate payload audit

Do not release until an independent reviewer records, against exact signed
candidate hashes, whether these are present and justified:

- [ ] `THIRD-PARTY-NOTICES.md` and complete `third-party/` included
- [ ] `third-party/inventory.json` reviewed against exact pins
- [ ] `third-party/payload.json` reviewed against actual executable payloads
- [ ] MPL-2.0 certifi exact source matches the currently pinned version
- [ ] LGPLv3 pystray full original source, licence and rebuild path verified
- [ ] All native DLLs and Rust crate notices belong to recorded wheel versions
- [ ] No unexpectedly bundled FFmpeg, Deno, pytest, keys or signing fixtures
- [ ] All L1–L6 decisions recorded, signed and dated by reviewer
- [ ] Any exception documented with risk, remediation and explicit owner approval

## Change control

- Do **not** treat a 41/41 passing PyPI advisory gate as legal compliance.
- Do **not** include `certifi 2026.10.23` or `pydantic-core 2.50.2` in the
  released lock until upstream artefact and Rust licence reviews are complete.
  Offline wheel scripts supply candidate evidence only.
- Any changed dependency or final packaging source requires a new candidate
  and re-review of impacted evidence.

**Release status: BLOCKED until all mandatory items and written sign-off.**
