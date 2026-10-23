# DeepSeek Chat Unofficial API & Network Inspector

Полнофункциональный клиент и инструмент анализа для [chat.deepseek.com](https://chat.deepseek.com/).

## Возможности

1. **Авторизация через Selenium**:
   - Автоматический запуск браузера Chrome с защитой от детекта автоматизации (`--disable-blink-features=AutomationControlled`, stealth CDP скрипты).
   - Сохранение профиля браузера в `./data/chrome_profile/` (не нужно повторно логиниться при каждом запуске).
   - Ожидание авторизации пользователя (SMS, Email, Google и др.) и автоматический захват:
     - Всех куки (`driver.get_cookies()`)
     - Токенов авторизации из `localStorage` (`userToken`) и HTTP-заголовков (`Authorization: Bearer ...`)
     - Заголовков `x-client-*`, `x-app-*` и User-Agent.
     - Сохранение в `./data/session.json`.

2. **Полный перехват и логирование сети и файлов**:
   - Внедрение JavaScript-перехватчика (`deepseek_api/interceptor.js`) на каждую страницу через Chrome DevTools Protocol (`Page.addScriptToEvaluateOnNewDocument`).
   - Логирование всех вызовов `fetch` и `XMLHttpRequest`: URL, HTTP-методы, заголовки, тела запросов (JSON/FormData), загружаемые файлы, статусы и ответы.
   - Запись структурированных логов в `logs/requests.jsonl` и человекочитаемых в `logs/traffic.log`.

3. **API на базе `requests`**:
   - Чистые HTTP-запросы без необходимости держать браузер открытым.
   - **Создание чата**: `client.create_chat()`
   - **Отправка сообщений**: `client.send_message(...)` со стримингом ответа (SSE) и поддержкой режима рассуждений (`thinking_enabled=True`).
   - **Загрузка и прикрепление файлов**: `client.upload_file(path)`
   - **Удаление чатов**: `client.delete_chat(chat_id)`
   - **История и список диалогов**: `client.list_chats()`, `client.get_chat_history(chat_id)`
   - **Решение Proof-of-Work (PoW)**: Встроенный WASM-солвер для `DeepSeekHashV1` (заголовок `x-ds-pow-response`).

---

## Структура проекта

```
Uroboros/
├── deepseek_api/
│   ├── __init__.py           # Экспорт основных классов
│   ├── browser.py            # Управление Selenium, авторизация, перехват
│   ├── client.py             # HTTP API клиент на requests
│   ├── interceptor.js        # Внедряемый JS-хук для fetch и XHR
│   ├── logger.py             # Логирование трафика и файлов
│   └── pow.py                # WASM Proof-of-Work солвер
├── data/
│   ├── session.json          # Сохраненные куки, токены и заголовки
│   └── chrome_profile/       # Профиль браузера Chrome
├── logs/
│   ├── requests.jsonl        # Структурированные JSONL логи запросов
│   ├── traffic.log           # Форматированный текстовый лог
│   └── files/                # Загруженные файлы
├── cli.py                    # Интерактивное консольное меню
├── example_usage.py          # Пример вызова функций из Python
└── requirements.txt          # Зависимости
```

---

## Быстрый старт

### 1. Запуск интерактивного меню
```bash
python cli.py
```

### 2. Шаги работы:
1. Выберите **[1]**, чтобы открыть Chrome и залогиниться на `https://chat.deepseek.com/`. Как только вы войдете, куки и токен сохранятся в `data/session.json`.
2. После сохранения куки браузер закроется, и вы сможете использовать все функции через быстрые HTTP-реквесты:
   - **[3]** Создать новый чат
   - **[4]** Отправить сообщение (с потоковым выводом текста и мыслей)
   - **[5]** Прикрепить файл и задать вопрос по нему
   - **[6]** Посмотреть список чатов и удалить любой чат
   - **[7]** Просмотреть логи отправленных и полученных реквестов

---

## Пример использования в коде

```python
from deepseek_api import DeepSeekClient

# Инициализация (сессия загружается автоматически из data/session.json)
client = DeepSeekClient()

# 1. Создаем чат
chat_id = client.create_chat()
print(f"Chat ID: {chat_id}")

# 2. Отправляем сообщение со стримингом
for chunk in client.send_message(chat_id, "Привет! Расскажи шутку о программистах.", stream=True):
    print(chunk["content"], end="", flush=True)

# 3. Прикрепляем файл
file_info = client.upload_file("my_document.pdf")
file_id = file_info["id"]

# Задаем вопрос с учетом прикрепленного файла
for chunk in client.send_message(chat_id, "Сделай краткое саммари файла", ref_file_ids=[file_id], stream=True):
    print(chunk["content"], end="", flush=True)

# 4. Удаляем чат
client.delete_chat(chat_id)
```
