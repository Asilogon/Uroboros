@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title Uroboros Studio
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [!] Виртуальное окружение .venv не найдено.
    echo [*] Запуск автоматической установки компонентов...
    echo.
    call "%~dp0install.bat"
    exit /b 0
)

echo [*] Запуск Uroboros Studio...
".venv\Scripts\python.exe" gui.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Приложение завершилось с кодом ошибки %ERRORLEVEL%.
    pause
)
