# Read-only evidence for docs/windows-validation-matrix.md. Run it only on an
# authorized Windows 10/11 test machine. It changes nothing: no install, no
# registry write, no network access, and no reading of user files or secrets.
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)] [ValidateSet('before', 'after')] [string]$Phase,
  [Parameter(Mandatory = $true)] [string]$OutputPath,
  [string]$ExpectedCertificateSha256,
  [switch]$AuthorizedTestMachine
)

$ErrorActionPreference = 'Stop'
if (-not $AuthorizedTestMachine) {
  throw 'Pass -AuthorizedTestMachine to confirm this is an approved Windows 10/11 test machine.'
}

function Get-FileVersionOrNull([string]$path) {
  if ($path -and (Test-Path -LiteralPath $path -PathType Leaf)) { return (Get-Item -LiteralPath $path).VersionInfo.ProductVersion }
  return $null
}

function Get-AppPath([string]$exe) {
  foreach ($hive in 'HKCU:', 'HKLM:') {
    $key = "$hive\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\$exe"
    if (Test-Path -LiteralPath $key) { return (Get-ItemProperty -LiteralPath $key).'(default)' }
  }
  return $null
}

function Get-ValueOrNull([string]$key, [string]$name) {
  try { return (Get-ItemProperty -LiteralPath $key -Name $name -ErrorAction Stop).$name } catch { return $null }
}

$os = Get-CimInstance Win32_OperatingSystem
$cv = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$webview = $null
foreach ($key in @('HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
                   'HKCU:\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}')) {
  if (-not $webview) { $webview = Get-ValueOrNull $key 'pv' }
}

$install = Join-Path $env:LOCALAPPDATA 'Programs\Rapido'
$binaries = foreach ($name in 'Rapido.exe', 'RapidoNativeHost.exe', 'unins000.exe') {
  $path = Join-Path $install $name
  if (Test-Path -LiteralPath $path -PathType Leaf) {
    $sig = Get-AuthenticodeSignature -LiteralPath $path
    $pin = $null
    if ($sig.SignerCertificate) {
      $sha = [System.Security.Cryptography.SHA256]::Create()
      try { $pin = ([BitConverter]::ToString($sha.ComputeHash($sig.SignerCertificate.RawData))).Replace('-', '').ToLowerInvariant() } finally { $sha.Dispose() }
    }
    [pscustomobject]@{
      name = $name
      sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
      version = Get-FileVersionOrNull $path
      signature_status = $sig.Status.ToString()
      signer_subject = if ($sig.SignerCertificate) { $sig.SignerCertificate.Subject } else { $null }
      signer_certificate_sha256 = $pin
      signer_matches_expected = if ($ExpectedCertificateSha256) { $pin -eq $ExpectedCertificateSha256.ToLowerInvariant() } else { $null }
      timestamped = [bool]$sig.TimeStamperCertificate
    }
  }
}

$registrations = foreach ($browser in @(
    @{ name = 'Chrome'; key = 'HKCU:\Software\Google\Chrome\NativeMessagingHosts' },
    @{ name = 'Edge'; key = 'HKCU:\Software\Microsoft\Edge\NativeMessagingHosts' },
    @{ name = 'Firefox'; key = 'HKCU:\Software\Mozilla\NativeMessagingHosts' })) {
  if (Test-Path -LiteralPath $browser.key) {
    Get-ChildItem -LiteralPath $browser.key | Where-Object { $_.PSChildName -match 'rapido' } | ForEach-Object {
      $manifest = $_.GetValue('')
      [pscustomobject]@{
        browser = $browser.name
        host = $_.PSChildName
        manifest = $manifest
        manifest_exists = [bool]($manifest -and (Test-Path -LiteralPath $manifest -PathType Leaf))
        manifest_sha256 = if ($manifest -and (Test-Path -LiteralPath $manifest -PathType Leaf)) { (Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
      }
    }
  }
}

$report = [ordered]@{
  schema = 1
  phase = $Phase
  collected_utc = [DateTime]::UtcNow.ToString('o')
  computer_is_test_machine_confirmed = $true
  os = [ordered]@{
    caption = $os.Caption
    version = $os.Version
    build = $os.BuildNumber
    ubr = Get-ValueOrNull $cv 'UBR'
    display_version = Get-ValueOrNull $cv 'DisplayVersion'
  }
  browsers = [ordered]@{
    chrome = Get-FileVersionOrNull (Get-AppPath 'chrome.exe')
    edge = Get-FileVersionOrNull (Get-AppPath 'msedge.exe')
    firefox = Get-FileVersionOrNull (Get-AppPath 'firefox.exe')
  }
  webview2_runtime = $webview
  smartscreen = [ordered]@{
    explorer_setting = Get-ValueOrNull 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer' 'SmartScreenEnabled'
    policy_enable = Get-ValueOrNull 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\System' 'EnableSmartScreen'
  }
  rapido_installed = Test-Path -LiteralPath (Join-Path $install 'Rapido.exe')
  rapido_binaries = @($binaries)
  native_host_registrations = @($registrations)
  user_data_folder_present = Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.rapido')
  rapido_processes = @(Get-Process -Name 'Rapido', 'RapidoNativeHost' -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
}

$folder = Split-Path -Parent $OutputPath
if ($folder) { New-Item -ItemType Directory -Path $folder -Force | Out-Null }
$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Host "Evidence ($Phase) written to $OutputPath"
