# Uroboros git setup (ASCII-only)

$ErrorActionPreference = 'Stop'

$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) {
    foreach ($c in @('C:\Program Files\Git\bin\git.exe','C:\Program Files (x86)\Git\bin\git.exe',"$env:LOCALAPPDATA\Programs\Git\bin\git.exe")) {
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
    Write-Host "Initializing git repository..." -ForegroundColor Yellow
    & $git init
    $repoRoot = (Get-Location).Path
}

Push-Location $repoRoot
try {
    & $git config commit.template ".gitmessage"
    Write-Host "OK: commit.template = .gitmessage" -ForegroundColor Green

    $hookPath = ".git\hooks\commit-msg"
    $hookScript = "#!/bin/sh`nMSG_FILE=`$1`nFIRST_LINE=`$(head -n1 `"`$MSG_FILE`")`nif ! echo `"`$FIRST_LINE`" | grep -Eq '^\\[[0-9]+\\.[0-9]+\\.[0-9]+\\] .+'; then`n  echo 'ERROR: First line must be: [X.Y.Z] Short description' >&2`n  echo 'Example: [0.2.0] Added R1 Thinking support' >&2`n  exit 1`nfi`n"
    if (-not (Test-Path $hookPath)) {
        [System.IO.File]::WriteAllText((Join-Path $repoRoot $hookPath), $hookScript, (New-Object System.Text.UTF8Encoding($false)))
        Write-Host "OK: created .git/hooks/commit-msg (format validation)" -ForegroundColor Green
    } else {
        Write-Host "INFO: .git/hooks/commit-msg already exists, skipping." -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "Done. Use scripts\commit.ps1 or scripts\commit.py for commits." -ForegroundColor Cyan
} finally {
    Pop-Location
}
