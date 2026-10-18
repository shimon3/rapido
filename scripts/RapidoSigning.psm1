# Rapido Authenticode signing and verification primitives.
#
# This module never creates, exports, reads or stores a private key, PIN,
# password or token. Signing uses SignTool with a certificate that is already
# available in the Windows certificate store, for example through a hardware
# token or a cloud key adapter such as SSL.com eSigner CKA. The only
# certificate identity it accepts is the SHA-256 pin passed by the caller.
# Compatible with Windows PowerShell 5.1 and PowerShell 7 on Windows.

Set-StrictMode -Version 3

function Find-RapidoSignTool {
  [CmdletBinding()]
  param()
  $roots = @(
    (Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'),
    (Join-Path $env:ProgramFiles 'Windows Kits\10\bin')
  ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
  $candidates = foreach ($root in $roots) {
    Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -match '^10\.0\.\d+\.\d+$' } |
      ForEach-Object {
        $path = Join-Path $_.FullName 'x64\signtool.exe'
        if (Test-Path -LiteralPath $path -PathType Leaf) {
          [pscustomobject]@{ Version = [version]$_.Name; Path = $path }
        }
      }
  }
  $best = $candidates | Sort-Object Version -Descending | Select-Object -First 1
  if (-not $best) {
    throw 'signtool.exe not found: install the Windows 10/11 SDK "Signing Tools for Desktop Apps".'
  }
  return $best.Path
}

function Get-RapidoCertificateSha256 {
  [CmdletBinding()]
  param([Parameter(Mandatory = $true)] [System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    return ([BitConverter]::ToString($sha.ComputeHash($Certificate.RawData))).Replace('-', '').ToLowerInvariant()
  } finally {
    $sha.Dispose()
  }
}

function Get-RapidoFileSha256 {
  # .NET hashing: Get-FileHash is unavailable when Windows PowerShell inherits
  # PowerShell 7's PSModulePath.
  [CmdletBinding()]
  param([Parameter(Mandatory = $true)] [string]$Path)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $stream = [System.IO.File]::OpenRead($Path)
  try {
    return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
  } finally {
    $stream.Dispose()
    $sha.Dispose()
  }
}

function Assert-RapidoSha256Pin {
  param([string]$Pin)
  if ($Pin -notmatch '^[0-9a-fA-F]{64}$') {
    throw 'The expected certificate identity must be a 64-character SHA-256 hex value.'
  }
  return $Pin.ToLowerInvariant()
}

function Invoke-RapidoSign {
  # Signs files in place with SHA-256 digests and an RFC 3161 SHA-256
  # timestamp. The certificate is selected by its SHA-1 store thumbprint (what
  # SignTool accepts) and then confirmed against the SHA-256 pin.
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)] [string[]]$Path,
    [Parameter(Mandatory = $true)] [string]$CertificateThumbprint,
    [Parameter(Mandatory = $true)] [string]$ExpectedCertificateSha256,
    [string]$TimestampUrl,
    [switch]$NoTimestamp,
    [string]$Description = 'Rapido',
    [string]$DescriptionUrl = 'https://github.com/shimon3/rapido',
    [string]$SignTool = (Find-RapidoSignTool),
    [int]$Attempts = 3
  )
  $pin = Assert-RapidoSha256Pin $ExpectedCertificateSha256
  if ($CertificateThumbprint -notmatch '^[0-9a-fA-F]{40}$') {
    throw 'CertificateThumbprint must be the 40-character SHA-1 store thumbprint.'
  }
  if (-not $NoTimestamp -and $TimestampUrl -notmatch '^https?://[^\s"]+$') {
    throw 'A timestamp URL is required unless -NoTimestamp is used for a negative test.'
  }
  $cert = Get-ChildItem -LiteralPath Cert:\CurrentUser\My |
    Where-Object { $_.Thumbprint -eq $CertificateThumbprint.ToUpperInvariant() } |
    Select-Object -First 1
  if (-not $cert) { throw 'The signing certificate is not available in CurrentUser\My.' }
  if ((Get-RapidoCertificateSha256 $cert) -ne $pin) {
    throw 'The selected certificate does not match the expected SHA-256 identity.'
  }
  foreach ($file in $Path) {
    $full = (Resolve-Path -LiteralPath $file).Path
    $arguments = @('sign', '/fd', 'SHA256', '/sha1', $CertificateThumbprint, '/s', 'My',
      '/d', $Description, '/du', $DescriptionUrl)
    if (-not $NoTimestamp) { $arguments += @('/tr', $TimestampUrl, '/td', 'SHA256') }
    $arguments += $full
    $done = $false
    for ($attempt = 1; $attempt -le $Attempts -and -not $done; $attempt++) {
      & $SignTool @arguments | Out-Host
      if ($LASTEXITCODE -eq 0) {
        $done = $true
      } elseif ($attempt -lt $Attempts) {
        # Timestamp services can fail transiently; signing itself is idempotent.
        Start-Sleep -Seconds (5 * $attempt)
      }
    }
    if (-not $done) { throw "SignTool failed for $full" }
  }
}

function Test-RapidoSignature {
  # Returns an object with ok/reasons; never throws for a bad file so negative
  # tests can assert the exact reason.
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)] [string]$Path,
    [Parameter(Mandatory = $true)] [string]$ExpectedCertificateSha256,
    [string]$ExpectedSubject,
    [switch]$AllowMissingTimestamp,
    [string]$SignTool = (Find-RapidoSignTool)
  )
  $pin = Assert-RapidoSha256Pin $ExpectedCertificateSha256
  $full = (Resolve-Path -LiteralPath $Path).Path
  $reasons = New-Object System.Collections.Generic.List[string]
  $signature = Get-AuthenticodeSignature -LiteralPath $full
  $signerPin = $null
  $subject = $null
  if ($signature.Status -ne 'Valid') { $reasons.Add('status-' + $signature.Status.ToString()) }
  if ($signature.SignerCertificate) {
    $signerPin = Get-RapidoCertificateSha256 $signature.SignerCertificate
    $subject = $signature.SignerCertificate.Subject
    if ($signerPin -ne $pin) { $reasons.Add('unexpected-signer') }
    if ($ExpectedSubject -and $subject -ne $ExpectedSubject) { $reasons.Add('unexpected-subject') }
  } else {
    $reasons.Add('unsigned')
  }
  if (-not $signature.TimeStamperCertificate -and -not $AllowMissingTimestamp) {
    $reasons.Add('missing-timestamp')
  }
  # Independent check of the digest algorithm and policy with SignTool.
  # Windows PowerShell 5.1 turns redirected native stderr into terminating
  # errors under 'Stop'; a rejected file must yield a reason, not an exception.
  $previous = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    $output = (& $SignTool verify /pa /v $full 2>&1 | ForEach-Object { "$_" }) -join "`n"
    $verifyExit = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previous
  }
  if ($verifyExit -ne 0) { $reasons.Add('signtool-verify-failed') }
  if ($signature.SignerCertificate -and $output -notmatch 'Hash of file \(sha256\)') {
    $reasons.Add('digest-not-sha256')
  }
  [pscustomobject]@{
    path = $full
    sha256 = (Get-RapidoFileSha256 $full)
    ok = ($reasons.Count -eq 0)
    reasons = @($reasons)
    status = $signature.Status.ToString()
    signer_subject = $subject
    signer_certificate_sha256 = $signerPin
    timestamped = [bool]$signature.TimeStamperCertificate
    timestamp_subject = if ($signature.TimeStamperCertificate) { $signature.TimeStamperCertificate.Subject } else { $null }
    signtool_verify_exit = $verifyExit
  }
}

function Assert-RapidoSignature {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)] [string[]]$Path,
    [Parameter(Mandatory = $true)] [string]$ExpectedCertificateSha256,
    [string]$ExpectedSubject
  )
  $results = foreach ($file in $Path) {
    Test-RapidoSignature -Path $file -ExpectedCertificateSha256 $ExpectedCertificateSha256 -ExpectedSubject $ExpectedSubject
  }
  $bad = @($results | Where-Object { -not $_.ok })
  if ($bad.Count) {
    $details = ($bad | ForEach-Object { (Split-Path -Leaf $_.path) + ': ' + ($_.reasons -join ',') }) -join '; '
    throw "Authenticode verification failed: $details"
  }
  return $results
}

function New-RapidoHashManifest {
  # Records SHA-256 of every file under a folder (relative paths, sorted) so a
  # later copy can be proven identical to the approved candidate.
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)] [string]$Root,
    [string[]]$ExtraFile = @()
  )
  $base = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')
  $entries = @(Get-ChildItem -LiteralPath $base -Recurse -File | Sort-Object FullName | ForEach-Object {
    [pscustomobject]@{
      path = $_.FullName.Substring($base.Length + 1).Replace('\', '/')
      sha256 = (Get-RapidoFileSha256 $_.FullName)
      bytes = $_.Length
    }
  })
  foreach ($file in $ExtraFile) {
    $item = Get-Item -LiteralPath $file
    $entries += [pscustomobject]@{
      path = $item.Name
      sha256 = (Get-RapidoFileSha256 $item.FullName)
      bytes = $item.Length
    }
  }
  return $entries
}

Export-ModuleMember -Function Find-RapidoSignTool, Get-RapidoCertificateSha256, Get-RapidoFileSha256, Invoke-RapidoSign,
  Test-RapidoSignature, Assert-RapidoSignature, New-RapidoHashManifest
