# Git + GitHub для Uroboros

## Что уже настроено

- **Remote `origin`:** `https://github.com/Asilogon/Uroboros.git`
- **Ветка по умолчанию:** `main`, отслеживает `origin/main`
- **Пользователь:** `Uroboros Bot <uroboros-bot@local>` (можете переопределить)
- **MinGit (портативный git):** `tools/_bin/minigit/git/cmd/git.exe` (не коммитится в репозиторий, см. `.gitignore`)
- **HEAD:** `ref: refs/heads/main` (больше не detached)

## Первый запуск

### 1. Настройте PATH для git

В новом терминале PowerShell:

```powershell
cd D:\VibeCoding\Uroboros
powershell -ExecutionPolicy Bypass -File tools\dev\git\setup_git_env.ps1
```

Этот скрипт:
- Находит `git.exe` (MinGit или системный Git)
- Добавляет его в `$env:PATH` для текущей сессии
- Проверяет/настраивает `user.name` и `user.email` в этом репозитории
- Показывает статус и ветки

### 2. Создайте Personal Access Token (PAT) на GitHub

1. Откройте https://github.com/settings/tokens
2. **Generate new token** → **Classic**
3. Дайте имя (например, `Uroboros-PC`), выберите срок действия
4. Поставьте галочку **scope `repo`** (полный доступ к приватным/публичным репозиториям)
5. Нажмите **Generate** и **скопируйте токен** — он показывается один раз!

### 3. Сделайте push

```powershell
cd D:\VibeCoding\Uroboros
powershell -ExecutionPolicy Bypass -File tools\dev\git\push_to_github.ps1 -SetUpstream
```

Когда git попросит авторизацию:
- **Username:** ваш логин на GitHub (например, `Asilogon`)
- **Password:** сам токен (не обычный пароль!)

Git сохранит креденшелы в **Windows Credential Manager** — следующий push пройдёт без ввода.

## Ежедневная работа

```powershell
# Загрузка изменений с GitHub
& git pull

# Создание коммита в формате проекта
python tools\dev\git\commit.py

# Отправка на GitHub
powershell -ExecutionPolicy Bypass -File tools\dev\git\push_to_github.ps1
```

## Почему это работало неправильно

Подробности — в разделе «Что было не так» в корневом `README.md` и в истории чата.

Кратко:

1. **Git не был установлен** — все коммиты создавались через Python-библиотеку `dulwich`, но она не умеет push без явного вызова и настроек.
2. **HEAD был detached** — коммиты шли в «никуда», ветка `main` при этом указывала на старый коммит с GitHub.
3. **origin/main отставал на 6 коммитов** — все локальные изменения были видны только на этом ПК, а не на GitHub.
4. **Credential helper = manager, но самого менеджера не было** — git при push не мог найти учётные данные и падал с «could not read Username».

После настройки: `git push` работает штатно, история синхронизирована.
