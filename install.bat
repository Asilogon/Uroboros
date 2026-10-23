@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title Uroboros - Автоматический установщик среды и библиотек
cd /d "%~dp0"

echo.
echo  ===========================================================================
echo   Запуск автоматической установки компонентов Uroboros...
echo  ===========================================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_env.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [!] Произошла ошибка во время установки. Проверьте вывод выше.
    echo.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo  ---------------------------------------------------------------------------
echo  Установка успешно завершена!
echo  [1] Запустить Uroboros прямо сейчас
echo  [2] Выход
echo  ---------------------------------------------------------------------------
set /p launchChoice="Выберите действие [1/2] (по умолчанию 1): "

if "%launchChoice%"=="2" (
    exit /b 0
)

cls
call "%~dp0run_gui.bat"
