"""
Пример программного использования DeepSeek API через requests:
"""
import sys
from pathlib import Path

# Добавляем путь к корню проекта
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deepseek_api import DeepSeekClient


def main():
    # 1. Инициализируем клиент (автоматически загружает session.json)
    client = DeepSeekClient()

    if not client.token and not client.http.cookies:
        print("[!] Сессия не найдена. Пожалуйста, запустите `python cli.py` и выберите пункт 1 для входа.")
        return

    print(">>> 1. Получение информации о пользователе:")
    try:
        user_info = client.get_user_info()
        print(f"Пользователь: {user_info}")
    except Exception as e:
        print(f"Инфо пользователя: {e}")

    print("\n>>> 2. Создание нового чата:")
    chat_id = client.create_chat()
    print(f"Создан чат с ID: {chat_id}")

    print("\n>>> 3. Отправка сообщения со стримингом ответа:")
    prompt = "Привет! Напиши одно короткое четверостишие о программировании."
    print(f"Вопрос: {prompt}\nОтвет: ", end="", flush=True)

    for chunk in client.send_message(chat_id, prompt, stream=True):
        if chunk.get("type") == "thinking":
            # Размышления модели (если включен thinking_enabled=True)
            print(f"\n[Thinking]: {chunk['content']}", end="", flush=True)
        else:
            print(chunk["content"], end="", flush=True)
    print("\n")

    print("\n>>> 4. Загрузка файла и отправка вопроса по файлу:")
    # Создадим временный файл для примера
    sample_file = Path("demo_doc.txt")
    sample_file.write_text("Важные данные проекта: Кодовое слово 'ФЕНИКС'.", encoding="utf-8")
    
    file_info = client.upload_file(sample_file)
    print(f"Файл загружен, ID: {file_info.get('id')}")

    print("Вопрос по файлу:")
    for chunk in client.send_message(
        chat_id,
        "Какое кодовое слово указано в документе?",
        stream=True,
        ref_file_ids=[file_info.get("id")]
    ):
        print(chunk.get("content", ""), end="", flush=True)
    print("\n")

    print("\n>>> 5. Удаление чата:")
    deleted = client.delete_chat(chat_id)
    print(f"Чат {chat_id} удален: {deleted}")


if __name__ == "__main__":
    main()
