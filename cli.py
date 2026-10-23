import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deepseek_api import (
    DeepSeekBrowser,
    DeepSeekClient,
    DeepSeekAPIError,
    default_logger,
)


def print_banner():
    print("""
======================================================================
       DEEPSEEK REVERSE API & NETWORK INSPECTOR (UROBOROS)
======================================================================
  [1] Запустить Selenium: Открыть сайт, залогиниться и сохранить куки
  [2] Мониторинг трафика сайта в реальном времени (смотреть реквесты)
  [3] Тест API (через requests): Создать новый чат
  [4] Тест API (через requests): Отправить сообщение в чат (со стримингом)
  [5] Тест API (через requests): Прикрепить файл и задать вопрос
  [6] Тест API (через requests): Список чатов и удаление чата
  [7] Просмотр последних логов запросов (JSONL / traffic.log)
  [0] Выход
======================================================================
""")


def action_login():
    print("\n--- Запуск браузера для работы / авторизации ---")
    browser = DeepSeekBrowser(headless=False)
    try:
        browser.open_deepseek()
        browser.start_traffic_monitor(print_traffic=True)
        browser.wait_until_closed_by_user()
        print("\n[OK] Сессия успешно сохранена в data/session.json!")
    finally:
        browser.close()


def action_monitor():
    print("\n--- Запуск мониторинга сетевого трафика ---")
    print("Браузер откроется в интерактивном режиме. Все запросы, заголовки,")
    print("файлы и ответы будут выводиться в консоль и сохраняться в logs/.")
    print("Для завершения закройте браузер или нажмите Ctrl+C в консоли.")
    browser = DeepSeekBrowser(headless=False)
    try:
        browser.open_deepseek()
        browser.start_traffic_monitor(print_traffic=True)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nОстановка мониторинга...")
    finally:
        browser.close()


def action_create_chat():
    print("\n--- Создание нового чата через requests ---")
    client = DeepSeekClient()
    try:
        chat_id = client.create_chat()
        print(f"[OK] Чат успешно создан! ID сессии: {chat_id}")
        return chat_id
    except DeepSeekAPIError as e:
        print(f"[Ошибка API]: {e}")
        print("Убедитесь, что вы предварительно вошли через пункт [1].")
        return None


def action_send_message():
    print("\n--- Отправка сообщения в чат через requests ---")
    client = DeepSeekClient()

    chat_id = input("Введите ID чата (или нажмите ENTER для создания нового): ").strip()
    if not chat_id:
        try:
            chat_id = client.create_chat()
            print(f"[OK] Создан новый чат: {chat_id}")
        except Exception as e:
            print(f"[Ошибка создания чата]: {e}")
            return

    prompt = input("\nВведите ваше сообщение: ").strip()
    if not prompt:
        prompt = "Привет! Расскажи коротко о себе и своих возможностях."
        print(f"Используем сообщение по умолчанию: '{prompt}'")

    enable_thinking = input("Включить режим рассуждений (DeepThink / R1)? [y/N]: ").strip().lower() == "y"

    print("\n--- Ответ DeepSeek (стриминг) ---")
    try:
        stream = client.send_message(
            chat_session_id=chat_id,
            prompt=prompt,
            stream=True,
            thinking_enabled=enable_thinking,
        )

        in_thinking = False
        for chunk in stream:
            chunk_type = chunk.get("type")
            content = chunk.get("content", "")

            if chunk_type == "thinking":
                if not in_thinking:
                    print("\n[Размышления модели]:\n", end="", flush=True)
                    in_thinking = True
                print(content, end="", flush=True)
            else:
                if in_thinking:
                    print("\n\n[Ответ]:\n", end="", flush=True)
                    in_thinking = False
                print(content, end="", flush=True)
        print("\n\n[Конец ответа]\n")

    except DeepSeekAPIError as e:
        print(f"\n[Ошибка отправки сообщения]: {e}")


def action_upload_file():
    print("\n--- Прикрепление файла и отправка в чат через requests ---")
    client = DeepSeekClient()

    file_path = input("Введите путь к файлу для загрузки (например, test.txt): ").strip()
    if not file_path:
        # Create a sample test file
        test_file = Path("sample_upload.txt")
        test_file.write_text("Это тестовый текстовый документ для DeepSeek API.\nВ нем содержится секретный код: DS-778899.", encoding="utf-8")
        file_path = str(test_file)
        print(f"Создан демонстрационный файл: {file_path}")

    try:
        file_info = client.upload_file(file_path)
        file_id = file_info.get("id")
        print(f"[OK] Файл загружен! ID файла: {file_id}")

        ask_chat = input("Задать вопрос по этому файлу в чате? [Y/n]: ").strip().lower()
        if ask_chat != "n":
            chat_id = client.create_chat()
            print(f"[OK] Создан чат: {chat_id}")
            prompt = input("Ваш вопрос по файлу (ENTER = 'О чем говорится в файле?'): ").strip()
            if not prompt:
                prompt = "О чем говорится в прикрепленном файле? Какой секретный код там указан?"

            print("\n--- Ответ модели по файлу ---")
            for chunk in client.send_message(chat_id, prompt, stream=True, ref_file_ids=[file_id]):
                print(chunk.get("content", ""), end="", flush=True)
            print("\n")

    except Exception as e:
        print(f"[Ошибка работы с файлом]: {e}")


def action_manage_chats():
    print("\n--- Список и удаление чатов через requests ---")
    client = DeepSeekClient()
    try:
        chats = client.list_chats(page=1, page_size=15)
        if not chats:
            print("Чаты не найдены.")
            return

        print(f"Найдено чатов: {len(chats)}")
        for idx, c in enumerate(chats, 1):
            title = c.get("title") or "Без названия"
            cid = c.get("id")
            updated = c.get("updated_at")
            print(f"[{idx}] {title} (ID: {cid}) [{updated}]")

        choice = input("\nВведите ID или номер чата для удаления (или ENTER для возврата): ").strip()
        if not choice:
            return

        target_id = choice
        if choice.isdigit() and 1 <= int(choice) <= len(chats):
            target_id = chats[int(choice) - 1]["id"]

        confirm = input(f"Точно удалить чат {target_id}? [y/N]: ").strip().lower()
        if confirm == "y":
            success = client.delete_chat(target_id)
            if success:
                print(f"[OK] Чат {target_id} успешно удален!")
            else:
                print(f"[Ошибка] Не удалось удалить чат.")

    except Exception as e:
        print(f"[Ошибка]: {e}")


def action_view_logs():
    print("\n--- Просмотр последних запросов к API ---")
    entries = default_logger.get_recent_entries(limit=10, api_only=True)
    if not entries:
        print("Логов пока нет. Запустите браузер [1] или отправьте запрос [3-5].")
        return

    for entry in reversed(entries):
        method = entry.get("method", "")
        url = entry.get("url", "")
        status = entry.get("status", "")
        ts = entry.get("timestamp", "")
        print(f"[{ts}] {method} {url} -> Status: {status}")
    print(f"\nПолные логи: {default_logger.traffic_log}")
    print(f"JSONL логи: {default_logger.jsonl_log}")


def main():
    while True:
        print_banner()
        choice = input("Выберите действие [0-7]: ").strip()
        if choice == "1":
            action_login()
        elif choice == "2":
            action_monitor()
        elif choice == "3":
            action_create_chat()
        elif choice == "4":
            action_send_message()
        elif choice == "5":
            action_upload_file()
        elif choice == "6":
            action_manage_chats()
        elif choice == "7":
            action_view_logs()
        elif choice == "0":
            print("Выход из программы.")
            break
        else:
            print("Неверный пункт меню, попробуйте снова.")


if __name__ == "__main__":
    main()
