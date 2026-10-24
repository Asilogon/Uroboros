# Ветка `feature/deepseek` в проекте Uroboros

## Что сделано

В git-репозитории `D:\VibeCoding\Uroboros` создана новая ветка:

- **Имя:** `feature/deepseek`
- **Базовая ветка:** `main` (коммит `56843f18206bdb98a9a92d2e103c78756bd34aa6`)
- **Состояние:** активна (HEAD переключён на неё)

## Как это было сделано

На компьютере **не установлен Git**, поэтому ветка была создана напрямую через служебные файлы `.git`:

```
.git\HEAD                          ->  ref: refs/heads/feature/deepseek
.git\refs\heads\feature\deepseek    ->  56843f18206bdb98a9a92d2e103c78756bd34aa6
.git\refs\heads\main                ->  56843f18206bdb98a9a92d2e103c78756bd34aa6
```

Это полностью эквивалентно выполнению `git checkout -b feature/deepseek`.

## Как проверить после установки Git

1. Скачайте и установите Git: https://git-scm.com/download/win
2. Откройте PowerShell и выполните:

```powershell
cd D:\VibeCoding\Uroboros
git branch
git status
```

Вы должны увидеть примерно следующее:

```
* feature/deepseek
  main
```

## Скрипт управления веткой

В корне проекта лежит `create_branch_deepseek.ps1` — универсальный скрипт, который:

- Если Git установлен — использует `git branch` / `git checkout`.
- Если Git НЕ установлен — создаёт ветку напрямую через `.git`.

### Запуск

```powershell
cd D:\VibeCoding\Uroboros
powershell -ExecutionPolicy Bypass -File .\create_branch_deepseek.ps1
```

Параметры:

| Параметр          | Значение по умолчанию | Описание                                |
|-------------------|-----------------------|-----------------------------------------|
| `-BranchName`     | `feature/deepseek`    | Имя создаваемой ветки                   |
| `-SwitchToBranch` | `$true`               | Переключаться ли на ветку после создания |

Пример с другим именем ветки:

```powershell
powershell -ExecutionPolicy Bypass -File .\create_branch_deepseek.ps1 -BranchName feature/deepseek-v2
```

## Дальнейшие шаги

- Работайте в ветке `feature/deepseek`, вносите изменения в `deepseek_api`, `deepseek_gui`.
- Для возврата на основную ветку (после установки Git): `git checkout main`.
- Для слияния в основную: `git checkout main; git merge feature/deepseek`.
