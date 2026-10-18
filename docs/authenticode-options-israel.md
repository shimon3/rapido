# Authenticode options for an individual developer in Israel

Research date: 2026-10-18. Intended subject identity: **Samuel Bentouza,
Israel**. Prices and eligibility can change and must be reconfirmed directly
with the provider before purchase. **No certificate has been purchased,
ordered, generated, or activated by this work.**

## Recommendation

Ask SSL.com and Certum for written pre-sales confirmation that they will issue a
publicly trusted individual code-signing certificate with the exact subject name
Samuel Bentouza and accept the available Israeli identity/address documents.

The practical first choice for GitHub-hosted automation is SSL.com Personal ID
(IV) with eSigner because it explicitly supports an individual identity and a
cloud HSM/CI flow. Certum Standard Code Signing in the Cloud is a credible lower
listed-price alternative, but its store currently reports the product out of
stock and its unattended GitHub Actions behavior must be demonstrated before
selection. Do not buy either until identity eligibility, total tax/currency
cost, Israel availability, signing quota, and CI authentication are confirmed.

## Current comparison

| Option | Publicly stated price | Individual / Israel fit | Key custody and CI consequence | Decision |
| --- | --- | --- | --- | --- |
| SSL.com Personal ID Code Signing + eSigner Tier 1 | USD 129/year for the IV certificate; eSigner annual Tier 1 USD 180 for 240 signings after the initial 30-day period | IV is explicitly for an individual. Israel acceptance is not promised on the cited purchase page, so eligibility must be confirmed before payment. | Cloud HSM; SSL.com documents CI/CD integration. No PFX should enter GitHub. | Preferred candidate, pending written eligibility and exact total. |
| Certum Standard Code Signing in the Cloud | Listed from EUR 209; store currently says out of stock | Certum documents issuance to an individual and requests identity proof plus a utility bill. Automatic verification supports documents from many countries, but Israel and document-language acceptance must be confirmed. | SimplySign cloud key. Confirm whether unattended, approval-gated GitHub signing is supported; do not assume a mobile flow is CI-safe. | Second candidate, pending stock and automation proof. |
| Sectigo OV Code Signing | Official direct price starts at USD 536.25/year on a five-year product; shorter terms cost more | Sectigo's current validation guidance covers a verified individual, government photo ID, address evidence, and a verified callback. Confirm Israel shipping and the exact one-year total. | Hardware token or customer HSM with attestation. A shipped token is not usable on a GitHub-hosted runner without separate controlled signing infrastructure. | Technically compatible but costly and operationally awkward. |
| DigiCert Code Signing | USD 696/year with own token/HSM, USD 840/year with supplied USB token, or USD 996/year with KeyLocker | The current retail comparison presents Organization Validation, and DigiCert's request guide requires an active validated organization. It is not the default route for Samuel Bentouza as an unincorporated individual. | Token, HSM, or KeyLocker cloud service. | Exclude unless DigiCert confirms an individual product in writing. |
| GlobalSign Code Signing | No usable individual price shown on the current shop page | Current shop says certificates are issued only to a legally registered organization. | Organization product. | Exclude for an individual identity. |
| Microsoft Azure Artifact Signing | Basic USD 9.99/month for up to 5,000 signatures | Microsoft currently permits Public Trust organizations in Israel, but individual developers only in the United States or Canada. An Israeli individual is not eligible under the published rule. | Managed HSM and excellent GitHub integration. | Exclude for the current individual identity; reconsider only if eligibility changes or a qualifying legal organization is used. |
| Microsoft Store | Registration/distribution route rather than an individual Authenticode purchase | Store distribution is worldwide, but Rapido's current Chrome/Edge/Firefox native-registration model is not yet proven for MSIX and an unpackaged EXE/MSI submission still needs a trusted publisher signature. | Store can re-sign MSIX; compatibility remains the blocker. | Not the first beta route. |

Sources:

- SSL.com Personal ID purchase and eSigner pricing:
  https://secure.ssl.com/certificates/iv-codesigning/buy
  and https://www.ssl.com/products/software-integrity/signing-service/
- Certum cloud product, pricing, and required documents:
  https://shop.certum.eu/standard-code-signing-in-the-cloud.html?___store=certum_en
  and https://support.certum.eu/en/code-signing-required-documents/
- Sectigo product pricing and individual validation:
  https://www.sectigo.com/ssl-certificates-tls/code-signing
  and https://www.sectigo.com/faqs/detail/OV-Code-Signing-Validation-for-Organizations-and-Individuals
- DigiCert comparison and validation guide:
  https://www.digicert.com/signing/compare-code-signing-certificates
  and https://docs.digicert.com/en/certcentral/order-and-manage-certificates/request-certificates/request-a-code-signing-or-ev-code-signing-certificate/request-code-signing-certificate.html
- GlobalSign shop:
  https://shop.globalsign.com/en/code-signing
- Microsoft Artifact Signing availability/pricing and Windows signing options:
  https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart
  and https://azure.microsoft.com/en-us/products/artifact-signing
  and https://learn.microsoft.com/windows/apps/package-and-deploy/code-signing-options

## Identity preparation before an order

Prepare but do not upload until a provider is selected:

1. passport or government photo ID showing the exact Latin spelling to appear in
   the certificate;
2. recent proof of residential address matching the order;
3. an email account and independently verifiable telephone number;
4. confirmation of whether the software is distributed personally, as an Israeli
   sole proprietor, or through a registered legal entity;
5. a public Rapido project page and repository linking Samuel Bentouza to the
   software;
6. written confirmation from the provider of the certificate subject fields,
   total price including tax and delivery, accepted Israeli documents,
   translation requirements, issue time, renewal/reissue rules, and revocation
   support.

Do not use a self-signed certificate, disposable CI fixture, document-signing
certificate, or certificate issued to a different publisher as the production
identity.

## Technical signing plan

Public code-signing keys issued after June 2023 must be protected by approved
hardware or a compliant signing service. A normal exportable PFX stored in a
GitHub secret is therefore not the design.

For Windows 10 and Windows 11, use Authenticode with SHA-256 and an RFC 3161
SHA-256 timestamp:

1. build Rapido.exe and RapidoNativeHost.exe;
2. sign each through the selected provider's token/cloud interface;
3. run SignTool verification and independently inspect Authenticode status,
   chain, timestamp, subject, issuer, serial number, and SHA-256 certificate
   identity;
4. build the Inno Setup installer only from those verified files;
5. sign and verify the installer;
6. create the portable ZIP only from the verified signed payload;
7. publish file SHA-256 hashes and a signed release manifest;
8. download the candidate independently and repeat verification before approval.

The signing identity must be available only to an approval-protected release
environment. Pull requests and ordinary builds stay unsigned and
non-publishing. A valid signature from an unexpected subject or certificate
must fail closed.

Microsoft recommends SHA-256 file digests and RFC 3161 timestamps with SHA-256.
The CA/Browser Forum requires hardware-backed key protection and limits newly
issued public code-signing certificates to at most 460 days from 2026-03-01.

## Required non-publishing rehearsal after owner approval and purchase

- sign disposable copies first; never overwrite the only unsigned evidence;
- verify valid signer, timestamp, and exact approved certificate identity;
- reject unsigned, tampered, wrong-signer, expired, revoked, indeterminate,
  wrong-version, and renamed-substitution candidates;
- prove a pull request cannot access the signing credential;
- prove a tag alone cannot publish;
- preserve and compare pre-signing and post-signing hashes;
- run installation, upgrade, repair, rollback/failure, uninstall, Chrome, Edge,
  and Firefox tests on Windows 10 and Windows 11;
- retain no private key material in repositories, logs, artifacts, caches, or
  application directories.

A production certificate authenticates a publisher and protects on-disk
integrity after signing. It does not prevent process injection or by itself
create the independently protected same-user trust anchor required to close
issue #26.
