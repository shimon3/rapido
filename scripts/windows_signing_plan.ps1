[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$BundlePath,

  [string]$InstallerPath,

  [Parameter(Mandatory = $true)]
  [string]$OutputPath
)

$ErrorActionPreference = 'Stop'

# Audit only: this script never signs files and never reads a certificate,
# private key, token, PIN, password, or GitHub secret.
$bundle = (Resolve-Path -LiteralPath $BundlePath).Path
$requiredPaths = @(
  (Join-Path $bundle 'Rapido.exe'),
  (Join-Path $bundle 'RapidoNativeHost.exe')
)

if ($InstallerPath) {
  $requiredPaths += (Resolve-Path -LiteralPath $InstallerPath).Path
}

foreach ($requiredPath in $requiredPaths) {
  if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
    throw "Required signing target is missing: $requiredPath"
  }
}

$privateKeyExtensions = @('.pfx', '.p12', '.pvk', '.key')
$privateKeyFiles = @(
  Get-ChildItem -LiteralPath $bundle -Recurse -File |
    Where-Object { $privateKeyExtensions -contains $_.Extension.ToLowerInvariant() }
)
if ($privateKeyFiles.Count -ne 0) {
  throw "Private-key material must not be present in the Windows bundle."
}

$portableExtensions = @('.exe', '.dll', '.pyd', '.ocx', '.sys')
$targets = @(
  Get-ChildItem -LiteralPath $bundle -Recurse -File |
    Where-Object { $portableExtensions -contains $_.Extension.ToLowerInvariant() }
)
if ($InstallerPath) {
  $targets += Get-Item -LiteralPath $InstallerPath
}
$targets = @($targets | Sort-Object FullName -Unique)
if ($targets.Count -eq 0) {
  throw "No Windows executable payload was found."
}

$primaryNames = @('Rapido.exe', 'RapidoNativeHost.exe')
$records = foreach ($target in $targets) {
  $signature = Get-AuthenticodeSignature -LiteralPath $target.FullName
  $stage = if ($primaryNames -contains $target.Name) {
    1
  } elseif ($InstallerPath -and $target.FullName -eq (Resolve-Path -LiteralPath $InstallerPath).Path) {
    2
  } else {
    0
  }

  [pscustomobject]@{
    path = $target.FullName
    sha256 = (Get-FileHash -LiteralPath $target.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    signing_stage = $stage
    required_first_party_target = $requiredPaths -contains $target.FullName
    signature_status = $signature.Status.ToString()
    signer_subject = if ($signature.SignerCertificate) {
      $signature.SignerCertificate.Subject
    } else {
      $null
    }
  }
}

$report = [ordered]@{
  schema = 1
  mode = 'audit-only'
  production_signing_enabled = $false
  generated_utc = [DateTime]::UtcNow.ToString('o')
  signing_order = @(
    'Sign and verify Rapido.exe and RapidoNativeHost.exe.',
    'Build the installer from the verified signed payload.',
    'Sign and verify the installer.',
    'Create the portable ZIP from the verified signed payload.'
  )
  required_targets = $requiredPaths
  executable_payload_count = $records.Count
  files = @($records)
  note = 'A green audit does not mean the files are signed or trusted.'
}

$outputDirectory = Split-Path -Parent $OutputPath
if ($outputDirectory) {
  New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "Signing audit wrote $($records.Count) executable records to $OutputPath"
