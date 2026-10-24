# Tools — утилиты проекта Uroboros

Вспомогательные инструменты проекта. Основной код приложения (`cli.py`, `gui.py`, `deepseek_api/`, `deepseek_gui/`, `example_usage.py`) остаётся в корне, а всё служебное — здесь.

## Структура

```
tools/
├── dev/
│   ├── patchers/        — одноразовые патчеры (js/app.py/css)
│   ├── diagnostics/     — поиск красных зон на скриншотах, проверка чистоты
│   └── git/             — помощники коммитов и git-инструменты
├── tests/               — функциональные тесты
└── setup/               — установка окружения (venv, зависимости)
```

## dev/patchers

Скрипты точечного патчинга файлов `deepseek_gui/static/js/app.js`, `deepseek_gui/app.py`, `deepseek_gui/templates/index.html`, `deepseek_gui/static/css/style.css`. Использовались в процессе разработки. Запускать из корня проекта:

```powershell
python tools\dev\patchers\patch_web_tool.py
```

| Файл | Назначение |
|---|---|
| `patch_web_tool.py` | Добавляет инструмент `web_fetch` в app.py + app.js |
| `patch_top_agents.py` | Патч верхней панели (агенты) |
| `patch_top_agents_js.py` | JS-часть верхней панели |
| `patch_remove_top_agents.py` | Удаляет верхнюю панель агентов |
| `patch_web_js.py`, `patch_web_js2.py` | JS-патчи для web_fetch |
| `fix_js_version_init.py` | Исправляет инициализацию версии в JS |

## dev/diagnostics

| Файл | Назначение |
|---|---|
| `find_red.py` | Поиск красных областей на скриншоте (PIL) |
| `find_red_clusters.py` | Кластеризация красных зон |
| `verify_cleanup.py` | Проверка чистоты проекта (нет ли временных файлов) |

Зависимости: `pip install pillow`.

## dev/git

| Файл | Назначение |
|---|---|
| `commit.py` | Интерактивный помощник коммитов (формат `[X.Y.Z] Краткое описание`) |
| `commit.ps1` | PowerShell-версия помощника |
| `setup_git.ps1` | Настраивает `commit.template` и hook-валидатор формата |
| `install_git_windows.md` | Инструкция по установке Git |
| `amend_commit.py` | Правит последний коммит (dulwich) |
| `commit_changes.py` | Быстрый коммит всех изменений (dulwich) |
| `restore_appjs.py` | Откатывает `app.js` к HEAD (dulwich) |
| `create_branch_deepseek.ps1` | Создаёт ветку `feature/deepseek` |

Полная конвенция коммитов — в `COMMIT_CONVENTION.md` в корне.

**Быстрый коммит:**
```powershell
python tools\dev\git\commit.py
```

**Настройка git в репозитории (один раз):**
```powershell
powershell -ExecutionPolicy Bypass -File tools\dev\git\setup_git.ps1
```

## tests

| Файл | Назначение |
|---|---|
| `test_web_tool.py` | Функциональный тест `web_fetch` + `/api/version` |

```powershell
python tools\tests\test_web_tool.py
```

## setup

| Файл | Назначение |
|---|---|
| `install_env.ps1` | Создаёт `.venv`, ставит зависимости из `requirements.txt` |

```powershell
powershell -ExecutionPolicy Bypass -File tools\setup\install_env.ps1
```

## Что не перенесено в tools

Точки входа и продакшн-код остаются в корне, чтобы их не сломать:

- `cli.py`, `gui.py` — запуск приложения
- `example_usage.py` — пример использования API
- `run_cli.bat`, `run_gui.bat`, `install.bat` — быстрые лаунчеры
- `requirements.txt`, `VERSION`, `README.md`, `COMMIT_CONVENTION.md`, `.gitmessage`, `.gitignore`
- `deepseek_api/`, `deepseek_gui/`, `data/`, `logs/` — код и данные приложения
