# Builds a redistributable, single-click NimboMount setup EXE on Windows x64.
# Requires Python 3.11+ and Inno Setup 6; all runtime dependencies are bundled.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root
$stage = Join-Path $root 'build\windows-deps'
New-Item -ItemType Directory -Force -Path $stage | Out-Null

function Download-Checked([string] $Uri, [string] $Destination, [string] $SHA256) {
    if (Test-Path -LiteralPath $Destination) {
        $existing = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash
        if ($existing -ieq $SHA256) {
            Write-Host "Using verified cached download: $Destination"
            return
        }
        Remove-Item -LiteralPath $Destination -Force
    }
    $temporary = "$Destination.part"
    for ($attempt = 1; $attempt -le 4; $attempt++) {
        try {
            Write-Host "Downloading $Uri (attempt $attempt of 4)"
            Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
            # Windows PowerShell 5.1 can fail while following GitHub release redirects.
            # curl.exe uses a separate HTTP stack and handles redirects and retries.
            $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
            if ($curl) {
                & $curl.Source --fail --location --retry 3 --retry-delay 2 --connect-timeout 30 --output $temporary $Uri
                if ($LASTEXITCODE -ne 0) { throw "curl.exe exited with code $LASTEXITCODE" }
            } else {
                Invoke-WebRequest -Uri $Uri -OutFile $temporary -MaximumRedirection 10 -UseBasicParsing
            }
            $got = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash
            if ($got -ine $SHA256) { throw "SHA-256 mismatch: expected $SHA256, received $got" }
            Move-Item -LiteralPath $temporary -Destination $Destination -Force
            return
        } catch {
            Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
            if ($attempt -eq 4) { throw "Download failed after 4 attempts: $Uri`n$($_.Exception.Message)" }
            Start-Sleep -Seconds ([Math]::Min(2 * $attempt, 8))
        }
    }
}

# Official rclone checksum list is fetched from the matching versioned release.
$rcloneVersion = '1.75.2'
$rcloneFile = "rclone-v$rcloneVersion-windows-amd64.zip"
$hashList = Join-Path $stage 'SHA256SUMS'
Invoke-WebRequest -Uri "https://downloads.rclone.org/v$rcloneVersion/SHA256SUMS" -OutFile $hashList
$hashLine = @(Get-Content $hashList | Where-Object { $_ -match [regex]::Escape($rcloneFile) + '$' })
if ($hashLine.Count -ne 1 -or $hashLine[0] -notmatch '^([0-9a-fA-F]{64})\s+\*?') { throw 'Could not locate official rclone checksum.' }
$rcloneHash = $Matches[1]
$rcloneZip = Join-Path $stage $rcloneFile
Download-Checked "https://downloads.rclone.org/v$rcloneVersion/$rcloneFile" $rcloneZip $rcloneHash
$rcloneUnpack = Join-Path $stage 'rclone-unpacked'
Expand-Archive -LiteralPath $rcloneZip -DestinationPath $rcloneUnpack -Force
$rcloneExe = Get-ChildItem $rcloneUnpack -Recurse -Filter rclone.exe | Select-Object -First 1
if (-not $rcloneExe) { throw 'Downloaded rclone archive does not contain rclone.exe.' }

# WinFsp 2026 Beta5 fixes CVE-2026-3006 and CVE-2026-7162.
$winfspFile = 'winfsp-2.2.26286.msi'
$winfspMsi = Join-Path $stage $winfspFile
Download-Checked "https://github.com/winfsp/winfsp/releases/download/v2.2B5/$winfspFile" $winfspMsi '293FFB9BCC0B625C85079FE85FA77F8FE98170ABA51A02AC9C83D58F6C3B0E2F'
$signature = Get-AuthenticodeSignature -FilePath $winfspMsi
if ($signature.Status -ne 'Valid') { throw "WinFsp MSI signature not valid: $($signature.Status)" }

py -m pip install --disable-pip-version-check -r requirements.txt 'pyinstaller>=6,<7'
if ($LASTEXITCODE -ne 0) { throw 'pip failed' }
py -m PyInstaller --clean --noconfirm --windowed --name NimboMount --collect-all keyring --icon "nimbomount/assets/NimboMount.ico" --add-data "nimbomount/assets;nimbomount/assets" launcher.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
Copy-Item $rcloneExe.FullName -Destination (Join-Path $root 'dist\NimboMount\rclone.exe') -Force

$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    $known = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe")
    $path = $known | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $path) { throw 'Inno Setup 6 ISCC.exe not found. Install Inno Setup 6 first.' }
    $compiler = $path
} else { $compiler = $iscc.Source }
& $compiler 'packaging\windows\NimboMount.iss'
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed' }
Write-Host 'Installer is ready in dist\installers\'
