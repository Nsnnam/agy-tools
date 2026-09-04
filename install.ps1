# Install agy-resume (agyr) tool
Write-Host "Installing agy-resume (agyr)..." -ForegroundColor Cyan

$scriptDir = $PSScriptRoot
$binDir = Join-Path $env:LOCALAPPDATA "agy\bin"
if (!(Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
}

$targetScript = Join-Path $scriptDir "agy_resume.py"
$shimContent = @"
@echo off
python "$targetScript" %*
"@

Set-Content -Path (Join-Path $binDir "agyr.cmd") -Value $shimContent -Encoding ASCII
Set-Content -Path (Join-Path $binDir "agy-resume.cmd") -Value $shimContent -Encoding ASCII

# Configure PowerShell Profile
$profileDir = Split-Path $PROFILE -Parent
if (!(Test-Path $profileDir)) {
    New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
}

$profileFunc = @"

# Antigravity CLI Resume Tool
function agyr {
    param([string[]]`$argsList)
    python "$targetScript" @argsList
}
function agy-resume {
    param([string[]]`$argsList)
    python "$targetScript" @argsList
}
"@

if (Test-Path $PROFILE) {
    $currentProfile = Get-Content $PROFILE -Raw
    if ($currentProfile -notmatch "function agyr") {
        Add-Content -Path $PROFILE -Value $profileFunc -Encoding UTF8
    }
} else {
    Set-Content -Path $PROFILE -Value $profileFunc -Encoding UTF8
}

Write-Host "[OK] agyr & agy-resume successfully configured in PATH and PowerShell profile!" -ForegroundColor Green
Write-Host "You can now run 'agyr' from anywhere." -ForegroundColor Yellow
