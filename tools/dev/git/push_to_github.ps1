# Push local commits to GitHub.
# Prerequisites: Git in PATH (or MinGit under tools/_bin/minigit/git) and a valid GitHub credential (Personal Access Token or Git Credential Manager).

param(
    [string]$Remote = 'origin',
    [string]$Branch = 'main',
    [switch]$SetUpstream
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))

# Locate git
$candidates = @(
    (Join-Path $root 'tools\_bin\minigit\git\cmd'),
    (Join-Path $root 'tools\_bin\minigit\git\mingw64\bin'),
    'C:\Program Files\Git\cmd',
    'C:\Program Files\Git\bin',
    'C:\Program Files (x86)\Git\cmd'
)
$gitDir = $null
foreach ($c in $candidates) { if (Test-Path (Join-Path $c 'git.exe')) { $gitDir = $c; break } }
if (-not $gitDir) {
    Write-Host 'ERROR: git.exe not found.' -ForegroundColor Red
    exit 1
}
$env:PATH = "$gitDir;$env:PATH"

Write-Host "Repo root: $root" -ForegroundColor Cyan
Write-Host "Remote: $Remote, Branch: $Branch" -ForegroundColor DarkGray

# Show state
& git -C $root status -sb
& git -C $root log --oneline "$Remote/$Branch..$Branch" 2>$null

$argsList = @('-C', $root, 'push')
if ($SetUpstream) { $argsList += '-u' }
$argsList += $Remote
$argsList += $Branch

Write-Host ''
Write-Host ('Running: git ' + ($argsList -join ' ')) -ForegroundColor DarkGray
& git @argsList
$rc = $LASTEXITCODE

if ($rc -ne 0) {
    Write-Host ''
    Write-Host 'Push failed. Likely causes:' -ForegroundColor Yellow
    Write-Host '  1. No GitHub credentials set. Create a Personal Access Token at https://github.com/settings/tokens (scope: repo).' -ForegroundColor Yellow
    Write-Host '  2. When prompted for username use your GitHub username; for password use the PAT.' -ForegroundColor Yellow
    Write-Host '  3. Alternatively install Git Credential Manager (bundled with Git for Windows).' -ForegroundColor Yellow
    exit $rc
}

Write-Host ''
Write-Host 'Push OK.' -ForegroundColor Green
