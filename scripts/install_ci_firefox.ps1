# Disposable GitHub-hosted Windows fixture only. Never install on the user's PC.
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:RUNNER_OS -ne 'Windows') {
    throw 'Firefox fixture installation requires GitHub-hosted Windows'
}
$fixture = Get-Content -LiteralPath (Join-Path $PSScriptRoot '../packaging/firefox-ci-fixture.json') -Raw | ConvertFrom-Json
if ($fixture.version -ne '157.0.1' -or $fixture.url -ne 'https://archive.mozilla.org/pub/firefox/releases/157.0.1/win64/en-US/Firefox%20Setup%20157.0.1.exe' -or
    $fixture.sha512 -notmatch '^[0-9a-f]{128}$') { throw 'Unexpected Firefox fixture policy' }
$installer = Join-Path $env:RUNNER_TEMP ('rapido-firefox-fixture-' + [guid]::NewGuid().ToString('N') + '.exe')
$target = Join-Path $env:ProgramFiles 'Mozilla Firefox'
try {
    Invoke-WebRequest -Uri $fixture.url -OutFile $installer -TimeoutSec 90
    if ((Get-FileHash -LiteralPath $installer -Algorithm SHA512).Hash.ToLowerInvariant() -ne $fixture.sha512) {
        throw 'Firefox installer checksum does not match reviewed Mozilla SHA512SUMS'
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $installer
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(^|,\s*)CN=Mozilla Corporation(,|$)') {
        throw 'Firefox installer signature is not valid for Mozilla Corporation'
    }
    $arguments = @('/S',('/InstallDirectoryPath="' + $target + '"'),'/DesktopShortcut=false','/TaskbarShortcut=false','/StartMenuShortcut=false','/MaintenanceService=false','/RegisterDefaultAgent=false')
    $process = Start-Process -FilePath $installer -ArgumentList $arguments -PassThru -Wait
    if ($process.ExitCode -ne 0) { throw "Firefox fixture installer failed: $($process.ExitCode)" }
    $binary = Join-Path $target 'firefox.exe'
    if ((Get-Item -LiteralPath $binary).VersionInfo.ProductVersion -ne $fixture.version) {
        throw 'Installed Firefox fixture version does not match policy'
    }
    Write-Host "Mozilla Firefox fixture verified and installed: $($fixture.version)"
} finally {
    if (Test-Path -LiteralPath $installer) { Remove-Item -LiteralPath $installer }
}
