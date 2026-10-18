# Authenticode production signing procedure

Status: ready to wire once the owner holds a certificate. **No certificate has
been purchased, no key generated, no secret stored, and no production
credential configured.** CI rehearses the exact order with throw-away
certificates (`scripts/rehearse_release_signing.ps1`). Their subject reads
`RAPIDO CI … - NOT AN OFFICIAL SIGNATURE`, and nothing they sign is uploaded.

Provider comparison and identity preparation: `docs/authenticode-options-israel.md`.

## 1. Provider facts re-checked on 2026-10-18

| Fact | Source | Status |
| --- | --- | --- |
| Personal ID (IV) code signing costs USD 129 for 1 year, with multi-year discounts | SSL.com purchase page (https://secure.ssl.com/certificates/iv-codesigning/buy) | Observed |
| Optional YubiKey FIPS token costs USD 379; the certificate also supports cloud signing through eSigner (CSC API) | same | Observed |
| The purchase page names no country restriction | same | Observed, but this is **not** a confirmation that Israel is accepted |
| IV requires a government photo ID showing name, address, year of birth and photograph, plus a selfie with the ID, or the AI-based ID check. If the ID has no address, SSL.com may ask for a secondary document or mail a postcard | SSL.com validation guide (https://www.ssl.com/guide/identity-validation-for-ssl-com-certificates-a-complete-guide/) | Observed. Israel is not named, and translation rules are not stated |
| eSigner OV/IV tiers are listed at 20/100/300/1,000 signings per month for USD 20/85/175/250, with a 30-day free trial. SSL.com's pages contradict each other on this | eSigner pricing guide (https://www.ssl.com/guide/esigner-pricing-for-code-signing/) | **Unconfirmed**: get a written quote |
| GitHub Actions integration uses `sslcom/actions-codesigner` (CodeSignTool, Java), with account username, password, credential ID and TOTP secret | https://www.ssl.com/how-to/cloud-code-signing-integration-with-github-actions/ | Observed |
| eSigner CKA loads the cloud certificate into the Windows store for `signtool.exe`. SSL.com's CKA CI guide mentions an **EV** certificate as the prerequisite | https://www.ssl.com/how-to/how-to-integrate-esigner-cka-with-ci-cd-tools-for-automated-code-signing/ | **Unconfirmed for IV**: ask SSL.com |
| SSL.com offers an eSigner **sandbox** mode | same guide (`MODE=sandbox`) | Useful for a no-cost rehearsal that the owner sets up |

Questions to ask SSL.com in writing before paying:

1. Will you issue Personal ID (IV) code signing to an individual resident in
   Israel, with subject `CN=Samuel Bentouza`, using an Israeli ID card or passport?
2. Which address documents do you accept, and do Hebrew documents need a translation?
3. Does eSigner CKA work with an IV certificate for unattended `signtool` on a
   GitHub-hosted Windows runner? If not, is CodeSignTool the only CI path?
4. What is the exact yearly total for the certificate plus the smallest eSigner
   tier, including tax?
5. What are the reissue, renewal and revocation procedures, and the response time?

Estimated use: about 3 signatures per release (2 executables and 1 installer),
plus rehearsals. The smallest tier is enough.

## 2. Prerequisites

- Windows 10/11 SDK component **Signing Tools for Desktop Apps**
  (`signtool.exe`). `Find-RapidoSignTool` picks the newest
  `Windows Kits\10\bin\10.0.*\x64\signtool.exe`. GitHub-hosted Windows images
  include the SDK. On another machine, install the SDK from Microsoft.
- PowerShell 5.1 or 7 on Windows.
- Inno Setup 6 (`ISCC.exe`) for the installer.
- One of these routes to a certificate in `Cert:\CurrentUser\My`:
  - **Route A, eSigner CKA (preferred if SSL.com confirms IV support):** CKA
    loads the certificate into the store, and `RapidoSigning.psm1` signs with
    `signtool /sha1 <thumbprint>`.
  - **Route B, CodeSignTool:** signs files directly. Use it only through a
    reviewed step that calls `Assert-RapidoSignature` afterwards, so the same
    pin, timestamp and digest checks apply.
  - **Route C, YubiKey token:** signing happens on the owner's machine, never on
    a hosted runner. Use the same module.

## 3. Values the owner records outside the repository

| Value | Where it is used | Secret? |
| --- | --- | --- |
| Certificate SHA-256 pin (64 hex) | `-ExpectedCertificateSha256` | No. Public identity, may be committed later |
| Exact subject string | `-ExpectedSubject` | No |
| SHA-1 store thumbprint | `-CertificateThumbprint` | No |
| Timestamp URL from the provider (RFC 3161), for example `http://ts.ssl.com` | `-TimestampUrl` | No |
| eSigner username, password, TOTP secret, credential ID | GitHub **environment** secrets for `release-signing` only | **Yes** |

GitHub configuration, made by the owner when the certificate exists:

1. Create the environment `release-signing` with required reviewer = owner,
   deployment branches limited to `v*` tags, and no access from forks or pull requests.
2. Store the four eSigner values as environment secrets only, never as
   repository secrets.
3. Pin any third-party signing action to a full commit SHA, never `@develop`.
4. Keep `publishable=false` until the reviewed change in section 5 is merged.

## 4. Exact signing order

| Step | Command (module functions) | Stops when |
| --- | --- | --- |
| 1 | Build `Rapido.exe` and `RapidoNativeHost.exe`. Record their unsigned SHA-256 values | build fails |
| 2 | `Invoke-RapidoSign -Path Rapido.exe,RapidoNativeHost.exe -CertificateThumbprint … -ExpectedCertificateSha256 … -TimestampUrl …` | the store certificate is not the pinned one, or SignTool fails 3 times |
| 3 | `Assert-RapidoSignature` on both, with pin and subject | status is not Valid, wrong signer or subject, missing timestamp, SHA-1 digest, or `signtool verify /pa` fails |
| 4 | Build the installer **only** from the verified folder: `ISCC /DPayloadDir=<verified folder>` | build fails |
| 5 | Sign and verify the installer, as in steps 2–3 | same checks |
| 6 | Create the portable ZIP from the same verified folder | — |
| 7 | `verify_release_candidate.ps1 -Record`: approved manifest (installer, ZIP, every payload file, commit, pin) | any signature problem |
| 8 | Windows 10/11 validation on that exact candidate (`docs/windows-validation-matrix.md`) | any failure |
| 9 | Download the candidate independently and run `verify_release_candidate.ps1` against the manifest | any hash, file-set or signature difference |
| 10 | Owner authorizes publication | — |

The installer no longer copies a second `RapidoNativeHost.exe` from `dist\`.
Before this fix, the unsigned onefile copy overwrote the bundle copy at
install time.

## 5. Code change still needed when the certificate exists

These changes are reviewed in a PR and are not done now:

1. Add a `sign` job on `windows-latest` with `environment: release-signing`,
   triggered only for `v*` tags, that downloads the unsigned build artifact
   and runs steps 2–7 with Route A or B.
2. Commit the public certificate pin and subject in the workflow, so a
   different certificate fails.
3. Replace `publishable=false` with the result of step 7, plus the owner's
   environment approval.
4. Keep the rehearsal and its negative cases running on every pull request.

## 6. Timestamp and verification

- Signature digest SHA-256 (`/fd SHA256`). Timestamp RFC 3161 with SHA-256
  (`/tr … /td SHA256`).
- Verification requires `TimeStamperCertificate` to be present, so a signature
  stays valid after the certificate expires.
- `signtool verify /pa /v` runs as an independent check. The module also
  requires `Hash of file (sha256)` in its output.
- The CA/Browser Forum caps new public code-signing certificates at 460 days
  from 2026-03-01. Plan the renewal overlap so a new certificate is ready
  before the old one expires. Changing the certificate changes the pin, so
  update the pin before the first release with the new certificate.

## 7. Protection of keys and credentials

- The key never leaves the provider's HSM (eSigner) or the FIPS token.
  Exporting a PFX is not part of this design, and tests reject the strings
  `.pfx`, `.p12`, `Export-PfxCertificate` and `ConvertTo-SecureString` in the
  signing scripts.
- Credentials exist only in the `release-signing` environment. Pull requests,
  forks, `main` and manual builds never receive them.
- Rotate the eSigner password and TOTP secret if a runner log or workflow is
  ever suspected to leak them. Revoke the certificate if the key is suspected
  to be misused.
- Never sign anything not built by the tagged workflow, and never sign a file
  from a pull request.

## 8. Tests

| Case | Where | Status |
| --- | --- | --- |
| Correct signer, timestamped, SHA-256 | CI rehearsal | Automated |
| Unsigned file | CI rehearsal + `test_windows_signature.ps1` | Automated |
| File modified after signing | same | Automated |
| Valid signature from another publisher | same | Automated |
| Signature without timestamp | CI rehearsal | Automated |
| Renamed substitution | CI rehearsal | Automated |
| Identical download accepted, ZIP with a planted DLL rejected | CI rehearsal | Automated |
| Expired or revoked certificate | Provider sandbox or real certificate | Pending: needs a real CA chain |
| SmartScreen reputation of the real certificate | Windows 10/11 machines | Pending owner authorization |
