# Disposable CI fixtures only; never execute on the user's workstation.
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:RUNNER_OS -ne 'Windows') {
    throw 'Signing fixtures require a disposable GitHub-hosted Windows runner'
}
$folder = Join-Path $env:RUNNER_TEMP ('rapido-signature-' + [guid]::NewGuid().ToString('N'))
$previousFixtures = $env:RAPIDO_SIGNATURE_FIXTURES
$certs = @()
$testExit = 1
$stores = @(@('Root', 'LocalMachine'), @('TrustedPublisher', 'CurrentUser'))
try {
    New-Item -ItemType Directory -Path $folder | Out-Null
    Write-Host 'Creating harmless unsigned PE fixture'
    # A harmless generated PE; none of these executables is ever launched.
    Add-Type -TypeDefinition 'public class RapidoSignatureFixture { public static void Main() {} }' -OutputAssembly (Join-Path $folder 'unsigned.exe') -OutputType ConsoleApplication
    foreach ($name in @('signed.exe', 'other-signer.exe')) {
        Write-Host ('Creating isolated signer for ' + $name)
        $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject ('CN=Rapido isolated CI ' + [guid]::NewGuid()) -CertStoreLocation 'Cert:\CurrentUser\My' -KeyAlgorithm RSA -KeyLength 2048 -HashAlgorithm SHA256 -NotAfter (Get-Date).AddDays(2)
        $certs += $cert
        foreach ($location in $stores) {
            # Machine root on this disposable VM avoids interactive per-user
            # root-store consent. Never change the user's workstation stores.
            Write-Host ('Adding test certificate to ' + $location[1] + '/' + $location[0])
            $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($location[0], $location[1])
            try { $store.Open('ReadWrite'); $store.Add($cert) } finally { $store.Close() }
        }
        $path = Join-Path $folder $name
        Copy-Item -LiteralPath (Join-Path $folder 'unsigned.exe') -Destination $path
        Write-Host ('Signing harmless fixture ' + $name)
        $signed = Set-AuthenticodeSignature -FilePath $path -Certificate $cert -HashAlgorithm SHA256
        if ($signed.Status -ne 'Valid') { throw ('Fixture signing failed: ' + $signed.Status) }
        if ($name -eq 'signed.exe') {
            $sha = [System.Security.Cryptography.SHA256]::Create()
            try { $pin = ([BitConverter]::ToString($sha.ComputeHash($cert.RawData))).Replace('-', '').ToLowerInvariant() } finally { $sha.Dispose() }
            @{ pin = $pin } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $folder 'policy.json') -Encoding UTF8
        }
    }
    $tampered = Join-Path $folder 'tampered.exe'
    Copy-Item -LiteralPath (Join-Path $folder 'signed.exe') -Destination $tampered
    $bytes = [IO.File]::ReadAllBytes($tampered)
    # Modify the DOS stub, which is included in the Authenticode digest.
    $bytes[64] = $bytes[64] -bxor 1
    [IO.File]::WriteAllBytes($tampered, $bytes)
    $env:RAPIDO_SIGNATURE_FIXTURES = $folder
    Write-Host 'Running real Windows signature and held-file tests'
    python -m pytest -q -rs tests/test_windows_signature.py
    $testExit = $LASTEXITCODE
} finally {
    $env:RAPIDO_SIGNATURE_FIXTURES = $previousFixtures
    foreach ($cert in $certs) {
        foreach ($location in $stores) {
            $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($location[0], $location[1])
            try { $store.Open('ReadWrite'); $store.Remove($cert) } finally { $store.Close() }
        }
        Remove-Item -LiteralPath ('Cert:\CurrentUser\My\' + $cert.Thumbprint) -DeleteKey
    }
    if (Test-Path -LiteralPath $folder) { Remove-Item -LiteralPath $folder -Recurse -Force }
    Write-Host 'Isolated fixture certificates, private keys and files removed'
}
exit $testExit
