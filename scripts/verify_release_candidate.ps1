# Proves that the files about to be published are exactly the files that were
# tested and approved. Read-only: it hashes, extracts the portable ZIP to a
# temporary folder, checks Authenticode with the pinned publisher, and writes a
# report. It never signs, uploads or publishes.
#
#   1. After testing, record the approved candidate:
#        .\verify_release_candidate.ps1 -Record -CandidateDir <tested files> `
#          -ApprovedManifest approved.json -Version 1.3.0-beta.1 -Commit <sha> `
#          -ExpectedCertificateSha256 <pin>
#   2. Before publication, check an independent download against it:
#        .\verify_release_candidate.ps1 -CandidateDir <downloaded files> `
#          -ApprovedManifest approved.json -ExpectedCertificateSha256 <pin>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)] [string]$CandidateDir,
  [Parameter(Mandatory = $true)] [string]$ApprovedManifest,
  [Parameter(Mandatory = $true)] [string]$ExpectedCertificateSha256,
  [string]$ExpectedSubject,
  [switch]$Record,
  [string]$Version,
  [string]$Commit,
  [string]$ReportPath
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'RapidoSigning.psm1') -Force
$pin = $ExpectedCertificateSha256.ToLowerInvariant()
$candidate = (Resolve-Path -LiteralPath $CandidateDir).Path
$problems = New-Object System.Collections.Generic.List[string]
$signatures = New-Object System.Collections.Generic.List[object]

function Get-Release([string]$folder) {
  $setup = @(Get-ChildItem -LiteralPath $folder -File -Filter 'Rapido-Setup-*.exe')
  $zip = @(Get-ChildItem -LiteralPath $folder -File -Filter 'Rapido-*-portable.zip')
  if ($setup.Count -ne 1 -or $zip.Count -ne 1) {
    throw 'The candidate folder must contain exactly one Rapido-Setup-*.exe and one Rapido-*-portable.zip'
  }
  return @{ setup = $setup[0]; zip = $zip[0] }
}

function Get-Payload([string]$zipPath, [string]$into) {
  Expand-Archive -LiteralPath $zipPath -DestinationPath $into
  $root = Join-Path $into 'Rapido'
  if (-not (Test-Path -LiteralPath (Join-Path $root 'Rapido.exe'))) { throw 'Portable ZIP has no Rapido\Rapido.exe' }
  return New-RapidoHashManifest -Root $root
}

$release = Get-Release $candidate
$temp = Join-Path ([IO.Path]::GetTempPath()) ('rapido-verify-' + [guid]::NewGuid().ToString('N'))
try {
  $payload = Get-Payload $release.zip.FullName $temp
  # Only the two distributable files; reports or manifests beside them are ignored.
  $names = @($release.setup.Name, $release.zip.Name)
  $files = @(New-RapidoHashManifest -Root $candidate | Where-Object { $names -contains $_.path })
  foreach ($exe in @($release.setup.FullName, (Join-Path $temp 'Rapido\Rapido.exe'), (Join-Path $temp 'Rapido\RapidoNativeHost.exe'))) {
    $result = Test-RapidoSignature -Path $exe -ExpectedCertificateSha256 $pin -ExpectedSubject $ExpectedSubject
    $signatures.Add($result)
    if (-not $result.ok) { $problems.Add("signature:$(Split-Path -Leaf $exe):$($result.reasons -join ',')") }
  }

  if ($Record) {
    if ($problems.Count) { throw "Refusing to approve a candidate with problems: $($problems -join '; ')" }
    if (-not $Version -or $Commit -notmatch '^[0-9a-f]{40}$') { throw '-Record needs -Version and the full 40-character -Commit' }
    $approved = [ordered]@{
      schema = 1
      version = $Version
      commit = $Commit
      signer_certificate_sha256 = $pin
      recorded_utc = [DateTime]::UtcNow.ToString('o')
      files = $files
      payload = @($payload)
    }
    $approved | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ApprovedManifest -Encoding UTF8
    Write-Host "Approved manifest written: $($files.Count) release files, $(@($payload).Count) payload files"
    exit 0
  }

  $approved = Get-Content -LiteralPath $ApprovedManifest -Raw | ConvertFrom-Json
  if ($approved.signer_certificate_sha256 -ne $pin) { $problems.Add('manifest-signer-differs-from-expected-pin') }
  foreach ($set in @(@{ name = 'release'; want = @($approved.files); have = $files },
                     @{ name = 'payload'; want = @($approved.payload); have = @($payload) })) {
    $have = @{}
    foreach ($entry in $set.have) { $have[$entry.path] = $entry.sha256 }
    $want = @{}
    foreach ($entry in $set.want) {
      $want[$entry.path] = $true
      if (-not $have.ContainsKey($entry.path)) { $problems.Add("$($set.name):missing-from-candidate:$($entry.path)") }
      elseif ($have[$entry.path] -ne $entry.sha256) { $problems.Add("$($set.name):hash-mismatch:$($entry.path)") }
    }
    foreach ($path in $have.Keys) {
      if (-not $want.ContainsKey($path)) { $problems.Add("$($set.name):unexpected-in-candidate:$path") }
    }
  }
} finally {
  if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
}

$report = [ordered]@{
  schema = 1
  candidate_matches_approved = ($problems.Count -eq 0)
  approved_version = $approved.version
  approved_commit = $approved.commit
  problems = @($problems)
  signatures = @($signatures)
}
if ($ReportPath) { $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReportPath -Encoding UTF8 }
if ($problems.Count) {
  Write-Host "Candidate REJECTED: $($problems.Count) problem(s)"
  $problems | ForEach-Object { Write-Host "  $_" }
  exit 1
}
Write-Host "Candidate matches the approved manifest for $($approved.version) ($($approved.commit))"
exit 0
