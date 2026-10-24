# Uroboros git environment setup for PowerShell
# Finds bundled MinGit (tools/_bin/minigit/git) or system git and adds to PATH for this session.

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
Write-Host "Repo root: $root" -ForegroundColor Cyan

$candidates = @(
    (Join-Path $root 'tools\_bin\minigit\git\cmd'),
    (Join-Path $root 'tools\_bin\minigit\git\mingw64\bin'),
    'C:\Program Files\Git\cmd',
    'C:\Program Files\Git\bin',
    'C:\Program Files (x86)\Git\cmd',
    "$env:LOCALAPPDATA\Programs\Git\cmd"
)

$gitDir = $null
foreach ($c in $candidates) {
    if (Test-Path (Join-Path $c 'git.exe')) {
        $gitDir = $c
        break
    }
}

if (-not $gitDir) {
    Write-Host "ERROR: git.exe not found. Install Git for Windows or place MinGit at tools\_bin\minigit\git\cmd\git.exe" -ForegroundColor Red
    exit 1
}

Write-Host "Using git from: $gitDir" -ForegroundColor Green
$env:PATH = "$gitDir;$env:PATH"

# Configure user identity for this repo if missing
& git -C $root config user.name 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    & git -C $root config user.name 'Uroboros Bot'
    & git -C $root config user.email 'uroboros-bot@local'
    Write-Host 'Configured git user (Uroboros Bot).' -ForegroundColor Green
}

Write-Host ''
Write-Host '--- git status ---' -ForegroundColor Cyan
& git -C $root status -sb

Write-Host ''
Write-Host '--- git branch -vv ---' -ForegroundColor Cyan
& git -C $root branch -vv

Write-Host ''
Write-Host 'To push changes to GitHub, run:' -ForegroundColor Yellow
Write-Host '    powershell -ExecutionPolicy Bypass -File tools\dev\git\push_to_github.ps1' -ForegroundColor White
