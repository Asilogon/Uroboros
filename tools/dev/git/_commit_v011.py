"""Commit 0.1.1: stream incomplete handling fix."""
from pathlib import Path
from dulwich import porcelain
from dulwich.repo import Repo

ROOT = Path(__file__).resolve().parents[3]
REPO = Repo(str(ROOT))

MESSAGE = """[0.1.1] Исправлена потеря связи со стримом DeepSeek

Подробные изменения:
- deepseek_api/client.py: обработка сетевых ошибок в SSE-стриме (ChunkedEncodingError, ConnectionError, ReadTimeout, IncompleteRead, SSLError, ProtocolError). При обрыве эмитится маркер {type: incomplete, reason: ...} вместо всплытия исключения.
- deepseek_api/client.py: таймаут для стрима изменён с 60 сек (одно число) на (30, 180) — 180 сек на чтение следующего чанка переживает паузы DeepSeek Thinking.
- deepseek_api/client.py: событие {type: complete} эмитится только при получении event: close или [DONE]; иначе — incomplete.
- deepseek_api/client.py: режим stream=False теперь возвращает поля complete (bool) и incomplete_reason (str|null).
- deepseek_gui/app.py: во всех 4 точках чтения стрима (обычный чат, lead, subagent SSE, subagent блокирующий) incomplete-чанк прерывает обработку, отдаёт SSE-событие error/connection_lost и не помечает задачу как успешно выполненную.
- deepseek_gui/app.py: run_subagent_task_internal при incomplete ставит агенту status='error', progress=0 и не возвращает ложный успех.
- deepseek_gui/app.py: убран автоматический шаблон 'Все задачи успешно выполнены!' при пустом ответе после обрыва.
- deepseek_gui/static/js/app.js: в SSE-цикле добавлен флаг hadStreamError; при error/connection_lost блок задачи остаётся в статусе 'Ошибка', а не 'Готово'; сообщение об ошибке выделено красным с явным текстом 'Соединение потеряно'.
- Логирование: обрывы стрима пишутся в logs/requests.jsonl с kind='stream_incomplete' для последующей диагностики.
- tools/dev/patchers: добавлены патчи patch_stream_incomplete.py, patch_appjs_stream_error.py, _fix_app_quote.py.
- tools/tests/test_stream_incomplete_e2e.py: сквозной тест, подтверждающий, что incomplete превращается в error-событие и ложный 'успех' не подставляется.
- tools/dev/diagnostics/check_js_balance.py, compare_appjs_to_head.py: вспомогательные проверки.
- Синхронизирован deepseek_gui/version.py с VERSION (было расхождение 0.0.3 → 0.1.1).
- VERSION повышен до 0.1.1."""

porcelain.add(REPO, paths=None)
commit_id = porcelain.commit(REPO, message=MESSAGE.encode("utf-8"))
print("Commit created:", commit_id.decode())
