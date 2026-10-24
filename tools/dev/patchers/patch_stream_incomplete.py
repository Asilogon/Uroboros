"""Patch deepseek_gui/app.py to handle 'incomplete' stream chunks.

When the network drops mid-stream (ChunkedEncodingError, ConnectionError,
ReadTimeout, IncompleteRead, etc.), deepseek_api.client now emits
{"type": "incomplete", "reason": "..."} before ending the generator.

This patcher rewires the 4 stream consumer loops in app.py so they:
  - propagate the error to the frontend as an 'error' event
  - never mark the task as successfully completed on incomplete stream
  - never fabricate a final 'успешно' report on incomplete stream

Idempotent: safe to run repeatedly; refuses to patch already-patched files.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'deepseek_gui' / 'app.py'

src = APP.read_text(encoding='utf-8')
marker = '# === PATCHED: stream incomplete handling ==='
if marker in src:
    print('Already patched; nothing to do.')
    raise SystemExit(0)

replacements = []

# ---------------------------------------------------------------------------
# (1) api_send_message: plain chat SSE generator
# ---------------------------------------------------------------------------
old1 = (
    "            for chunk in stream:\n"
    "                yield f\"data: {json.dumps(chunk, ensure_ascii=False)}\\n\\n\"\n"
    "            yield f\"data: {json.dumps({'type': 'done'})}\\n\\n\"\n"
)
new1 = (
    "            for chunk in stream:\n"
    "                if isinstance(chunk, dict) and chunk.get('type') == 'incomplete':\n"
    "                    reason = chunk.get('reason', 'unknown')\n"
    "                    try:\n"
    "                        default_logger.log({\n"
    "                            'kind': 'stream_incomplete',\n"
    "                            'chat_session_id': chat_id,\n"
    "                            'reason': reason,\n"
    "                        })\n"
    "                    except Exception:\n"
    "                        pass\n"
    "                    err_data = {\n"
    "                        'type': 'error',\n"
    "                        'kind': 'connection_lost',\n"
    "                        'message': ('Соединение с DeepSeek потеряно, ответ неполный. '\n"
    "                                    'Нажмите «Отправить» ещё раз, чтобы продолжить.'),\n"
    "                        'reason': reason,\n"
    "                    }\n"
    "                    yield f\"data: {json.dumps(err_data, ensure_ascii=False)}\\n\\n\"\n"
    "                    yield f\"data: {json.dumps({'type': 'done', 'incomplete': True})}\\n\\n\"\n"
    "                    return\n"
    "                yield f\"data: {json.dumps(chunk, ensure_ascii=False)}\\n\\n\"\n"
    "            yield f\"data: {json.dumps({'type': 'done'})}\\n\\n\"\n"
)
replacements.append(('api_send_message', old1, new1))

# ---------------------------------------------------------------------------
# (2) run_subagent_task_internal: stream=False, dict result with 'complete' field
# ---------------------------------------------------------------------------
old2 = (
    "            res = client.send_message(chat_id, current_sub_prompt, stream=False, thinking_enabled=thinking_enabled)\n"
    "            ans_text = res.get(\"text\", \"\")\n"
    "            ans_think = res.get(\"thinking\", \"\")\n"
    "            last_ans_text = ans_text\n"
)
new2 = (
    "            res = client.send_message(chat_id, current_sub_prompt, stream=False, thinking_enabled=thinking_enabled)\n"
    "            ans_text = res.get(\"text\", \"\")\n"
    "            ans_think = res.get(\"thinking\", \"\")\n"
    "            last_ans_text = ans_text\n"
    "            if not res.get('complete', True):\n"
    "                reason = res.get('incomplete_reason') or 'unknown'\n"
    "                try:\n"
    "                    default_logger.log({\n"
    "                        'kind': 'stream_incomplete',\n"
    "                        'chat_session_id': chat_id,\n"
    "                        'agent_id': agent_id,\n"
    "                        'reason': reason,\n"
    "                    })\n"
    "                except Exception:\n"
    "                    pass\n"
    "                incomplete_text = (\n"
    "                    '⚠️ Соединение с DeepSeek потеряно во время выполнения задачи. '\n"
    "                    'Ответ неполный. Попробуйте запустить задачу ещё раз.'\n"
    "                )\n"
    "                try:\n"
    "                    projects_manager.update_agent_task(project_id, agent_id, task_desc, status='error', progress=0)\n"
    "                    projects_manager.append_subagent_message(\n"
    "                        project_id, agent_id, role='ASSISTANT', text=incomplete_text\n"
    "                    )\n"
    "                except Exception:\n"
    "                    pass\n"
    "                return {\n"
    "                    'text': incomplete_text,\n"
    "                    'thinking': '\",\n"
    "                    'executed_commands': [],\n"
    "                    'steps': sub_steps,\n"
    "                    'incomplete': True,\n"
    "                    'incomplete_reason': reason,\n"
    "                }\n"
)
replacements.append(('run_subagent_task_internal', old2, new2))

# ---------------------------------------------------------------------------
# (3) api_subagent_message: subagent SSE generator
# ---------------------------------------------------------------------------
old3 = (
    "                for chunk in stream:\n"
    "                    if chunk[\"type\"] == \"thinking\":\n"
    "                        collected_thinking.append(chunk[\"content\"])\n"
    "                        yield f\"data: {json.dumps(chunk, ensure_ascii=False)}\\n\\n\"\n"
    "                    elif chunk[\"type\"] == \"text\":\n"
    "                        collected_text.append(chunk[\"content\"])\n"
)
new3 = (
    "                for chunk in stream:\n"
    "                    if chunk[\"type\"] == \"thinking\":\n"
    "                        collected_thinking.append(chunk[\"content\"])\n"
    "                        yield f\"data: {json.dumps(chunk, ensure_ascii=False)}\\n\\n\"\n"
    "                    elif chunk[\"type\"] == \"text\":\n"
    "                        collected_text.append(chunk[\"content\"])\n"
    "                    elif chunk.get(\"type\") == \"incomplete\":\n"
    "                        reason = chunk.get('reason', 'unknown')\n"
    "                        try:\n"
    "                            default_logger.log({\n"
    "                                'kind': 'stream_incomplete',\n"
    "                                'chat_session_id': chat_id,\n"
    "                                'agent_id': agent_id,\n"
    "                                'reason': reason,\n"
    "                            })\n"
    "                        except Exception:\n"
    "                            pass\n"
    "                        err_data = {\n"
    "                            'type': 'error',\n"
    "                            'kind': 'connection_lost',\n"
    "                            'message': ('Соединение с DeepSeek потеряно, ответ неполный. '\n"
    "                                        'Попробуйте отправить сообщение ещё раз.'),\n"
    "                            'reason': reason,\n"
    "                        }\n"
    "                        yield f\"data: {json.dumps(err_data, ensure_ascii=False)}\\n\\n\"\n"
    "                        yield f\"data: {json.dumps({'type': 'done', 'incomplete': True})}\\n\\n\"\n"
    "                        return\n"
)
replacements.append(('api_subagent_message', old3, new3))

# ---------------------------------------------------------------------------
# (4) api_project_lead_message: lead SSE generator
# ---------------------------------------------------------------------------
old4 = (
    "                for chunk in stream:\n"
    "                    if chunk[\"type\"] == \"thinking\":\n"
    "                        iter_thinking.append(chunk[\"content\"])\n"
    "                        yield f\"data: {json.dumps(chunk, ensure_ascii=False)}\\n\\n\"\n"
    "                    elif chunk[\"type\"] == \"text\":\n"
    "                        iter_text.append(chunk[\"content\"])\n"
)
new4 = (
    "                for chunk in stream:\n"
    "                    if chunk[\"type\"] == \"thinking\":\n"
    "                        iter_thinking.append(chunk[\"content\"])\n"
    "                        yield f\"data: {json.dumps(chunk, ensure_ascii=False)}\\n\\n\"\n"
    "                    elif chunk[\"type\"] == \"text\":\n"
    "                        iter_text.append(chunk[\"content\"])\n"
    "                    elif chunk.get(\"type\") == \"incomplete\":\n"
    "                        reason = chunk.get('reason', 'unknown')\n"
    "                        try:\n"
    "                            default_logger.log({\n"
    "                                'kind': 'stream_incomplete',\n"
    "                                'chat_session_id': chat_id,\n"
    "                                'project_id': project_id,\n"
    "                                'reason': reason,\n"
    "                            })\n"
    "                        except Exception:\n"
    "                            pass\n"
    "                        err_data = {\n"
    "                            'type': 'error',\n"
    "                            'kind': 'connection_lost',\n"
    "                            'message': ('Соединение с DeepSeek потеряно, ответ неполный. '\n"
    "                                        'Попробуйте отправить сообщение ещё раз.'),\n"
    "                            'reason': reason,\n"
    "                        }\n"
    "                        yield f\"data: {json.dumps(err_data, ensure_ascii=False)}\\n\\n\"\n"
    "                        yield f\"data: {json.dumps({'type': 'done', 'incomplete': True})}\\n\\n\"\n"
    "                        return\n"
)
replacements.append(('api_project_lead_message', old4, new4))

# ---------------------------------------------------------------------------
# Apply; abort on any missing anchor
# ---------------------------------------------------------------------------
for name, old, new in replacements:
    if old not in src:
        print(f'ERROR: anchor not found for {name}; aborting. File NOT modified.')
        print('--- expected snippet ---')
        print(old)
        raise SystemExit(1)

for name, old, new in replacements:
    src = src.replace(old, new, 1)
    print(f'patched: {name}')

# Add marker at the top of the file (as a comment)
src = marker + '\n' + src

APP.write_text(src, encoding='utf-8', newline='\n')
print()
print('OK: app.py patched.')
