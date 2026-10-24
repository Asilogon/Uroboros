# ============================================================
#  Uroboros - скрипт управления веткой DeepSeek
#  Создаёт (или переключает на) ветку feature/deepseek.
#  Работает двумя способами:
#    1) Через git.exe, если Git установлен в системе.
#    2) Напрямую через файлы .git, если Git не установлен.
# ============================================================

param(
    [string]$BranchName = 'feature/deepseek',
    [switch]$SwitchToBranch = $true
)

$ErrorActionPreference = 'Stop'
$repoPath = 'D:\VibeCoding\Uroboros'

if (-not (Test-Path (Join-Path $repoPath '.git'))) {
    Write-Host "[ERROR] Не найден git-репозиторий в $repoPath" -ForegroundColor Red
    exit 1
}

Set-Location $repoPath
Write-Host "Репозиторий: $repoPath" -ForegroundColor Cyan
Write-Host "Целевая ветка: $BranchName" -ForegroundColor Cyan

# ---- Попытка найти git.exe ----
$gitExe = $null
$candidates = @(
    'C:\Program Files\Git\cmd\git.exe',
    'C:\Program Files (x86)\Git\cmd\git.exe',
    'C:\Program Files\Git\bin\git.exe',
    'C:\Program Files (x86)\Git\bin\git.exe'
)
foreach ($c in $candidates) {
    if (Test-Path $c) { $gitExe = $c; break }
}
if (-not $gitExe) {
    $cmd = Get-Command git -ErrorAction SilentlyContinue
    if ($cmd) { $gitExe = $cmd.Source }
}

if ($gitExe) {
    # ---------- Способ 1: через настоящий git ----------
    Write-Host "\n[INFO] Найден git: $gitExe" -ForegroundColor Green

    $existing = & $gitExe branch --list $BranchName
    if ([string]::IsNullOrWhiteSpace($existing)) {
        Write-Host "[INFO] Создаю ветку $BranchName ..." -ForegroundColor Yellow
        & $gitExe branch $BranchName
        if ($LASTEXITCODE -ne 0) { throw "git branch завершился с кодом $LASTEXITCODE" }
    } else {
        Write-Host "[INFO] Ветка $BranchName уже существует." -ForegroundColor Yellow
    }

    if ($SwitchToBranch) {
        Write-Host "[INFO] Переключаюсь на $BranchName ..." -ForegroundColor Yellow
        & $gitExe checkout $BranchName
        if ($LASTEXITCODE -ne 0) { throw "git checkout завершился с кодом $LASTEXITCODE" }
    }

    Write-Host "\n[OK] Готово." -ForegroundColor Green
    & $gitExe branch
    & $gitExe status
    exit 0
}

# ---------- Способ 2: напрямую через файлы .git ----------
Write-Host "\n[WARN] git.exe не найден — работаю напрямую через .git" -ForegroundColor Yellow

$headFile = Join-Path $repoPath '.git\HEAD'
$headsDir = Join-Path $repoPath '.git\refs\heads'
$targetRef = "refs/heads/$BranchName"
$targetFile = Join-Path $headsDir ($BranchName -replace '/', '\')

# 1. Определяем SHA текущего HEAD
$headContent = (Get-Content $headFile -Raw).Trim()
if ($headContent -match '^ref:\s*(.+)$') {
    $currentRef = $matches[1].Trim()
    $currentRefFile = Join-Path $repoPath ('.git\' + ($currentRef -replace '/', '\'))
    if (-not (Test-Path $currentRefFile)) {
        Write-Host "[ERROR] Не найден текущий ref: $currentRefFile" -ForegroundColor Red
        exit 1
    }
    $currentSha = (Get-Content $currentRefFile -Raw).Trim()
} elseif ($headContent -match '^[0-9a-f]{40}$') {
    $currentSha = $headContent
} else {
    Write-Host "[ERROR] Не удалось распознать .git/HEAD: $headContent" -ForegroundColor Red
    exit 1
}

Write-Host "Текущий SHA: $currentSha" -ForegroundColor Cyan

# 2. Создаём файл новой ветки
$targetDir = Split-Path $targetFile -Parent
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
}

if (Test-Path $targetFile) {
    $existingSha = (Get-Content $targetFile -Raw).Trim()
    if ($existingSha -ne $currentSha) {
        Write-Host "[WARN] Ветка уже существует и указывает на другой SHA: $existingSha" -ForegroundColor Yellow
    } else {
        Write-Host "[INFO] Ветка уже существует и указывает на тот же SHA." -ForegroundColor Yellow
    }
} else {
    Set-Content -Path $targetFile -Value $currentSha -NoNewline -Encoding ascii
    Write-Host "[OK] Создан файл ветки: $targetFile" -ForegroundColor Green
}

# 3. Переключаем HEAD
if ($SwitchToBranch) {
    Set-Content -Path $headFile -Value "ref: $targetRef" -NoNewline -Encoding ascii
    Write-Host "[OK] HEAD переключён на $targetRef" -ForegroundColor Green
}

# 4. Проверка
Write-Host "\n--- Проверка ---" -ForegroundColor Cyan
Write-Host "HEAD: $(Get-Content $headFile -Raw)"
Write-Host "Ветки:"
Get-ChildItem $headsDir -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($headsDir.Length + 1).Replace('\', '/')
    Write-Host ("  {0,-30} -> {1}" -f $rel, (Get-Content $_.FullName -Raw).Trim())
}

Write-Host "\n[OK] Готово. Ветка '$BranchName' создана и активна." -ForegroundColor Green
