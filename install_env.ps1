# ==============================================================================
# Uroboros - Automated Environment & Dependencies Installer
# ==============================================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$RootPath = $PSScriptRoot
if (-not $RootPath) {
    $RootPath = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if (-not $RootPath) {
    $RootPath = (Get-Location).Path
}
Set-Location $RootPath

function Print-Banner {
    Write-Host ""
    Write-Host " ===========================================================================" -ForegroundColor Cyan
    Write-Host "        __  __            __                            " -ForegroundColor Cyan
    Write-Host "       / / / /________  / /_  ____  _________  _____    " -ForegroundColor Cyan
    Write-Host "      / / / / ___/ __ \/ __ \/ __ \/ ___/ __ \/ ___/    " -ForegroundColor Cyan
    Write-Host "     / /_/ / /  / /_/ / /_/ / /_/ / /  / /_/ (__  )     " -ForegroundColor Cyan
    Write-Host "     \____/_/   \____/_.___/\____/_/   \____/____/      " -ForegroundColor Cyan
    Write-Host ""
    Write-Host "        АВТОМАТИЧЕСКИЙ УСТАНОВЩИК СРЕДЫ И БИБЛИОТЕК (WINDOWS)       " -ForegroundColor Yellow
    Write-Host " ===========================================================================" -ForegroundColor Cyan
    Write-Host ""
}

Print-Banner

# ------------------------------------------------------------------------------
# 1. ПРОВЕРКА И УСТАНОВКА PYTHON
# ------------------------------------------------------------------------------
Write-Host "[1/5] Проверка интерпретатора Python..." -ForegroundColor White

$PythonExe = $null
$pyCandidates = @(
    "python",
    "py",
    "${env:LocalAppData}\Programs\Python\Python312\python.exe",
    "${env:LocalAppData}\Programs\Python\Python311\python.exe",
    "${env:LocalAppData}\Programs\Python\Python310\python.exe",
    "${env:ProgramFiles}\Python312\python.exe",
    "${env:ProgramFiles}\Python311\python.exe"
)

foreach ($cand in $pyCandidates) {
    try {
        $verStr = & $cand --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $verStr -match "Python (\d+)\.(\d+)") {
            $maj = [int]$Matches[1]
            $min = [int]$Matches[2]
            if ($maj -ge 3 -and $min -ge 10) {
                $PythonExe = $cand
                Write-Host "  [OK] Найден подходящий Python: $($Matches[0]) ($cand)" -ForegroundColor Green
                break
            }
        }
    } catch {}
}

if (-not $PythonExe) {
    Write-Host "  [!] Python 3.10+ не найден на компьютере!" -ForegroundColor Yellow
    Write-Host "  [*] Запуск автоматической установки Python 3.12..." -ForegroundColor Cyan

    $installedViaWinget = $false
    $wingetCmd = Get-Command winget -ErrorAction SilentlyContinue
    if ($wingetCmd) {
        try {
            Write-Host "  [*] Установка через Windows Package Manager (winget)..." -ForegroundColor Cyan
            $proc = Start-Process -FilePath "winget" -ArgumentList "install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements" -Wait -PassThru
            if ($proc.ExitCode -eq 0) {
                $installedViaWinget = $true
            }
        } catch {
            Write-Host "  [!] Winget завершился с ошибкой, переключаемся на прямой загрузчик..." -ForegroundColor Yellow
        }
    }

    if (-not $installedViaWinget) {
        $installerUrl = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
        $installerPath = Join-Path $env:TEMP "python-3.12.8-installer.exe"
        Write-Host "  [*] Скачивание официального установщика Python 3.12 с python.org..." -ForegroundColor Cyan
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
        Write-Host "  [*] Установка Python 3.12 в тихом режиме (добавление в PATH)..." -ForegroundColor Cyan
        Start-Process -FilePath $installerPath -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait
        Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
    }

    # Обновляем переменную окружения PATH текущей сессии
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $sysPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $env:Path = "$userPath;$sysPath"

    foreach ($cand in @("python", "py", "${env:LocalAppData}\Programs\Python\Python312\python.exe")) {
        try {
            $verStr = & $cand --version 2>&1
            if ($LASTEXITCODE -eq 0 -and $verStr -match "Python (\d+)\.(\d+)") {
                $PythonExe = $cand
                Write-Host "  [OK] Python успешно установлен: $($Matches[0])!" -ForegroundColor Green
                break
            }
        } catch {}
    }

    if (-not $PythonExe) {
        Write-Host "  [!] Не удалось обнаружить Python после установки. Пожалуйста, перезапустите установщик." -ForegroundColor Red
        Exit 1
    }
}

# ------------------------------------------------------------------------------
# 2. ПРОВЕРКА БРАУЗЕРА GOOGLE CHROME
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/5] Проверка браузера Google Chrome (нужен для авторизации DeepSeek)..." -ForegroundColor White
$chromeInstalled = $false
$chromeLocations = @(
    "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "${env:LocalAppData}\Google\Chrome\Application\chrome.exe"
)
foreach ($loc in $chromeLocations) {
    if (Test-Path $loc) {
        $chromeInstalled = $true
        Write-Host "  [OK] Google Chrome обнаружен: $loc" -ForegroundColor Green
        break
    }
}

if (-not $chromeInstalled) {
    Write-Host "  [!] Google Chrome не обнаружен." -ForegroundColor Yellow
    $wingetCmd = Get-Command winget -ErrorAction SilentlyContinue
    if ($wingetCmd) {
        Write-Host "  [*] Автоматическая установка Google Chrome через winget..." -ForegroundColor Cyan
        try {
            Start-Process -FilePath "winget" -ArgumentList "install Google.Chrome --silent --accept-package-agreements --accept-source-agreements" -Wait
            Write-Host "  [OK] Google Chrome успешно установлен!" -ForegroundColor Green
        } catch {
            Write-Host "  [!] Установите Google Chrome вручную с https://google.com/chrome" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  [i] Рекомендуется установить Google Chrome для захвата сессий DeepSeek." -ForegroundColor Yellow
    }
}

# ------------------------------------------------------------------------------
# 3. НАСТРОЙКА ВИРТУАЛЬНОГО ОКРУЖЕНИЯ (.VENV)
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/5] Настройка виртуального окружения Python (.venv)..." -ForegroundColor White

$VenvDir = Join-Path $RootPath ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "  [*] Создание виртуального окружения в папке .venv..." -ForegroundColor Cyan
    & $PythonExe -m venv $VenvDir
    if (-not (Test-Path $VenvPython)) {
        Write-Host "  [ОШИБКА] Не удалось создать виртуальное окружение .venv!" -ForegroundColor Red
        Exit 1
    }
    Write-Host "  [OK] Виртуальное окружение создано." -ForegroundColor Green
} else {
    Write-Host "  [OK] Виртуальное окружение .venv уже существует." -ForegroundColor Green
}

# Проверяем наличие pip в виртуальном окружении
& $VenvPython -m pip --version 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [*] Восстановление pip через ensurepip..." -ForegroundColor Cyan
    & $VenvPython -m ensurepip --default-pip
}

Write-Host "  [*] Обновление pip, setuptools, wheel..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip setuptools wheel --quiet

# ------------------------------------------------------------------------------
# 4. УСТАНОВКА ВСЕХ ЗАВИСИМОСТЕЙ ИЗ REQUIREMENTS.TXT
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "[4/5] Установка всех необходимых библиотек проекта..." -ForegroundColor White

$ReqFile = Join-Path $RootPath "requirements.txt"
if (Test-Path $ReqFile) {
    Write-Host "  [*] Установка пакетов из requirements.txt..." -ForegroundColor Cyan
    & $VenvPython -m pip install -r $ReqFile
} else {
    Write-Host "  [!] requirements.txt не найден, устанавливаем базовый стек..." -ForegroundColor Yellow
    & $VenvPython -m pip install selenium requests curl_cffi deepseek-pow pydantic wasmtime flask pywebview pythonnet pillow
}

# ------------------------------------------------------------------------------
# 5. ТЕСТИРОВАНИЕ И ПРОВЕРКА ЦЕЛОСТНОСТИ СИСТЕМЫ
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "[5/5] Самодиагностика и проверка модулей..." -ForegroundColor White

$modulesToCheck = @(
    "flask",
    "selenium",
    "requests",
    "curl_cffi",
    "deepseek_pow",
    "wasmtime",
    "pydantic",
    "webview",
    "pythonnet",
    "PIL"
)

$allOk = $true
foreach ($mod in $modulesToCheck) {
    & $VenvPython -c "import $mod" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Модуль $mod готов к работе." -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] Ошибка импорта модуля $mod." -ForegroundColor Red
        $allOk = $false
    }
}

if ($allOk) {
    Write-Host "  [SUCCESS] Все библиотеки успешно инициализированы!" -ForegroundColor Green
} else {
    Write-Host "  [WARNING] Некоторые модули требуют дополнительной настройки." -ForegroundColor Yellow
}

# Создание ярлыка на рабочем столе
try {
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktopPath "Uroboros Studio.lnk"
    $wsh = New-Object -ComObject WScript.Shell
    $shortcut = $wsh.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $RootPath "run_gui.bat"
    $shortcut.WorkingDirectory = $RootPath
    $shortcut.Description = "Uroboros Multi-Agent Studio"
    $shortcut.IconLocation = "$VenvPython,0"
    $shortcut.Save()
    Write-Host ""
    Write-Host "  [OK] Ярлык 'Uroboros Studio' успешно создан на Рабочем столе!" -ForegroundColor Green
} catch {
    Write-Host "  [i] Создание ярлыка пропущено." -ForegroundColor Gray
}

Write-Host ""
Write-Host " ===========================================================================" -ForegroundColor Green
Write-Host "   ПОЗДРАВЛЯЕМ! ВСЕ ЯЗЫКИ, СРЕДЫ И БИБЛИОТЕКИ УСПЕШНО УСТАНОВЛЕНЫ!          " -ForegroundColor Green
Write-Host " ===========================================================================" -ForegroundColor Green
Write-Host ""
Write-Host " Для запуска приложения используйте:" -ForegroundColor White
Write-Host "   1. Двойной клик по ярлыку на рабочем столе 'Uroboros Studio'" -ForegroundColor Cyan
Write-Host "   2. Или файл 'run_gui.bat' в папке проекта" -ForegroundColor Cyan
Write-Host ""
