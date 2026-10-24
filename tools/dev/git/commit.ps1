# Uroboros Commit Helper (ASCII-only for max compatibility)
# Interactive commit message builder: [X.Y.Z] Short description + detailed changes

param(
    [switch]$NoAdd,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# --- Locate git ---
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) {
    $candidates = @(
        'C:\Program Files\Git\bin\git.exe',
        'C:\Program Files (x86)\Git\bin\git.exe',
        "$env:LOCALAPPDATA\Programs\Git\bin\git.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $gitCmd = @{ Source = $c }; break }
    }
}
if (-not $gitCmd) {
    Write-Host "ERROR: Git not found. Install Git for Windows: https://git-scm.com/download/win" -ForegroundColor Red
    exit 1
}
$git = $gitCmd.Source

$repoRoot = & $git rev-parse --show-toplevel 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Current directory is not a git repository." -ForegroundColor Red
    Write-Host "Run: git init" -ForegroundColor Yellow
    exit 1
}
Push-Location $repoRoot
try {
    Write-Host ""
    Write-Host "=== Uroboros Commit Helper ===" -ForegroundColor Cyan
    Write-Host "Repo: $repoRoot" -ForegroundColor DarkGray
    Write-Host ""

    $status = & $git status --short
    if (-not $status) {
        Write-Host "No changes to commit." -ForegroundColor Yellow
        exit 0
    }
    Write-Host "Changed files:" -ForegroundColor Green
    $status | ForEach-Object { Write-Host "  $_" }
    Write-Host ""

    # --- Version ---
    do {
        $ver = Read-Host "Version (SemVer, e.g. 0.2.0)"
        $ver = $ver.Trim().TrimStart('v')
        if ($ver -match '^\d+\.\d+\.\d+$') { break }
        Write-Host "  Format must be X.Y.Z (digits and dots only)." -ForegroundColor Red
    } while ($true)

    # --- Short description ---
    do {
        $subject = Read-Host "Short description (max 72 chars)"
        $subject = $subject.Trim().TrimEnd('.')
        if ($subject.Length -gt 0 -and $subject.Length -le 72) { break }
        Write-Host "  Length must be 1..72 characters." -ForegroundColor Red
    } while ($true)

    # --- Detailed changes ---
    Write-Host ""
    Write-Host "Detailed changes (one per line, empty line to finish):" -ForegroundColor Green
    $bullets = @()
    while ($true) {
        $line = Read-Host "  -"
        if ([string]::IsNullOrWhiteSpace($line)) { break }
        $bullets += $line.Trim()
    }

    # --- Build message ---
    $msg = "[$ver] $subject"
    if ($bullets.Count -gt 0) {
        $msg += "`n`nDetailed changes:`n"
        foreach ($b in $bullets) { $msg += "- $b`n" }
        $msg = $msg.TrimEnd()
    }

    Write-Host ""
    Write-Host "--- Final commit message ---" -ForegroundColor Cyan
    Write-Host $msg
    Write-Host "----------------------------" -ForegroundColor Cyan

    if ($DryRun) {
        Write-Host "[DryRun] Commit not created." -ForegroundColor Yellow
        exit 0
    }

    $confirm = Read-Host "Create commit? (y/N)"
    if ($confirm -notmatch '^[yY]') {
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit 0
    }

    if (-not $NoAdd) {
        & $git add -A
        if ($LASTEXITCODE -ne 0) { throw "git add failed" }
    }

    $tmpFile = [System.IO.Path]::GetTempFileName()
    try {
        Set-Content -Path $tmpFile -Value $msg -Encoding UTF8
        & $git commit -F $tmpFile
        if ($LASTEXITCODE -ne 0) { throw "git commit failed" }
        Write-Host ""
        Write-Host "Commit created successfully." -ForegroundColor Green
        & $git log -1 --oneline
    } finally {
        Remove-Item $tmpFile -ErrorAction SilentlyContinue
    }
} finally {
    Pop-Location
}
