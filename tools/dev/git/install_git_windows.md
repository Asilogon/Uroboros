# Установка Git для Windows

На этом компьютере **Git не установлен** (нет в PATH, нет в стандартных папках).
Без Git коммиты невозможны. Установите его одним из способов.

## Способ 1. Через winget (рекомендуется)

Откройте PowerShell и выполните:

```powershell
winget install --id Git.Git -e --source winget
```

После установки **закройте и снова откройте** терминал (или перезапустите VS Code), чтобы обновился PATH.

Проверка:
```powershell
git --version
```

## Способ 2. Через установщик

1. Скачайте: https://git-scm.com/download/win
2. Установите со стандартными настройками.
3. Перезапустите терминал.

## После установки

Выполните настройку репозитория (шаблон сообщения + hook-валидатор):

```powershell
cd D:\VibeCoding\Uroboros
powershell -ExecutionPolicy Bypass -File .\scripts\setup_git.ps1
```

## Как делать коммиты

### Вариант A. Python-помощник (работает всегда)
```powershell
python scripts\commit.py
```

### Вариант B. PowerShell-помощник
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\commit.ps1
```

### Вариант C. Вручную
```powershell
git add -A
git commit -m "[0.0.1] Краткое описание" -m "Подробные изменения:`n- Пункт 1`n- Пункт 2"
```

Полная конвенция — в `COMMIT_CONVENTION.md`.
