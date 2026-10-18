# Non-publishing rehearsal of the production signing order, on a disposable
# GitHub-hosted runner only. It signs COPIES with throw-away certificates whose
# subject says they are not official, runs the negative cases, writes a JSON
# report, and deletes every certificate, private key and signed copy. The real
# dist\ files and the uploaded artifact stay unsigned.
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)] [string]$BundlePath,
  [Parameter(Mandatory = $true)] [string]$InstallerScript,
  [Parameter(Mandatory = $true)] [string]$AppVersion,
  [Parameter(Mandatory = $true)] [string]$AppFileVersion,
  [Parameter(Mandatory = $true)] [string]$ReportPath,
  [string[]]$TimestampUrl = @('http://timestamp.digicert.com', 'http://timestamp.sectigo.com')
)

$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:RUNNER_OS -ne 'Windows') {
  throw 'The signing rehearsal requires a disposable GitHub-hosted Windows runner'
}
Import-Module (Join-Path $PSScriptRoot 'RapidoSigning.psm1') -Force

$work = Join-Path $env:RUNNER_TEMP ('rapido-signing-rehearsal-' + [guid]::NewGuid().ToString('N'))
$stores = @(@('Root', 'LocalMachine'), @('TrustedPublisher', 'CurrentUser'))
$certs = @()
$cases = New-Object System.Collections.Generic.List[object]

function New-DisposableSigner([string]$label) {
  $cert = New-SelfSignedCertificate -Type CodeSigningCert `
    -Subject ("CN=RAPIDO CI $label - NOT AN OFFICIAL SIGNATURE, O=Disposable test " + [guid]::NewGuid().ToString('N')) `
    -CertStoreLocation 'Cert:\CurrentUser\My' -KeyAlgorithm RSA -KeyLength 3072 -HashAlgorithm SHA256 `
    -KeyExportPolicy NonExportable -NotAfter (Get-Date).AddDays(1)
  foreach ($location in $stores) {
    # Trusting the throw-away root is acceptable only on this disposable VM.
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($location[0], $location[1])
    try { $store.Open('ReadWrite'); $store.Add($cert) } finally { $store.Close() }
  }
  return $cert
}

function Sign-WithFallback($files, $cert, [switch]$NoTimestamp) {
  $pin = Get-RapidoCertificateSha256 $cert
  if ($NoTimestamp) {
    Invoke-RapidoSign -Path $files -CertificateThumbprint $cert.Thumbprint -ExpectedCertificateSha256 $pin -NoTimestamp
    return
  }
  $last = $null
  foreach ($url in $TimestampUrl) {
    try {
      Invoke-RapidoSign -Path $files -CertificateThumbprint $cert.Thumbprint -ExpectedCertificateSha256 $pin -TimestampUrl $url
      return
    } catch { $last = $_ }
  }
  throw $last
}

function Expect-Rejected($name, $path, $pin, $reason) {
  $result = Test-RapidoSignature -Path $path -ExpectedCertificateSha256 $pin
  $passed = (-not $result.ok) -and ($result.reasons -contains $reason)
  $cases.Add([pscustomobject]@{ case = $name; expected = "rejected:$reason"; passed = $passed; reasons = $result.reasons })
  if (-not $passed) { throw "Negative case '$name' was not rejected for '$reason' (got: $($result.reasons -join ','))" }
}

$exitCode = 1
try {
  New-Item -ItemType Directory -Path $work | Out-Null
  $payload = Join-Path $work 'payload\Rapido'
  New-Item -ItemType Directory -Path (Split-Path -Parent $payload) | Out-Null
  Copy-Item -LiteralPath (Resolve-Path -LiteralPath $BundlePath).Path -Destination $payload -Recurse
  $primary = @((Join-Path $payload 'Rapido.exe'), (Join-Path $payload 'RapidoNativeHost.exe'))
  $before = @{}
  foreach ($file in $primary) { $before[(Split-Path -Leaf $file)] = (Get-RapidoFileSha256 $file) }
  $unsignedCopy = Join-Path $work 'unsigned-Rapido.exe'
  Copy-Item -LiteralPath $primary[0] -Destination $unsignedCopy

  $signer = New-DisposableSigner 'REHEARSAL'
  $certs += $signer
  $wrong = New-DisposableSigner 'WRONG SIGNER'
  $certs += $wrong
  $pin = Get-RapidoCertificateSha256 $signer

  # Stage 1: sign and verify both first-party executables.
  Sign-WithFallback $primary $signer
  $stage1 = Assert-RapidoSignature -Path $primary -ExpectedCertificateSha256 $pin -ExpectedSubject $signer.Subject

  # Stage 2: build the installer only from the verified signed payload.
  $iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
  if (-not (Test-Path -LiteralPath $iscc)) { throw 'Inno Setup was not installed by the build step' }
  $out = Join-Path $work 'out'
  & $iscc "/DAppVersion=$AppVersion" "/DAppFileVersion=$AppFileVersion" "/DPayloadDir=$payload" "/O$out" $InstallerScript | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "Rehearsal installer build failed: $LASTEXITCODE" }
  $setup = (Get-ChildItem -LiteralPath $out -Filter 'Rapido-Setup-*.exe' | Select-Object -First 1).FullName

  # Stage 3: sign and verify the installer.
  Sign-WithFallback @($setup) $signer
  $stage3 = Assert-RapidoSignature -Path @($setup) -ExpectedCertificateSha256 $pin -ExpectedSubject $signer.Subject

  # Stage 4: portable ZIP from the same verified payload, then a hash manifest.
  $zip = Join-Path $out "Rapido-$AppVersion-portable.zip"
  Compress-Archive -Path $payload -DestinationPath $zip
  $manifest = New-RapidoHashManifest -Root $payload -ExtraFile @($setup, $zip)

  # The payload must still be the verified one after packaging.
  Assert-RapidoSignature -Path $primary -ExpectedCertificateSha256 $pin | Out-Null

  # Stage 5: approve the tested files, then prove an identical copy passes and
  # a modified copy is refused by the candidate verification procedure.
  $verify = Join-Path $PSScriptRoot 'verify_release_candidate.ps1'
  $approved = Join-Path $work 'approved.json'
  $commit = if ($env:GITHUB_SHA -match '^[0-9a-f]{40}$') { $env:GITHUB_SHA } else { '0' * 40 }
  & powershell -NoProfile -ExecutionPolicy Bypass -File $verify -Record -CandidateDir $out -ApprovedManifest $approved `
    -ExpectedCertificateSha256 $pin -Version $AppVersion -Commit $commit | Out-Host
  if ($LASTEXITCODE -ne 0) { throw 'Recording the approved candidate failed' }
  $copy = Join-Path $work 'downloaded'
  Copy-Item -LiteralPath $out -Destination $copy -Recurse
  & powershell -NoProfile -ExecutionPolicy Bypass -File $verify -CandidateDir $copy -ApprovedManifest $approved `
    -ExpectedCertificateSha256 $pin -ExpectedSubject $signer.Subject | Out-Host
  $cases.Add([pscustomobject]@{ case = 'identical download'; expected = 'accepted'; passed = ($LASTEXITCODE -eq 0); reasons = @() })
  if ($LASTEXITCODE -ne 0) { throw 'An identical copy of the approved candidate was rejected' }
  $modified = Join-Path $work 'modified'
  New-Item -ItemType Directory -Path $modified | Out-Null
  Copy-Item -LiteralPath $setup -Destination $modified
  $extra = Join-Path $work 'extra\Rapido'
  New-Item -ItemType Directory -Path (Split-Path -Parent $extra) | Out-Null
  Copy-Item -LiteralPath $payload -Destination $extra -Recurse
  Set-Content -LiteralPath (Join-Path $extra 'planted.dll') -Value 'not a real library' -Encoding ASCII
  Compress-Archive -Path $extra -DestinationPath (Join-Path $modified (Split-Path -Leaf $zip))
  & powershell -NoProfile -ExecutionPolicy Bypass -File $verify -CandidateDir $modified -ApprovedManifest $approved `
    -ExpectedCertificateSha256 $pin | Out-Host
  $cases.Add([pscustomobject]@{ case = 'portable ZIP with a planted file'; expected = 'rejected'; passed = ($LASTEXITCODE -eq 1); reasons = @() })
  if ($LASTEXITCODE -ne 1) { throw 'A modified candidate was not rejected' }

  # Negative cases: every one must be refused for the stated reason.
  Expect-Rejected 'unsigned executable' $unsignedCopy $pin 'unsigned'
  $tampered = Join-Path $work 'tampered-Rapido.exe'
  Copy-Item -LiteralPath $primary[0] -Destination $tampered
  $bytes = [IO.File]::ReadAllBytes($tampered)
  $bytes[64] = $bytes[64] -bxor 1  # DOS stub: covered by the Authenticode digest.
  [IO.File]::WriteAllBytes($tampered, $bytes)
  Expect-Rejected 'tampered after signing' $tampered $pin 'status-HashMismatch'
  $other = Join-Path $work 'wrong-signer-Rapido.exe'
  Copy-Item -LiteralPath $unsignedCopy -Destination $other
  Sign-WithFallback @($other) $wrong
  Expect-Rejected 'valid signature from another publisher' $other $pin 'unexpected-signer'
  $noTs = Join-Path $work 'untimestamped-Rapido.exe'
  Copy-Item -LiteralPath $unsignedCopy -Destination $noTs
  Sign-WithFallback @($noTs) $signer -NoTimestamp
  Expect-Rejected 'signature without timestamp' $noTs $pin 'missing-timestamp'
  $renamed = Join-Path $work 'RapidoNativeHost.exe'
  Copy-Item -LiteralPath $other -Destination $renamed
  Expect-Rejected 'renamed substitution of another signed file' $renamed $pin 'unexpected-signer'

  $report = [ordered]@{
    schema = 1
    mode = 'disposable-rehearsal'
    official_signature = $false
    note = 'Throw-away certificates on a disposable runner. Nothing signed here is uploaded or published.'
    signer_subject = $signer.Subject
    signing_order = @('Rapido.exe + RapidoNativeHost.exe', 'verify', 'installer from signed payload', 'sign installer', 'verify', 'portable zip', 'hash manifest')
    unsigned_sha256 = $before
    stage1_payload = @($stage1)
    stage3_installer = @($stage3)
    negative_cases = @($cases)
    manifest_entries = $manifest.Count
    manifest_sha256_of_installer = ($manifest | Where-Object { $_.path -like 'Rapido-Setup-*.exe' }).sha256
  }
  $folder = Split-Path -Parent $ReportPath
  if ($folder) { New-Item -ItemType Directory -Path $folder -Force | Out-Null }
  $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
  Write-Host "Signing rehearsal passed: 2 payload files + installer signed and verified, $($cases.Count) negative cases rejected."
  $exitCode = 0
} finally {
  foreach ($cert in $certs) {
    foreach ($location in $stores) {
      $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($location[0], $location[1])
      try { $store.Open('ReadWrite'); $store.Remove($cert) } finally { $store.Close() }
    }
    Remove-Item -LiteralPath ('Cert:\CurrentUser\My\' + $cert.Thumbprint) -DeleteKey -ErrorAction SilentlyContinue
  }
  if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force }
  Write-Host 'Disposable rehearsal certificates, keys and signed copies removed'
}
exit $exitCode
