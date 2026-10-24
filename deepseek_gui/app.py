import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, Response, jsonify, render_template, request

# Add parent directory to path to import deepseek_api
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from deepseek_api import (
    DeepSeekBrowser,
    DeepSeekClient,
    DeepSeekAPIError,
    TrafficLogger,
    default_logger,
)
from .projects_manager import projects_manager
from .version import __version__

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)

DATA_DIR = ROOT_DIR / "data"
SESSION_FILE = DATA_DIR / "session.json"
CHATS_FILE = DATA_DIR / "chats.json"

browser_instance = None
browser_thread = None
active_client = None


def get_client() -> DeepSeekClient:
    global active_client
    if active_client is None:
        active_client = DeepSeekClient()
    else:
        active_client.load_session()
    return active_client


def load_local_chats() -> List[Dict[str, Any]]:
    if CHATS_FILE.exists():
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_local_chats(chats: List[Dict[str, Any]]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHATS_FILE, "w", encoding="utf-8") as f:
        json.dump(chats, f, indent=2, ensure_ascii=False)


@app.route("/api/version", methods=["GET"])
def api_version():
    """Returns the current application version."""
    return jsonify({"version": __version__})


@app.route("/")
def index():
    saved_theme = "dark"
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                saved_theme = json.load(f).get("theme", "dark")
        except Exception:
            pass
    return render_template("index.html", initial_theme=saved_theme)


@app.route("/api/status", methods=["GET"])
def api_status():
    logged_in = False
    saved_at = None
    cookies_count = 0
    token = None
    user_agent = None

    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            token = data.get("token")
            cookies = data.get("cookies", [])
            cookies_count = len(cookies)
            saved_at = data.get("saved_at")
            user_agent = data.get("user_agent")
            if token or cookies_count > 0:
                logged_in = True
        except Exception:
            pass

    return jsonify({
        "logged_in": logged_in,
        "token": token or "",
        "token_preview": (token[:12] + "...") if token else None,
        "cookies_count": cookies_count,
        "saved_at": saved_at or "Не сохранено",
        "user_agent": user_agent or "Default",
    })


@app.route("/api/settings/save", methods=["POST"])
def api_save_settings():
    data = request.json or {}
    token = data.get("token", "").strip()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session_data = {}
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                session_data = json.load(f)
        except Exception:
            session_data = {}

    session_data["token"] = token if token else None
    session_data["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)

    # Reload client session
    get_client().load_session()

    return jsonify({"success": True, "message": "Токен успешно сохранен!"})


@app.route("/api/settings/clear", methods=["POST"])
def api_clear_settings():
    if SESSION_FILE.exists():
        try:
            os.remove(SESSION_FILE)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    global active_client
    active_client = None
    return jsonify({"success": True, "message": "Сессия очищена."})


@app.route("/api/auth/reset_profile", methods=["POST"])
def api_reset_profile():
    global browser_instance
    if browser_instance:
        browser_instance.close()
        browser_instance = None
    b = DeepSeekBrowser()
    b.reset_profile()
    return jsonify({"success": True, "message": "Кэш браузера и история капчи успешно очищены."})


@app.route("/api/auth/start_selenium", methods=["POST"])
def api_start_selenium():
    global browser_instance, browser_thread

    if browser_thread and browser_thread.is_alive():
        return jsonify({"status": "running", "message": "Браузер уже запущен. Вы можете работать в нем."})

    def run_browser():
        global browser_instance
        try:
            browser_instance = DeepSeekBrowser(headless=False)
            browser_instance.open_deepseek()
            browser_instance.start_traffic_monitor(print_traffic=False)
            # Waits until user explicitly closes the Chrome browser window!
            browser_instance.wait_until_closed_by_user()
        finally:
            if browser_instance:
                browser_instance.close()
                browser_instance = None

    browser_thread = threading.Thread(target=run_browser, daemon=True)
    browser_thread.start()

    return jsonify({
        "status": "started",
        "message": "Браузер Chrome открыт. Выполните вход. Окно НЕ закроется автоматически — работайте в нем столько, сколько потребуется, и закройте крестиком, когда закончите.",
    })


@app.route("/api/chats", methods=["GET"])
def api_get_chats():
    client = get_client()
    try:
        remote_chats = client.list_chats(page=1, page_size=30)
        formatted = []
        for c in remote_chats:
            up_val = c.get("updated_at")
            up_str = "недавно"
            if isinstance(up_val, (int, float)):
                try:
                    up_str = time.strftime("%H:%M", time.localtime(up_val))
                except Exception:
                    up_str = "недавно"
            elif isinstance(up_val, str):
                up_str = up_val

            formatted.append({
                "id": c.get("id"),
                "title": c.get("title") or "Новый диалог",
                "updated_at": up_str,
            })
        if formatted:
            save_local_chats(formatted)
            return jsonify({"success": True, "chats": formatted})
    except Exception:
        pass

    # Return local clean chats list
    local_chats = load_local_chats()
    return jsonify({"success": True, "chats": local_chats})


@app.route("/api/chats/<chat_id>/history", methods=["GET"])
def api_get_chat_history(chat_id):
    client = get_client()
    try:
        messages = client.get_chat_history(chat_id)
        formatted = []
        for m in messages:
            role = m.get("role", "USER")
            thinking = []
            text = []
            for frag in m.get("fragments", []):
                frag_type = frag.get("type")
                c = frag.get("content", "")
                if frag_type == "THINK":
                    thinking.append(c)
                else:
                    text.append(c)

            msg_time = "только что"
            ins_at = m.get("inserted_at")
            if isinstance(ins_at, (int, float)):
                try:
                    msg_time = time.strftime("%H:%M", time.localtime(ins_at))
                except Exception:
                    pass

            formatted.append({
                "message_id": m.get("message_id"),
                "role": role,
                "thinking": "".join(thinking),
                "text": "".join(text),
                "time": msg_time,
            })
        return jsonify({"success": True, "messages": formatted})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "messages": []})


@app.route("/api/chats/new", methods=["POST"])
def api_new_chat():
    client = get_client()
    chat_id = None
    try:
        chat_id = client.create_chat()
    except Exception:
        chat_id = f"chat_{int(time.time())}"

    new_entry = {
        "id": chat_id,
        "title": "Новый диалог",
        "updated_at": "только что",
    }
    chats = load_local_chats()
    chats.insert(0, new_entry)
    save_local_chats(chats)

    return jsonify({"success": True, "chat_id": chat_id, "title": new_entry["title"]})


@app.route("/api/chats/<chat_id>", methods=["DELETE"])
def api_delete_chat(chat_id):
    # Try deleting remotely
    try:
        client = get_client()
        client.delete_chat(chat_id)
    except Exception:
        pass

    # Remove from local list
    chats = load_local_chats()
    chats = [c for c in chats if c.get("id") != chat_id]
    save_local_chats(chats)

    return jsonify({"success": True})


uploaded_files_registry = {}


@app.route("/api/chats/<chat_id>/message", methods=["POST"])
def api_send_message(chat_id):
    data = request.json or {}
    prompt = data.get("prompt", "")
    thinking_enabled = data.get("thinking_enabled", False)
    ref_file_ids = data.get("ref_file_ids", [])

    # Augment prompt with uploaded text files if present
    augmented_prompt = prompt
    valid_remote_file_ids = []
    for fid in ref_file_ids:
        fpath = uploaded_files_registry.get(fid)
        if fpath and Path(fpath).exists():
            try:
                file_text = Path(fpath).read_text(encoding="utf-8", errors="replace")
                augmented_prompt += f"\n\n[Прикрепленный файл: {Path(fpath).name}]\n```\n{file_text}\n```"
            except Exception:
                valid_remote_file_ids.append(fid)
        else:
            valid_remote_file_ids.append(fid)

    # Update title in local list if it's the first message
    chats = load_local_chats()
    for c in chats:
        if c.get("id") == chat_id and (c.get("title") == "Новый диалог" or not c.get("title")):
            c["title"] = (prompt[:32] + "...") if len(prompt) > 32 else prompt
            c["updated_at"] = "только что"
            break
    save_local_chats(chats)

    client = get_client()

    def generate_sse():
        try:
            stream = client.send_message(
                chat_session_id=chat_id,
                prompt=augmented_prompt,
                stream=True,
                thinking_enabled=thinking_enabled,
                ref_file_ids=valid_remote_file_ids,
            )
            for chunk in stream:
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except (GeneratorExit, Exception) as e:
            if isinstance(e, GeneratorExit):
                return
            err_data = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(err_data, ensure_ascii=False)}\n\n"

    return Response(generate_sse(), mimetype="text/event-stream")


@app.route("/api/upload", methods=["POST"])
def api_upload_file():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part in request"}), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify({"success": False, "error": "No file selected"}), 400

    temp_dir = ROOT_DIR / "logs" / "files"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f.filename
    f.save(str(temp_path))

    file_id = f"file_{int(time.time()*1000)}"
    uploaded_files_registry[file_id] = temp_path

    client = get_client()
    try:
        biz_info = client.upload_file(temp_path)
        remote_id = biz_info.get("id") or file_id
        uploaded_files_registry[remote_id] = temp_path
        return jsonify({
            "success": True,
            "id": remote_id,
            "filename": f.filename,
            "size": temp_path.stat().st_size,
        })
    except Exception as e:
        return jsonify({
            "success": True,
            "id": file_id,
            "filename": f.filename,
            "size": temp_path.stat().st_size,
            "local_only": True,
        })


@app.route("/api/logs", methods=["GET"])
def api_get_logs():
    limit = int(request.args.get("limit", 30))
    entries = default_logger.get_recent_entries(limit=limit, api_only=False)
    return jsonify({"success": True, "logs": entries})


# =====================================================================
# MULTI-AGENT & PROJECTS API ROUTES
# =====================================================================

@app.route("/api/theme", methods=["POST"])
def api_set_theme():
    data = request.json or {}
    theme = data.get("theme", "dark")

    # Persist theme in session.json
    try:
        session_data = {}
        if SESSION_FILE.exists():
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                session_data = json.load(f)
        session_data["theme"] = theme
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    try:
        import ctypes
        from ctypes import c_int, byref, sizeof
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi
        dark_val = 1 if theme == "dark" else 0
        val = c_int(dark_val)
        caption_color = c_int(0x000E0C0C if theme == "dark" else 0x00F5F4F3)
        border_color = c_int(0x00181616 if theme == "dark" else 0x00E5E7EB)

        hwnds = []
        def enum_cb(h, _):
            length = user32.GetWindowTextLengthW(h)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(h, buff, length + 1)
                if "Uroboros" in buff.value:
                    hwnds.append(h)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

        for hwnd in hwnds:
            try:
                dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(val), sizeof(val))
                dwmapi.DwmSetWindowAttribute(hwnd, 19, byref(val), sizeof(val))
                dwmapi.DwmSetWindowAttribute(hwnd, 35, byref(caption_color), sizeof(caption_color))
                dwmapi.DwmSetWindowAttribute(hwnd, 34, byref(border_color), sizeof(border_color))
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
            except Exception:
                pass
    except Exception:
        pass
    return jsonify({"success": True, "theme": theme})


@app.route("/api/projects", methods=["GET"])
def api_get_projects():
    projects = projects_manager.load_all()
    summaries = []
    for p in projects:
        summaries.append({
            "id": p["id"],
            "name": p["name"],
            "mode": p.get("mode", "multi"),
            "description": p.get("description", ""),
            "icon": p.get("icon", ""),
            "status": p.get("status", "active"),
            "created_at": p.get("created_at", ""),
            "subagents_count": len(p.get("subagents", [])),
            "lead_name": p.get("lead_agent", {}).get("name", "Руководитель"),
        })
    return jsonify({"success": True, "projects": summaries})


@app.route("/api/projects", methods=["POST"])
def api_create_project():
    data = request.json or {}
    name = data.get("name", "Новый проект")
    description = data.get("description", "")
    icon = data.get("icon", "")
    root_path = data.get("root_path", "")
    mode = data.get("mode", "multi")
    new_proj = projects_manager.create_project(name, description, icon, root_path=root_path, mode=mode)
    return jsonify({"success": True, "project": new_proj})


@app.route("/api/browse_folder", methods=["POST"])
def api_browse_folder():
    """Opens a native Windows folder browser dialog and returns selected path."""
    try:
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$f.Description = 'Выберите рабочую папку проекта'; "
            "$f.ShowNewFolderButton = $true; "
            "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.SelectedPath }"
        )
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        selected = proc.stdout.strip()
        if selected and Path(selected).exists():
            return jsonify({"success": True, "path": selected})
        return jsonify({"success": False, "cancelled": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/projects/<project_id>", methods=["GET"])
def api_get_project_detail(project_id):
    proj = projects_manager.get_project(project_id)
    if not proj:
        return jsonify({"success": False, "error": "Project not found"}), 404
    return jsonify({"success": True, "project": proj})


@app.route("/api/projects/<project_id>", methods=["DELETE"])
def api_delete_project(project_id):
    proj = projects_manager.get_project(project_id)
    if proj:
        try:
            client = get_client()
            lead_chat_id = proj.get("lead_agent", {}).get("chat_session_id")
            if lead_chat_id:
                try:
                    client.delete_chat(lead_chat_id)
                except Exception as e:
                    print(f"Error deleting lead chat session {lead_chat_id}: {e}")
            for a in proj.get("subagents", []):
                sub_chat_id = a.get("chat_session_id")
                if sub_chat_id:
                    try:
                        client.delete_chat(sub_chat_id)
                    except Exception as e:
                        print(f"Error deleting subagent chat session {sub_chat_id}: {e}")
        except Exception as e:
            print(f"Error connecting to client for project chat deletion: {e}")
    success = projects_manager.delete_project(project_id)
    return jsonify({"success": success})


@app.route("/api/projects/<project_id>/agents", methods=["POST"])
def api_add_project_agent(project_id):
    data = request.json or {}
    name = data.get("name", "Субагент")
    role = data.get("role", "Исполнитель задач")
    system_prompt = data.get("system_prompt", "")
    color = data.get("color", "#3b82f6")
    icon = data.get("icon", "")
    agent = projects_manager.add_subagent(project_id, name, role, system_prompt, color, icon)
    if not agent:
        return jsonify({"success": False, "error": "Project not found"}), 404
    return jsonify({"success": True, "agent": agent})


@app.route("/api/projects/<project_id>/agents/<agent_id>", methods=["DELETE"])
def api_delete_project_agent(project_id, agent_id):
    proj = projects_manager.get_project(project_id)
    if proj:
        for a in proj.get("subagents", []):
            if a.get("id") == agent_id:
                sub_chat_id = a.get("chat_session_id")
                if sub_chat_id:
                    try:
                        client = get_client()
                        client.delete_chat(sub_chat_id)
                    except Exception as e:
                        print(f"Error deleting subagent chat session {sub_chat_id}: {e}")
                break
    success = projects_manager.remove_subagent(project_id, agent_id)
    return jsonify({"success": success})


@app.route("/api/projects/<project_id>/agents/<agent_id>/task", methods=["POST"])
def api_update_agent_task(project_id, agent_id):
    data = request.json or {}
    task = data.get("task", "")
    status = data.get("status", "working")
    progress = int(data.get("progress", 50))
    success = projects_manager.update_agent_task(project_id, agent_id, task, status, progress)
    return jsonify({"success": success})


def write_project_file(project_root: str, file_path: str, content: str) -> Dict[str, Any]:
    """Writes or overwrites a file relative to project root with UTF-8 encoding."""
    try:
        root = Path(project_root).resolve()
        clean_rel = file_path.strip().lstrip("/\\")
        target = (root / clean_rel).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        size_bytes = len(content.encode("utf-8"))
        return {
            "success": True,
            "path": str(target),
            "rel_path": clean_rel,
            "size": size_bytes,
        }
    except Exception as e:
        return {
            "success": False,
            "path": file_path,
            "rel_path": file_path,
            "error": str(e),
        }


def read_project_file(project_root: str, file_path: str) -> Dict[str, Any]:
    """Reads a file relative to project root."""
    try:
        root = Path(project_root).resolve()
        clean_rel = file_path.strip().lstrip("/\\")
        target = (root / clean_rel).resolve()
        if not target.exists():
            return {
                "success": False,
                "path": file_path,
                "rel_path": clean_rel,
                "error": f"Файл '{clean_rel}' не найден на диске",
            }
        content = target.read_text(encoding="utf-8", errors="replace")
        return {
            "success": True,
            "path": str(target),
            "rel_path": clean_rel,
            "content": content,
            "size": len(content.encode("utf-8")),
        }
    except Exception as e:
        return {
            "success": False,
            "path": file_path,
            "rel_path": file_path,
            "error": str(e),
        }


def extract_file_writes(text: str) -> List[Dict[str, str]]:
    """Extracts file write requests supporting both block and inline syntax."""
    results = []
    seen = set()

    # 1. Block style: [FILE_WRITE: filename] ... [/FILE_WRITE]
    pattern_block = r"\[FILE_WRITE:\s*([^\r\n\]]+)\]([\s\S]*?)\[/FILE_WRITE\]"
    for m in re.finditer(pattern_block, text):
        path = m.group(1).strip()
        content = m.group(2).strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if len(lines) >= 2 and lines[-1].strip() == "```":
                content = "\n".join(lines[1:-1])
        results.append({"path": path, "content": content})
        seen.add(path)

    # 2. Inline style: [FILE_WRITE: filename | content]
    pattern_inline = r"\[FILE_WRITE:\s*([^\|\]\r\n]+)\s*\|\s*([\s\S]*?)\]"
    for m in re.finditer(pattern_inline, text):
        path = m.group(1).strip()
        if path not in seen:
            content = m.group(2).strip()
            results.append({"path": path, "content": content})
            seen.add(path)

    return results


def extract_file_reads(text: str) -> List[str]:
    """Extracts [FILE_READ: path] directives."""
    return [p.strip() for p in re.findall(r"\[FILE_READ:\s*([^\]]+)\]", text) if p.strip()]


def robust_json_load(raw: str) -> Optional[Dict[str, Any]]:
    """Tries parsing JSON with heuristics for unescaped newlines and unescaped quotes."""
    if not raw or not raw.strip():
        return None

    # 1. Direct standard parse
    try:
        return json.loads(raw)
    except Exception:
        pass

    # 2. Repair unescaped double quotes inside common JSON string fields
    try:
        s = raw.replace('\r\n', '\n')

        def _fix_content(m):
            prefix = m.group(1)
            body = m.group(2)
            suffix = m.group(3)
            fixed_body = re.sub(r'(?<!\\)"', r'\"', body)
            return prefix + fixed_body + suffix

        s = re.sub(
            r'("(?:content|task|message|to_user|thought|command|text|prompt)":\s*")([\s\S]*?)("\s*(?:,\s*"|\n\s*\}|\n\s*\]))',
            _fix_content,
            s
        )

        def _fix_newlines(match):
            val = match.group(0)
            return val.replace('\n', '\\n').replace('\r', '')

        s = re.sub(r'"(?:\\.|[^"\\])*"', _fix_newlines, s)
        return json.loads(s)
    except Exception:
        pass

    # 3. Fallback: broader repair across any JSON string property
    try:
        def _fix_any_quotes(m):
            k = m.group(1)
            body = m.group(2)
            end = m.group(3)
            fixed = re.sub(r'(?<!\\)"', r'\"', body)
            return f'"{k}": "{fixed}{end}'

        s2 = re.sub(r'"([a-zA-Z0-9_-]+)":\s*"([\s\S]*?)("\s*(?:,\s*"|\n\s*\}|\n\s*\]))', _fix_any_quotes, raw)
        return json.loads(s2)
    except Exception:
        pass

    return None


def sanitize_user_facing_text(text: Optional[str]) -> str:
    """
    Cleans up any text meant for the user so it contains ONLY pure user-facing information.
    Removes robotic commentary about steps, iterations, subordinate delegation, internal phases,
    and leaked English meta-reasoning ('I need to...', 'Let me delegate...', 'to_agent:...').
    """
    if not text or not str(text).strip():
        return ""
    t = str(text).strip()

    english_meta_markers = [
        r"(?i)\bi\s+need\s+to\b",
        r"(?i)\blet\s+me\s+delegate\b",
        r"(?i)\bi\s+will\s+delegate\b",
        r"(?i)\bthe\s+subagent\b",
        r"(?i)\bquality\s+audit\b",
        r"(?i)\baudit\s+rejection\b",
        r"(?i)\bfile_write\b",
        r"(?i)\bfile_read\b",
        r"(?i)\bto_agent\s*:",
        r"(?i)\bto_user\s*:\s*null\b",
    ]
    t = re.sub(r"```[\s\S]*?```", "", t)
    t = re.sub(r"(?im)^\s*to_agent\s*:[\s\S]*?$", "", t)
    t = re.sub(r"(?im)^\s*to_user\s*:.*$", "", t)

    forbidden_patterns = [
        r"(?im)^\s*шаг\s*\d+.*?(?:завершён|выполнен|пройден|успешно|начался|в процессе)[^.\n]*[.\n]?",
        r"(?i)\bшаг\s*\d+\s*(?:успешно\s*)?(?:завершён|выполнен|пройден)[^.\n]*[.\n]?",
        r"(?i)(?:все\s+)?действия\s+по\s+предыдущему\s+шагу[^.\n]*[.\n]?",
        r"(?i)дополнительных\s+действий\s+специалистов\s+не\s+требуется[^.\n]*[.\n]?",
        r"(?i)поскольку\s+задача[,\s]+судя\s+по\s+всему[,\s]+полностью\s+решена[^.\n]*[.\n]?",
        r"(?i)(?:принято[!,.]?\s*)?(?:передал|передаю)\s+[^.\n]+?(?:ждите\s+результат|начинаю\s+работу|приступаю)[^.\n]*[.\n]?",
        r"(?i)ждите\s+результат[.!]*",
        r"(?i)начинаю\s+работу[.!]*",
        r"(?i)если\s+у\s+вас\s+есть\s+новые\s+уточнения\s+или\s+следующий\s+шаг.*",
        r"(?im)^\s*(?:проверю|проверим|выполню\s+проверку|проведу\s+аудит)\s+созданные\s+файлы.*?[.\n]?",
        r"(?im)^\s*мне\s+нужно\s+(?:увидеть|проверить|изучить)\s+содержимое.*?[.\n]?",
        r"(?im)^\s*давайте\s+провер(?:ю|им)\s+их\s+содержимое.*?[.\n]?",
        r"(?im)^\s*выполню\s+финальную\s+проверку.*?[.\n]?",
        r"(?im)^\s*по\s+результатам\s+аудита:?.*?[.\n]?",
        r"(?im)^\s*достаточно\s+об[ъеё]мный\s+файл.*?[.\n]?",
        r"(?im)^\s*минимальный[,\s]+скорее\s+всего\s+содержит.*?[.\n]?",
    ]

    for pat in forbidden_patterns:
        t = re.sub(pat, "", t)

    clean_lines = []
    for line in t.splitlines():
        line_s = line.strip()
        if not line_s:
            continue
        if any(re.search(em, line_s) for em in english_meta_markers):
            continue
        clean_lines.append(line.rstrip())

    res_text = "\n\n".join(clean_lines).strip()
    russian_chars = len(re.findall(r"[а-яА-ЯёЁ]", res_text))
    if russian_chars < 5 and len(res_text) > 0:
        return ""

    return res_text


def parse_agent_response(text: str) -> Dict[str, Any]:
    """
    Parses agent response into a normalized structure:
    {
        "thought": str,
        "actions": [
            {"type": "to_agent", "recipient": "...", "message": "..."},
            {"type": "spawn_agent", "name": "...", "role": "...", "icon": "...", "task": "..."},
            {"type": "file_write", "path": "...", "content": "..."},
            {"type": "file_read", "path": "..."},
            {"type": "cmd", "command": "..."}
        ],
        "to_user": Optional[str]
    }
    """
    res = {"thought": "", "actions": [], "to_user": None}
    if not text or not text.strip():
        return res

    # 1. Try finding JSON block inside ```json ... ``` or outermost { ... }
    json_candidates = []
    for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", text):
        cand = m.group(1).strip()
        if cand.startswith("{") and cand.endswith("}"):
            json_candidates.append(cand)

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        cand = text[start:end+1].strip()
        if cand not in json_candidates:
            json_candidates.append(cand)

    for cand in json_candidates:
        data = robust_json_load(cand)
        if isinstance(data, dict):
            res["thought"] = data.get("thought", "")
            user_msg = data.get("to_user") or data.get("message_to_user") or data.get("user_message")
            if user_msg and str(user_msg).strip().lower() not in ("null", "none"):
                sanitized_u = sanitize_user_facing_text(str(user_msg))
                if sanitized_u:
                    res["to_user"] = sanitized_u
            raw_actions = data.get("actions", [])
            if isinstance(raw_actions, list):
                for a in raw_actions:
                    if isinstance(a, dict):
                        norm_act = dict(a)
                        # If agent/recipient/role is present, it's always a subagent message/delegation directive
                        if "agent" in norm_act or "recipient" in norm_act or "role" in norm_act:
                            norm_act["type"] = "to_agent"
                            norm_act["recipient"] = norm_act.get("recipient") or norm_act.get("agent") or norm_act.get("role")
                            norm_act["message"] = norm_act.get("message") or norm_act.get("task") or norm_act.get("action") or ""
                        elif "action" in norm_act and "type" not in norm_act:
                            norm_act["type"] = norm_act["action"]
                        elif "type" not in norm_act:
                            if "path" in norm_act and "content" in norm_act:
                                norm_act["type"] = "file_write"
                            elif "path" in norm_act:
                                norm_act["type"] = "file_read"
                            elif "command" in norm_act:
                                norm_act["type"] = "cmd"
                            elif "spawn" in norm_act or ("name" in norm_act and "role" in norm_act):
                                norm_act["type"] = "spawn_agent"
                        if "type" in norm_act:
                            res["actions"].append(norm_act)
            return res

    # 2. Fallback regex parser for raw JSON file_write actions (even if entire JSON is malformed)
    pattern_json_fw = r'\{\s*"type"\s*:\s*"file_write"\s*,\s*"path"\s*:\s*"([^"]+)"\s*,\s*"content"\s*:\s*"'
    matches = list(re.finditer(pattern_json_fw, text))
    for i, m in enumerate(matches):
        fpath = m.group(1).strip()
        c_start = m.end()
        if i + 1 < len(matches):
            chunk = text[c_start:matches[i+1].start()]
            m_end = re.search(r'"\s*\}\s*,?\s*$', chunk)
            raw_c = chunk[:m_end.start()] if m_end else chunk
        else:
            chunk = text[c_start:]
            m_end = re.search(r'"\s*\}\s*\]', chunk)
            raw_c = chunk[:m_end.start()] if m_end else chunk
        try:
            cleaned_c = raw_c.encode('utf-8').decode('unicode_escape')
        except Exception:
            cleaned_c = raw_c.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
        if not any(a.get("type") == "file_write" and a.get("path") == fpath for a in res["actions"]):
            res["actions"].append({
                "type": "file_write",
                "path": fpath,
                "content": cleaned_c
            })

    # 3. Fallback regex parser for raw JSON commands
    for m_cmd_json in re.finditer(r'\{\s*"type"\s*:\s*"cmd"\s*,\s*"command"\s*:\s*"([^"]+)"', text):
        c_str = m_cmd_json.group(1).replace('\\"', '"').replace('\\\\', '\\').strip()
        if not any(a.get("type") == "cmd" and a.get("command") == c_str for a in res["actions"]):
            res["actions"].append({
                "type": "cmd",
                "command": c_str
            })

    # 4. Fallback extract to_user & thought from raw JSON if still empty
    if not res["to_user"]:
        m_user_json = re.search(r'"to_user"\s*:\s*"([\s\S]*?)"(?:\s*\}|\s*$)', text)
        if m_user_json:
            u_txt = m_user_json.group(1).replace('\\n', '\n').replace('\\"', '"').strip()
            if u_txt and u_txt.lower() not in ("null", "none", '""', "''"):
                sanitized_raw_u = sanitize_user_facing_text(u_txt)
                if sanitized_raw_u:
                    res["to_user"] = sanitized_raw_u

    if not res["thought"]:
        m_th_json = re.search(r'"thought"\s*:\s*"([\s\S]*?)"(?:\s*,\s*"actions"|\s*\}|\s*$)', text)
        if m_th_json:
            res["thought"] = m_th_json.group(1).replace('\\n', '\n').replace('\\"', '"').strip()

    # 5. Tag fallback parser (if agent uses XML tags or bracket tags)
    if not res["to_user"]:
        m_user = re.search(r"<(?:to_user|user_message)>([\s\S]*?)</(?:to_user|user_message)>", text)
        if m_user:
            res["to_user"] = sanitize_user_facing_text(m_user.group(1).strip())
        else:
            m_user_bracket = re.search(r"\[TO_USER:\s*([\s\S]*?)\](?=\s*(?:\[|<|$))", text)
            if m_user_bracket:
                res["to_user"] = sanitize_user_facing_text(m_user_bracket.group(1).strip())

    # 1. XML style: <to_agent ...>...</to_agent> with or without name attribute
    for m_agent in re.finditer(r'<to_agent(?:\s+(?:name|agent|recipient|to)=["\']([^"\']+)["\'])?\s*>([\s\S]*?)</to_agent>', text):
        recip = m_agent.group(1) or "FrontendDev"
        msg = m_agent.group(2).strip()
        if not any(a.get("type") == "to_agent" and a.get("message") == msg for a in res["actions"]):
            res["actions"].append({
                "type": "to_agent",
                "recipient": recip.strip(),
                "message": msg
            })

    # 2. Bracket style: [TO_AGENT: Recipient | Message] or [TO_AGENT: Message]
    for m_assign in re.finditer(r'\[(?:TO_AGENT|ASSIGN):\s*(?:([^\|\]]+)\s*\|\s*)?([^\]]+)\]', text):
        recip = m_assign.group(1) or "FrontendDev"
        msg = m_assign.group(2).strip()
        if not any(a.get("type") == "to_agent" and a.get("message") == msg for a in res["actions"]):
            res["actions"].append({
                "type": "to_agent",
                "recipient": recip.strip(),
                "message": msg
            })

    # 3. Pseudo-YAML style: to_agent: "..." or to_agent [Recipient]: "..."
    pattern_yaml_to_agent = r'(?:^|\n)\s*to_agent(?:\s*\[([^\]]+)\]|\s*:?\s*([a-zA-Zа-яА-Я0-9_-]+))?\s*:\s*(?:"([\s\S]*?)"|\'([\s\S]*?)\'|([^\n\r]+(?:\n(?!\s*(?:to_user|actions|thought|```))[\s\S]*?)?))'
    for m_yaml in re.finditer(pattern_yaml_to_agent, text):
        recip = m_yaml.group(1) or m_yaml.group(2) or "FrontendDev"
        msg = (m_yaml.group(3) or m_yaml.group(4) or m_yaml.group(5) or "").strip()
        if msg and not any(a.get("type") == "to_agent" and a.get("message") == msg for a in res["actions"]):
            res["actions"].append({
                "type": "to_agent",
                "recipient": recip.strip(),
                "message": msg
            })

    for m_spawn in re.finditer(r'<spawn_agent\s+name=["\']([^"\']+)["\']\s+role=["\']([^"\']+)["\'](?:\s+icon=["\']([^"\']+)["\'])?>([\s\S]*?)</spawn_agent>', text):
        res["actions"].append({
            "type": "spawn_agent",
            "name": m_spawn.group(1).strip(),
            "role": m_spawn.group(2).strip(),
            "icon": m_spawn.group(3).strip() if m_spawn.group(3) else "🤖",
            "task": m_spawn.group(4).strip()
        })
    for m_spawn in re.finditer(r'\[SPAWN:\s*([^\|\]]+)\s*\|\s*([^\|\]]+)(?:\s*\|\s*([^\|\]]+))?(?:\s*\|\s*([^\]]+))?\]', text):
        s_name = m_spawn.group(1).strip()
        s_role = m_spawn.group(2).strip()
        s_p3 = m_spawn.group(3).strip() if m_spawn.group(3) else ""
        s_p4 = m_spawn.group(4).strip() if m_spawn.group(4) else ""
        s_icon = s_p3 if s_p3 and len(s_p3) <= 4 else "🤖"
        s_task = s_p4 if s_p4 else (s_p3 if len(s_p3) > 4 else "")
        res["actions"].append({
            "type": "spawn_agent",
            "name": s_name,
            "role": s_role,
            "icon": s_icon,
            "task": s_task
        })

    for m_fw in re.finditer(r'<file_write\s+path=["\']([^"\']+)["\']>([\s\S]*?)</file_write>', text):
        res["actions"].append({
            "type": "file_write",
            "path": m_fw.group(1).strip(),
            "content": m_fw.group(2).strip()
        })
    for fw in extract_file_writes(text):
        if not any(a.get("type") == "file_write" and a.get("path") == fw["path"] for a in res["actions"]):
            res["actions"].append({
                "type": "file_write",
                "path": fw["path"],
                "content": fw["content"]
            })

    for m_fr in re.finditer(r'<file_read\s+path=["\']([^"\']+)["\']\s*/?>', text):
        res["actions"].append({
            "type": "file_read",
            "path": m_fr.group(1).strip()
        })
    for fr in extract_file_reads(text):
        if not any(a.get("type") == "file_read" and a.get("path") == fr for a in res["actions"]):
            res["actions"].append({
                "type": "file_read",
                "path": fr
            })

    for m_cmd in re.finditer(r'<cmd>([\s\S]*?)</cmd>', text):
        res["actions"].append({
            "type": "cmd",
            "command": m_cmd.group(1).strip()
        })
    for cmd_str in re.findall(r'\[CMD:\s*([^\]]+)\]', text):
        if not any(a.get("type") == "cmd" and a.get("command") == cmd_str for a in res["actions"]):
            res["actions"].append({
                "type": "cmd",
                "command": cmd_str.strip()
            })

    if not res["to_user"]:
        cleaned = clean_all_directives(text)
        if cleaned:
            res["to_user"] = cleaned

    return res


def clean_all_directives(text: str) -> str:
    """Removes technical tags, XML blocks, and JSON structures for clean user-facing presentation."""
    if not text:
        return ""

    # If the text has a structured agent response with to_user, return to_user directly
    try:
        parsed = parse_agent_response(text)
        if parsed.get("to_user"):
            return parsed["to_user"]
    except Exception:
        pass

    cleaned = re.sub(r"```(?:json)?\s*\{[\s\S]*?\}\s*```", "", text)
    m_user = re.search(r"<(?:to_user|user_message)>([\s\S]*?)</(?:to_user|user_message)>", cleaned)
    if m_user:
        cleaned = m_user.group(1).strip()
    m_user_bracket = re.search(r"\[TO_USER:\s*([\s\S]*?)\]", cleaned)
    if m_user_bracket:
        cleaned = m_user_bracket.group(1).strip()

    cleaned = re.sub(r"<to_agent[^>]*>[\s\S]*?</to_agent>", "", cleaned)
    cleaned = re.sub(r"<spawn_agent[^>]*>[\s\S]*?</spawn_agent>", "", cleaned)
    cleaned = re.sub(r"<file_write[^>]*>[\s\S]*?</file_write>", "", cleaned)
    cleaned = re.sub(r"<file_read[^>]*>[\s\S]*?</file_read>", "", cleaned)
    cleaned = re.sub(r"<cmd>[\s\S]*?</cmd>", "", cleaned)
    cleaned = re.sub(r"\[FILE_WRITE:\s*([^\r\n\]]+)\]([\s\S]*?)\[/FILE_WRITE\]", "", cleaned)
    cleaned = re.sub(r"\[FILE_WRITE:\s*([^\|\]\r\n]+)\s*\|\s*([\s\S]*?)\]", "", cleaned)
    cleaned = re.sub(r"\[FILE_READ:\s*([^\]]+)\]", "", cleaned)
    cleaned = re.sub(r"\[CMD:\s*([^\]]+)\]", "", cleaned)
    cleaned = re.sub(r"\[ASSIGN:\s*([^\|\]]+)\s*\|\s*([^\]]+)\]", "", cleaned)
    cleaned = re.sub(r"\[SPAWN:\s*([^\]]+)\]", "", cleaned)
    cleaned = re.sub(r"\[DONE\]", "", cleaned, flags=re.IGNORECASE)

    cleaned_strip = cleaned.strip()
    if cleaned_strip.startswith("{") and cleaned_strip.endswith("}"):
        try:
            d = robust_json_load(cleaned_strip)
            if isinstance(d, dict):
                return sanitize_user_facing_text(d.get("to_user") or d.get("message_to_user") or "")
        except Exception:
            pass
    return sanitize_user_facing_text(cleaned.strip())


def execute_shell_command(command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Executes a shell command via PowerShell in the project workspace directory."""
    clean_cmd = command.strip()
    if not clean_cmd:
        return {"success": False, "command": "", "output": "Пустая команда", "code": 1}

    target_dir = ROOT_DIR
    if cwd:
        try:
            cand = Path(cwd).resolve()
            if cand.exists() and cand.is_dir():
                target_dir = cand
        except Exception:
            pass

    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", clean_cmd],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        full_output = out
        if err:
            full_output = (full_output + "\n" if full_output else "") + err
        return {
            "success": proc.returncode == 0,
            "command": clean_cmd,
            "cwd": str(target_dir),
            "output": full_output or "(Команда выполнена успешно, вывод пуст)",
            "code": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "command": clean_cmd,
            "cwd": str(target_dir),
            "output": "Превышен таймаут выполнения команды (30 сек)",
            "code": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "command": clean_cmd,
            "cwd": str(target_dir),
            "output": f"Ошибка запуска терминала: {e}",
            "code": 1,
        }


@app.route("/api/terminal/exec", methods=["POST"])
def api_terminal_exec():
    data = request.json or {}
    cmd = data.get("command", "").strip()
    project_id = data.get("project_id")
    cwd = data.get("cwd")
    if not cwd and project_id:
        proj = projects_manager.get_project(project_id)
        if proj:
            cwd = proj.get("root_path")
    result = execute_shell_command(cmd, cwd=cwd)
    return jsonify(result)


def run_subagent_task_internal(project_id: str, agent_id: str, task_desc: str, thinking_enabled: bool = True) -> Dict[str, Any]:
    """Executes a subagent task inside its dedicated chat session and records history."""
    proj = projects_manager.get_project(project_id)
    if not proj:
        return {"text": "Ошибка: Проект не найден", "thinking": "", "executed_commands": [], "steps": []}

    target_agent = None
    for a in proj.get("subagents", []):
        if a["id"] == agent_id:
            target_agent = a
            break

    if not target_agent:
        return {"text": "Ошибка: Субагент не найден", "thinking": "", "executed_commands": [], "steps": []}

    project_root = proj.get("root_path") or str(ROOT_DIR)

    # Record incoming task in subagent history
    projects_manager.append_subagent_message(
        project_id,
        agent_id,
        role="USER",
        text=f"📋 [Поручение от Руководителя проекта]:\n{task_desc}"
    )

    client = get_client()
    chat_id = target_agent.get("chat_session_id")
    if not chat_id:
        try:
            chat_id = client.create_chat()
            projects_manager.set_subagent_chat_session(project_id, agent_id, chat_id)
        except Exception:
            chat_id = f"subchat_{agent_id}_{int(time.time())}"

    system_role = target_agent.get("system_prompt", f"Ты — {target_agent['name']}, специалист в роли: {target_agent['role']}.")
    prompt = (
        f"Ты — специалист, работающий на реальном компьютере Windows.\n"
        f"Твоя роль: {system_role}\n"
        f"Проект: '{proj['name']}'\n"
        f"Основная рабочая директория проекта (Workspace Root): {project_root}\n"
        f"У тебя есть прямой доступ к файловой системе и терминалу этой папки!\n\n"
        f"Твоя задача: {task_desc}\n\n"
        "ФОРМАТ ОТВЕТА (СТРОГО JSON):\n"
        "Отвечай строго в формате JSON в блоке ```json ... ```:\n"
        "```json\n"
        "{\n"
        "  \"thought\": \"Краткий ход мыслей по решению задачи\",\n"
        "  \"actions\": [\n"
        "    {\n"
        "      \"type\": \"file_write\",\n"
        "      \"path\": \"относительный_путь_к_файлу\",\n"
        "      \"content\": \"содержимое файла\"\n"
        "    },\n"
        "    {\n"
        "      \"type\": \"file_read\",\n"
        "      \"path\": \"относительный_путь_к_файлу\"\n"
        "    },\n"
        "    {\n"
        "      \"type\": \"cmd\",\n"
        "      \"command\": \"powershell команда\"\n"
        "    }\n"
        "  ],\n"
        "  \"to_user\": \"Понятный и структурированный отчет о проделанной работе\"\n"
        "}\n"
        "```\n\n"
        "КРИТИЧЕСКИ ВАЖНО:\n"
        "Если задача требует создания, редактирования файла или сохранения сценария/текста/кода — "
        "ОБЯЗАТЕЛЬНО добавь в `actions` действие `file_write` с относительным путем и содержимым файла!\n"
        "Никогда не выводи служебный код в текст, пиши только структурированный JSON.\n\n"
        "ПРАВИЛА АВТОНОМНОГО ВЫПОЛНЕНИЯ:\n"
        "1. Ты можешь выполнять неограниченное количество последовательных действий (читать файлы, выполнять консольные команды, создавать и редактировать файлы) шаг за шагом, пока полностью не выполнишь задачу.\n"
        "2. Система выполняет каждое твое действие и возвращает тебе результат на следующем шаге.\n"
        "3. Когда задача полностью выполнена:\n"
        "   - Сформулируй итоговый понятный отчет в поле `to_user`.\n"
        "   - В поле `actions` передай `[]` (или укажи финальные действия)."
    )

    try:
        max_sub_turns = 30
        executed_cmds = []
        sub_steps = []
        current_sub_prompt = prompt
        last_cleaned_text = ""
        full_ans_think = []
        last_ans_text = ""

        for sub_turn in range(1, max_sub_turns + 1):
            res = client.send_message(chat_id, current_sub_prompt, stream=False, thinking_enabled=thinking_enabled)
            ans_text = res.get("text", "")
            ans_think = res.get("thinking", "")
            last_ans_text = ans_text

            if ans_think:
                full_ans_think.append(ans_think)

            parsed = parse_agent_response(ans_text)
            if ans_think and not any(s.get("category") == "thought" for s in sub_steps):
                sub_steps.append({
                    "category": "thought",
                    "title": "Thought process",
                    "thought": ans_think
                })
            elif parsed.get("thought") and not any(s.get("category") == "thought" for s in sub_steps):
                sub_steps.append({
                    "category": "thought",
                    "title": "Thought process",
                    "thought": parsed["thought"]
                })

            turn_observations = []
            has_actions = bool(parsed.get("actions"))
            for act in parsed.get("actions", []):
                a_type = act.get("type", "")
                if a_type == "file_write":
                    path = act.get("path", "").strip()
                    content = act.get("content", "")
                    w_res = write_project_file(project_root, path, content)
                    sub_steps.append({
                        "category": "file",
                        "title": f"Created file {path}",
                        "file_path": path,
                        "full_path": w_res.get("path", ""),
                        "size": w_res.get("size", 0),
                        "success": w_res.get("success", False),
                    })
                    turn_observations.append(f"[Файл '{path}' успешно сохранен на диске ({w_res.get('size', 0)} байт)]")
                elif a_type == "file_read":
                    path = act.get("path", "").strip()
                    r_res = read_project_file(project_root, path)
                    sub_steps.append({
                        "category": "file_read",
                        "title": f"Read file {path}",
                        "file_path": path,
                        "success": r_res.get("success", False),
                        "output": r_res.get("content", r_res.get("error", "")),
                    })
                    file_content = r_res.get("content", r_res.get("error", ""))
                    turn_observations.append(f"[Содержимое файла '{path}']:\n{file_content}")
                elif a_type == "cmd":
                    cmd_str = act.get("command", "").strip()
                    cmd_res = execute_shell_command(cmd_str, cwd=project_root)
                    executed_cmds.append(cmd_res)
                    sub_steps.append({
                        "category": "cmd",
                        "title": f"Ran {cmd_str}",
                        "command": cmd_str,
                        "output": cmd_res["output"],
                        "code": cmd_res["code"]
                    })
                    turn_observations.append(f"[Результат выполнения команды `{cmd_str}` (код {cmd_res['code']})]:\n{cmd_res['output']}")

            if parsed.get("to_user"):
                last_cleaned_text = parsed["to_user"]

            # If agent requested no more actions:
            if not has_actions:
                # If agent only read files and never wrote any file, don't stop early!
                has_any_write = any(s.get("category") == "file" for s in sub_steps)
                has_any_read = any(s.get("category") == "file_read" for s in sub_steps)
                if has_any_read and not has_any_write and sub_turn < max_sub_turns:
                    current_sub_prompt = (
                        f"НАПОМИНАНИЕ ИСХОДНОЙ ЗАДАЧИ:\n{task_desc}\n\n"
                        "Ты прочитал файл, но ещё НЕ сохранил требуемые изменения на диск!\n"
                        "Теперь внеси все необходимые изменения в код согласно задаче и ОБЯЗАТЕЛЬНО сохрани итоговый файл через действие `file_write` в блоке JSON."
                    )
                    continue
                break

            # If all actions were file_write and agent already gave a complete to_user report: done!
            only_writes = all(act.get("type") == "file_write" for act in parsed.get("actions", []))
            if only_writes and parsed.get("to_user"):
                break

            obs_joined = "\n\n".join(turn_observations) if turn_observations else "Действие выполнено."
            current_sub_prompt = (
                f"НАПОМИНАНИЕ ИСХОДНОЙ ЗАДАЧИ:\n{task_desc}\n\n"
                f"[Результаты операций]:\n{obs_joined}\n\n"
                "ИНСТРУКЦИЯ К СЛЕДУЮЩЕЙ ОПЕРАЦИИ:\n"
                "Ты получил данные/прочитал файл. Теперь выполни требуемые изменения в коде согласно задаче "
                "и ОБЯЗАТЕЛЬНО сохрани итоговый файл на диск через действие `file_write` в формате JSON!\n"
                "Не завершай задачу без сохранения готового файла."
            )

        # Mark agent as done and store in tasks
        projects_manager.update_agent_task(project_id, agent_id, task_desc, status="done", progress=100)

        cleaned_text = last_cleaned_text or clean_all_directives(last_ans_text)
        if not cleaned_text:
            created_fs = [st for st in sub_steps if st.get("category") == "file"]
            if created_fs:
                cleaned_text = f"Файл `{created_fs[0]['file_path']}` успешно сохранен на диске."
            else:
                cleaned_text = "Задача выполнена."

        total_thinking = "\n\n".join(full_ans_think)
        projects_manager.append_subagent_message(
            project_id,
            agent_id,
            role="ASSISTANT",
            text=cleaned_text,
            thinking=total_thinking,
            steps=sub_steps,
            message_id=client._session_last_msg_ids.get(chat_id),
        )

        return {
            "text": cleaned_text,
            "raw_text": last_ans_text,
            "thinking": total_thinking,
            "executed_commands": executed_cmds,
            "steps": sub_steps
        }
    except Exception as e:
        err_msg = f"Ошибка выполнения задачи субагентом: {e}"
        projects_manager.append_subagent_message(project_id, agent_id, role="ASSISTANT", text=err_msg)
        return {"text": err_msg, "thinking": "", "executed_commands": [], "steps": []}


@app.route("/api/projects/<project_id>/lead/history", methods=["GET"])
def api_project_lead_history(project_id):
    proj = projects_manager.get_project(project_id)
    if not proj:
        return jsonify({"success": False, "messages": []})
    return jsonify({"success": True, "messages": proj.get("lead_agent", {}).get("history", [])})


@app.route("/api/projects/<project_id>/agents/<agent_id>/history", methods=["GET"])
def api_get_subagent_history(project_id, agent_id):
    """Returns message history for a specific subagent."""
    proj = projects_manager.get_project(project_id)
    if not proj:
        return jsonify({"success": False, "messages": []})
    for a in proj.get("subagents", []):
        if a["id"] == agent_id:
            return jsonify({"success": True, "agent": a, "messages": a.get("history", [])})
    return jsonify({"success": False, "error": "Agent not found"}), 404


@app.route("/api/projects/<project_id>/agents/<agent_id>/message", methods=["POST"])
def api_subagent_message(project_id, agent_id):
    """Direct conversation with a subagent in its own dedicated chat session."""
    data = request.json or {}
    user_prompt = data.get("prompt", "")
    thinking_enabled = data.get("thinking_enabled", False)

    proj = projects_manager.get_project(project_id)
    if not proj:
        return jsonify({"success": False, "error": "Project not found"}), 404

    target_agent = None
    for a in proj.get("subagents", []):
        if a["id"] == agent_id:
            target_agent = a
            break

    if not target_agent:
        return jsonify({"success": False, "error": "Agent not found"}), 404

    project_root = proj.get("root_path") or str(ROOT_DIR)
    projects_manager.append_subagent_message(project_id, agent_id, "USER", user_prompt)

    client = get_client()
    chat_id = target_agent.get("chat_session_id")
    if not chat_id:
        try:
            chat_id = client.create_chat()
            projects_manager.set_subagent_chat_session(project_id, agent_id, chat_id)
        except Exception:
            chat_id = f"subchat_{agent_id}_{int(time.time())}"

    system_role = target_agent.get("system_prompt", f"Ты — {target_agent['name']}, специалист в роли: {target_agent['role']}.")
    full_prompt = (
        f"Ты — специалист, работающий на реальном компьютере Windows.\n"
        f"Твоя роль: {system_role}\n"
        f"Проект: '{proj['name']}'\n"
        f"Рабочая директория проекта (Workspace Root): {project_root}\n\n"
        f"Пользователь обращается напрямую к тебе:\n{user_prompt}\n\n"
        "ФОРМАТ ОТВЕТА (СТРОГО JSON):\n"
        "Отвечай строго в формате JSON в блоке ```json ... ```:\n"
        "```json\n"
        "{\n"
        "  \"thought\": \"Краткий ход мыслей\",\n"
        "  \"actions\": [\n"
        "    { \"type\": \"file_write\", \"path\": \"относительный_путь\", \"content\": \"содержимое\" },\n"
        "    { \"type\": \"file_read\", \"path\": \"относительный_путь\" },\n"
        "    { \"type\": \"cmd\", \"command\": \"powershell команда\" }\n"
        "  ],\n"
        "  \"to_user\": \"Твой структурированный и понятный ответ пользователю в Markdown\"\n"
        "}\n"
        "```\n\n"
        "ВАЖНО:\n"
        "Если требуется создать, изменить или сохранить файл — обязательно добавь в `actions` действие `file_write` с путем и содержимым!\n"
        "В поле `to_user` напиши красивый, понятный ответ для пользователя.\n\n"
        "ПРАВИЛА АВТОНОМНОГО ВЫПОЛНЕНИЯ:\n"
        "1. Ты можешь выполнять неограниченное количество последовательных действий (читать файлы, выполнять команды терминала, создавать и редактировать файлы) шаг за шагом, пока полностью не выполнишь задачу.\n"
        "2. Система выполняет каждое твое действие и возвращает тебе результат на следующем шаге.\n"
        "3. Когда задача полностью выполнена:\n"
        "   - Сформулируй итоговый понятный ответ в поле `to_user`.\n"
        "   - В поле `actions` передай `[]` (или укажи финальные действия)."
    )

    def generate_subagent_sse():
        all_accumulated_steps = []
        full_thinking_history = []
        last_clean_text = ""
        current_sub_prompt = full_prompt
        max_sub_loop = 30  # Unlimited autonomous action steps
        last_raw_ans = ""

        try:
            for sub_loop_idx in range(1, max_sub_loop + 1):
                yield f"data: {json.dumps({'type': 'loop_step_start', 'step': sub_loop_idx}, ensure_ascii=False)}\n\n"
                collected_text = []
                collected_thinking = []
                t_start = time.time()

                stream = client.send_message(
                    chat_session_id=chat_id,
                    prompt=current_sub_prompt,
                    stream=True,
                    thinking_enabled=thinking_enabled,
                )
                for chunk in stream:
                    if chunk["type"] == "thinking":
                        collected_thinking.append(chunk["content"])
                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                    elif chunk["type"] == "text":
                        collected_text.append(chunk["content"])

                raw_ans = "".join(collected_text)
                last_raw_ans = raw_ans
                full_think = "".join(collected_thinking)
                if full_think:
                    full_thinking_history.append(full_think)

                parsed = parse_agent_response(raw_ans)

                if full_think:
                    think_dur = int(time.time() - t_start)
                    th_step = {
                        "category": "thought",
                        "title": f"Thought for {max(1, think_dur)}s",
                        "thought": full_think,
                        "duration": f"{think_dur}s"
                    }
                    all_accumulated_steps.append(th_step)
                    yield f"data: {json.dumps({'type': 'action_step', 'step': th_step}, ensure_ascii=False)}\n\n"
                elif parsed.get("thought"):
                    th_step = {
                        "category": "thought",
                        "title": "Thought process",
                        "thought": parsed["thought"]
                    }
                    all_accumulated_steps.append(th_step)
                    yield f"data: {json.dumps({'type': 'action_step', 'step': th_step}, ensure_ascii=False)}\n\n"

                turn_observations = []
                has_actions = bool(parsed.get("actions"))
                has_write = False

                for act in parsed.get("actions", []):
                    a_type = act.get("type", "")
                    if a_type == "file_write":
                        has_write = True
                        path = act.get("path", "").strip()
                        content = act.get("content", "")
                        w_res = write_project_file(project_root, path, content)
                        file_step = {
                            "category": "file",
                            "title": f"Created file {path}",
                            "file_path": path,
                            "full_path": w_res.get("path", ""),
                            "size": w_res.get("size", 0),
                            "success": w_res.get("success", False),
                        }
                        all_accumulated_steps.append(file_step)
                        yield f"data: {json.dumps({'type': 'action_step', 'step': file_step}, ensure_ascii=False)}\n\n"
                        turn_observations.append(f"[Файл '{path}' сохранен на диске ({w_res.get('size', 0)} байт)]")

                    elif a_type == "file_read":
                        path = act.get("path", "").strip()
                        r_res = read_project_file(project_root, path)
                        read_step = {
                            "category": "file_read",
                            "title": f"Read file {path}",
                            "file_path": path,
                            "success": r_res.get("success", False),
                            "output": r_res.get("content", r_res.get("error", "")),
                        }
                        all_accumulated_steps.append(read_step)
                        yield f"data: {json.dumps({'type': 'action_step', 'step': read_step}, ensure_ascii=False)}\n\n"
                        file_content = r_res.get("content", r_res.get("error", ""))
                        turn_observations.append(f"[Содержимое файла '{path}']:\n{file_content}")

                    elif a_type == "cmd":
                        cmd_str = act.get("command", "").strip()
                        t0 = time.time()
                        res_cmd = execute_shell_command(cmd_str, cwd=project_root)
                        dur = time.time() - t0
                        step_obj = {
                            "category": "cmd",
                            "title": f"Ran {cmd_str}",
                            "command": cmd_str,
                            "output": res_cmd["output"],
                            "code": res_cmd["code"],
                            "duration": f"{dur:.1f}s"
                        }
                        all_accumulated_steps.append(step_obj)
                        yield f"data: {json.dumps({'type': 'action_step', 'step': step_obj}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'terminal_cmd', 'sender': target_agent['name'], 'command': cmd_str, 'output': res_cmd['output'], 'code': res_cmd['code']}, ensure_ascii=False)}\n\n"
                        turn_observations.append(f"[Результат выполнения команды `{cmd_str}` (код {res_cmd['code']})]:\n{res_cmd['output']}")

                if parsed.get("to_user"):
                    last_clean_text = parsed["to_user"]
                    yield f"data: {json.dumps({'type': 'user_message_update', 'text': last_clean_text}, ensure_ascii=False)}\n\n"

                # Check if subagent is done
                if not has_actions:
                    has_any_write = any(s.get("category") == "file" for s in all_accumulated_steps)
                    has_any_read = any(s.get("category") == "file_read" for s in all_accumulated_steps)
                    if has_any_read and not has_any_write and sub_loop_idx < max_sub_loop:
                        current_sub_prompt = (
                            f"НАПОМИНАНИЕ ИСХОДНОЙ ЗАДАЧИ:\n{user_prompt}\n\n"
                            "Ты прочитал файл, но ещё НЕ сохранил требуемые изменения на диск!\n"
                            "Теперь внеси все необходимые изменения в код согласно задаче и ОБЯЗАТЕЛЬНО сохрани итоговый файл через действие `file_write` в блоке JSON."
                        )
                        continue
                    break

                if has_write and not any(a.get("type") in ("cmd", "file_read") for a in parsed.get("actions", [])) and parsed.get("to_user"):
                    break

                obs_joined = "\n\n".join(turn_observations) if turn_observations else "Действие выполнено."
                current_sub_prompt = (
                    f"НАПОМИНАНИЕ ИСХОДНОЙ ЗАДАЧИ:\n{user_prompt}\n\n"
                    f"[Результаты операций]:\n{obs_joined}\n\n"
                    "ИНСТРУКЦИЯ К СЛЕДУЮЩЕЙ ОПЕРАЦИИ:\n"
                    "Ты получил данные/прочитал файл. Теперь выполни требуемые изменения в коде согласно задаче "
                    "и ОБЯЗАТЕЛЬНО сохрани итоговый файл на диск через действие `file_write` в формате JSON!\n"
                    "Не завершай задачу без сохранения готового файла."
                )

            # Subagent loop finished
            created_fs = [st for st in all_accumulated_steps if st.get("category") == "file" and st.get("success")]
            if created_fs and (not last_clean_text or any(w in last_clean_text.lower() for w in ["запускаю", "начинаю", "читаю файл"])):
                files_list_str = "\n".join([f"• `{st.get('file_path')}`" for st in created_fs])
                cleaned_ans = f"✅ **Задача выполнена!**\n\nСоздано/обновлено файлов ({len(created_fs)} шт.):\n{files_list_str}\n\nРабочая директория: `{project_root}`."
            else:
                cleaned_ans = last_clean_text or clean_all_directives(last_raw_ans) or "Задача выполнена."

            full_think_total = "\n\n".join(full_thinking_history)
            projects_manager.append_subagent_message(
                project_id,
                agent_id,
                "ASSISTANT",
                cleaned_ans,
                full_think_total,
                steps=all_accumulated_steps,
                message_id=client._session_last_msg_ids.get(chat_id),
            )

            yield f"data: {json.dumps({'type': 'final_text', 'text': cleaned_ans, 'steps': all_accumulated_steps}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except (GeneratorExit, Exception) as e:
            if all_accumulated_steps or last_clean_text:
                interrupted_text = last_clean_text or "Выполнение было остановлено."
                try:
                    projects_manager.append_subagent_message(
                        project_id,
                        agent_id,
                        "ASSISTANT",
                        interrupted_text,
                        "\n\n".join(full_thinking_history),
                        steps=all_accumulated_steps,
                        message_id=client._session_last_msg_ids.get(chat_id),
                    )
                except Exception:
                    pass
            if isinstance(e, GeneratorExit):
                return
            err_data = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(err_data, ensure_ascii=False)}\n\n"

    return Response(generate_subagent_sse(), mimetype="text/event-stream")


@app.route("/api/projects/<project_id>/lead/message", methods=["POST"])
def api_project_lead_message(project_id):
    """Autonomous multi-agent coordinator loop (ReAct) with tool execution and subagent delegation."""
    data = request.json or {}
    user_prompt = data.get("prompt", "")
    thinking_enabled = data.get("thinking_enabled", False)

    proj = projects_manager.get_project(project_id)
    if not proj:
        return jsonify({"success": False, "error": "Project not found"}), 404

    lead = proj.get("lead_agent", {})

    # Record user message in lead history
    projects_manager.append_lead_message(project_id, "USER", user_prompt)

    client = get_client()
    chat_id = lead.get("chat_session_id")
    if not chat_id:
        try:
            chat_id = client.create_chat()
            all_projs = projects_manager.load_all()
            for p in all_projs:
                if p["id"] == project_id:
                    p["lead_agent"]["chat_session_id"] = chat_id
                    projects_manager.save_all(all_projs)
                    break
        except Exception:
            chat_id = f"lead_chat_{int(time.time())}"

    def generate_autonomous_sse():
        # Fresh snapshot of subagents
        fresh_proj = projects_manager.get_project(project_id) or proj
        subagents = fresh_proj.get("subagents", [])
        project_root = fresh_proj.get("root_path") or str(ROOT_DIR)

        is_solo = fresh_proj.get("mode") == "solo"

        agents_desc = []
        for a in subagents:
            st = a.get("status", "idle")
            if st == "done" or not a.get("current_task") or a.get("current_task") == "Ожидает назначения задачи":
                agents_desc.append(f"- {a['name']} ({a['role']}): статус [свободен, готов к новым задачам]")
            else:
                short_task = a.get("current_task", "")[:120].replace('\n', ' ')
                agents_desc.append(f"- {a['name']} ({a['role']}): статус [{st}], текущая задача: '{short_task}'")
        subagents_context = "\n".join(agents_desc) if agents_desc else "Пока нет субагентов."

        if is_solo:
            system_prefix = (
                f"Ты — Единый Универсальный Автономный Инженер проекта '{fresh_proj['name']}'.\n"
                f"Все задачи ты выполняешь на настоящем компьютере Windows.\n"
                f"Основная рабочая папка проекта (Workspace Root): {project_root}\n\n"
                "ГЛАВНОЕ ПРАВИЛО: ТЫ РАБОТАЕШЬ ОДИН БЕЗ СУБАГЕНТОВ!\n"
                "Все задачи пользователя ты решаешь ПОЛНОСТЬЮ САМОСТОЯТЕЛЬНО от начала до конца:\n"
                "- Лично пишешь весь программный код, разметку, стили и скрипты.\n"
                "- Физически создаёшь и сохраняешь файлы на диск через действие `file_write` в рабочую папку ({project_root}).\n"
                "- Проверяешь существующие файлы через `file_read`.\n"
                "- Запускаешь консольные команды (тесты, скрипты, запуск) через действие `cmd`.\n"
                "- Ты НЕ используешь действия `to_agent` и `spawn_agent` — субагентов нет, всю работу ты делаешь сам.\n\n"
                "СТРОЖАЙШЕЕ ПРАВИЛО ОБЩЕНИЯ С ПОЛЬЗОВАТЕЛЕМ (КРИТИЧЕСКИ ВАЖНО):\n"
                "- НИКАКИХ СЛОВ О ШАГАХ, ИТЕРАЦИЯХ И ВНУТРЕННИХ ПРОЦЕССАХ!\n"
                "  Пользователь не должен знать о внутренней кухне. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНЫ фразы:\n"
                "  «Шаг 1 успешно завершён», «Все действия по шагу выполнены», «Создаю файл, ждите».\n"
                "- ТОЛЬКО СУГУБО ПОЛЬЗОВАТЕЛЬСКАЯ ИНФОРМАЦИЯ В `to_user`:\n"
                "  Пиши только то, что полезно конечному пользователю: что сделано, какие файлы созданы, как запустить или открыть результат, как управлять.\n"
                "- Если задача ещё в процессе решения (пишешь код, сохраняешь файлы, проверяешь) — передавай `\"to_user\": null`.\n"
                "  Пиши пользователю только тогда, когда всё полностью готово и проверено!\n\n"
                "ЯЗЫК МЫШЛЕНИЯ И ОТВЕТОВ (СТРОГО РУССКИЙ):\n"
                "Все размышления (`thought`) и сообщения пользователю (`to_user`) должны быть ИСКЛЮЧИТЕЛЬНО НА РУССКОМ ЯЗЫКЕ.\n\n"
                "ФОРМАТ ВЗАИМОДЕЙСТВИЯ (СТРОГО JSON):\n"
                "Отвечай строго в формате JSON в блоке ```json ... ``` следующей структуры:\n"
                "```json\n"
                "{\n"
                "  \"thought\": \"Твои краткие внутренние размышления на русском (не показываются пользователю в чате)\",\n"
                "  \"actions\": [\n"
                "    {\n"
                "      \"type\": \"file_write\",\n"
                "      \"path\": \"относительный_путь/имя_файла.расширение\",\n"
                "      \"content\": \"полный код или содержимое файла (всегда пиши полный код целиком)\"\n"
                "    },\n"
                "    {\n"
                "      \"type\": \"file_read\",\n"
                "      \"path\": \"относительный_путь/имя_файла\"\n"
                "    },\n"
                "    {\n"
                "      \"type\": \"cmd\",\n"
                "      \"command\": \"powershell команда для тестирования или запуска\"\n"
                "    }\n"
                "  ],\n"
                "  \"to_user\": \"Только сугубо пользовательская информация о готовом результате (если задача полностью решена и проверена). Если в процессе — null\"\n"
                "}\n"
                "```\n\n"
                "ПРАВИЛА АВТОНОМНОЙ РАБОТЫ:\n"
                "1. Если пользователь просит создать файл (сценарий, код, html, документ и т.д.) — ОБЯЗАТЕЛЬНО используй действие `file_write` с полным кодом файла!\n"
                "2. Если требуется проверить работу — используй действие `cmd`.\n"
                "3. Когда все файлы созданы и проверены, сформируй красивый понятный итоговый ответ для пользователя в поле `to_user` (а поле `actions` оставь пустым `[]`)."
            )
        else:
            system_prefix = (
                f"Ты — Главный Архитектор и Руководитель проекта '{fresh_proj['name']}'.\n"
                f"Все агенты работают на настоящем компьютере Windows.\n"
                f"Основная рабочая папка проекта (Workspace Root): {project_root}\n"
                f"Описание проекта: {fresh_proj.get('description', '')}\n\n"
                f"Команда субагентов в подчинении:\n{subagents_context}\n\n"
                "ГЛАВНЫЕ ОБЯЗАННОСТИ РУКОВОДИТЕЛЯ:\n"
                "1. ДЕЛЕГИРОВАНИЕ: ТЫ САМ НЕ ПИШЕШЬ КОД/СЦЕНАРИИ ВРУЧНУЮ. Ты распределяешь задачи своим субагентам через `to_agent`.\n"
                "2. ОБЯЗАТЕЛЬНЫЙ АУДИТ ПОДЧИНЁННЫХ:\n"
                "   Никогда не верь подчинённым на слово! Подчинённый может написать «всё готово», но не сохранить файл или сделать ошибку.\n"
                "   Перед тем как отчитаться пользователю, ТЫ ОБЯЗАН ПРОВЕСТИ АУДИТ:\n"
                "   - Проверь отчёт системы: действительно ли файлы физически созданы/сохранены на диске через `file_write`?\n"
                "   - Если нужно — лично прочитай созданный файл через `file_read` или проверь консольной командой через `cmd`.\n"
                "   - Если подчинённый не выполнил задачу, не сохранил файл или допустил брак — ВЕРНИ ЗАДАЧУ СУБАГЕНТУ через `to_agent` с указанием конкретных замечаний!\n"
                "   - Принимай работу только тогда, когда лично убедился в её 100% готовности.\n\n"
                "3. СТРОЖАЙШЕЕ ПРАВИЛО ОБЩЕНИЯ С ПОЛЬЗОВАТЕЛЕМ (КРИТИЧЕСКИ ВАЖНО):\n"
                "   - НИКАКИХ СЛОВ О ШАГАХ, ИТЕРАЦИЯХ И ВНУТРЕННИХ ПРОЦЕССАХ!\n"
                "     Пользователь не должен знать о внутренней кухне. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНЫ фразы:\n"
                "     «Шаг 1/2 успешно завершён», «Все действия по предыдущему шагу выполнены», «Дополнительных действий специалистов не требуется», «Передаю задачу субагенту, ждите результат».\n"
                "   - ТОЛЬКО СУГУБО ПОЛЬЗОВАТЕЛЬСКАЯ ИНФОРМАЦИЯ В `to_user`:\n"
                "     Пиши только то, что полезно конечному пользователю: что сделано, какие фичи реализованы, как этим пользоваться (управление мышью/клавишами), какой файл открыть.\n"
                "   - Если задача ещё в процессе решения или ты проводишь аудит подчинённых — передавай `\"to_user\": null`.\n"
                "     Не беспокой пользователя промежуточными отписками, пиши ему только когда всё готово и проверено!\n\n"
                "4. ЯЗЫК МЫШЛЕНИЯ И ОТВЕТОВ (СТРОГО РУССКИЙ):\n"
                "   Все размышления (`thought`), поручения субагентам (`message`) и сообщения пользователю (`to_user`) должны быть ИСКЛЮЧИТЕЛЬНО НА РУССКОМ ЯЗЫКЕ.\n"
                "   Категорически запрещено переходить на английский язык (никаких 'I need to...', 'Let me...').\n\n"
                "5. ПРАВИЛО ИМЕНОВАНИЯ СУБАГЕНТОВ (СТРОГО ОБЯЗАТЕЛЬНО — ТОЛЬКО КОРОТКИЕ ИМЕНА):\n"
                "   - Имя субагента (`name` или `recipient`) ОБЯЗАНО БЫТЬ ОЧЕНЬ КОРОТКИМ: строго 1–2 слова (не более 15–20 символов)!\n"
                "   - Имя — это краткий позывной или специализация.\n"
                "   - ПРАВИЛЬНЫЕ примеры имён: 'Браузер', 'Playwright', 'Аудитор', 'Frontend', 'Тестировщик', '3D-моделлер', 'Парсер'.\n"
                "   - КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО писать в имя агента длинные фразы, перечислять стек библиотек в скобках или описывать задачи!\n"
                "   - НЕПРАВИЛЬНО: 'Разработчик браузерного модуля (Python, Playwright/Selenium)...' (это грубая ошибка!).\n"
                "   - Подробную специализацию пиши в поле 'role' (до 5–7 слов), а задачу — в 'message' или 'task'.\n\n"
                "ФОРМАТ ВЗАИМОДЕЙСТВИЯ (СТРОГО JSON):\n"
                "Отвечай строго в формате JSON в блоке ```json ... ``` следующей структуры:\n"
                "```json\n"
                "{\n"
                "  \"thought\": \"Твои краткие внутренние размышления по аудиту и руководству (не показываются пользователю в чате)\",\n"
                "  \"actions\": [\n"
                "    {\n"
                "      \"type\": \"to_agent\",\n"
                "      \"recipient\": \"КороткоеИмя (1-2 слова, например 'Браузер' или 'Аудитор')\",\n"
                "      \"message\": \"Конкретная задача или замечания по аудиту\"\n"
                "    },\n"
                "    {\n"
                "      \"type\": \"spawn_agent\",\n"
                "      \"name\": \"КороткоеИмя (1-2 слова, например 'Playwright' или 'Аудитор')\",\n"
                "      \"role\": \"Краткая роль (до 5 слов)\",\n"
                "      \"icon\": \"Эмодзи\",\n"
                "      \"task\": \"Стартовая задача\"\n"
                "    },\n"
                "    {\n"
                "      \"type\": \"file_read\",\n"
                "      \"path\": \"относительный_путь для проверки/аудита\"\n"
                "    },\n"
                "    {\n"
                "      \"type\": \"cmd\",\n"
                "      \"command\": \"powershell команда для тестирования/аудита\"\n"
                "    }\n"
                "  ],\n"
                "  \"to_user\": \"Только сугубо пользовательская информация о готовом результате (если задача полностью решена и проверена). Если в процессе — null\"\n"
                "}\n"
                "```\n\n"
                "ПРАВИЛА УПРАВЛЕНИЯ И ДЕЛЕГИРОВАНИЯ:\n"
                "1. Не выводи в чат пользователю внутреннюю работу — пиши в `to_user` только то, что адресовано пользователю.\n"
                "2. Для передачи задач субагентам используй action `to_agent`.\n"
                "3. Если подходящего специалиста еще нет — создай через action `spawn_agent`.\n"
                "4. ВАЖНО: Если пользователь просит создать файл (сценарий, код, документ, проект и т.д.) — "
                "поручи это субагенту через `to_agent`, ОБЯЗАТЕЛЬНО указав в инструкции субагенту, "
                "чтобы он сохранил файл на диск в директорию проекта с помощью действия `file_write`!\n"
                "5. Субагенты сами выполняют задачи в своих отдельных чатах и сохраняют файлы на диск в папку: {project_root}.\n"
                "6. Система автоматически передаст задачу субагенту, сохранит созданные им файлы на диск и вернет результат тебе.\n"
                "7. Когда все субагенты завершат задачи и аудит пройден, сформируй красивый и понятный структурированный итоговый ответ для пользователя в поле `to_user` (а поле `actions` оставь пустым `[]`)."
            )

        current_prompt = f"{system_prefix}\n\nЗадача пользователя: {user_prompt}"
        max_loop_steps = 30  # Unlimited autonomous multi-step loop
        all_accumulated_steps = []
        full_thinking_history = []
        last_clean_text = ""

        try:
            for loop_idx in range(1, max_loop_steps + 1):
                yield f"data: {json.dumps({'type': 'loop_step_start', 'step': loop_idx}, ensure_ascii=False)}\n\n"

                iter_thinking = []
                iter_text = []
                t_loop_start = time.time()

                stream = client.send_message(
                    chat_session_id=chat_id,
                    prompt=current_prompt,
                    stream=True,
                    thinking_enabled=thinking_enabled,
                )

                for chunk in stream:
                    if chunk["type"] == "thinking":
                        iter_thinking.append(chunk["content"])
                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                    elif chunk["type"] == "text":
                        iter_text.append(chunk["content"])

                raw_iter_ans = "".join(iter_text)
                iter_think_str = "".join(iter_thinking)
                parsed = parse_agent_response(raw_iter_ans)

                if iter_think_str:
                    full_thinking_history.append(iter_think_str)
                    think_dur = int(time.time() - t_loop_start)
                    thought_step = {
                        "category": "thought",
                        "title": f"Thought for {max(1, think_dur)}s",
                        "thought": iter_think_str,
                        "duration": f"{think_dur}s"
                    }
                    all_accumulated_steps.append(thought_step)
                    yield f"data: {json.dumps({'type': 'action_step', 'step': thought_step}, ensure_ascii=False)}\n\n"
                elif parsed.get("thought"):
                    thought_step = {
                        "category": "thought",
                        "title": "Thought process",
                        "thought": parsed["thought"]
                    }
                    all_accumulated_steps.append(thought_step)
                    yield f"data: {json.dumps({'type': 'action_step', 'step': thought_step}, ensure_ascii=False)}\n\n"

                actions = parsed.get("actions", [])
                has_directives = bool(actions)
                step_observations = []

                for act in actions:
                    a_type = act.get("type", "")

                    if a_type == "file_write":
                        path = act.get("path", "").strip()
                        content = act.get("content", "")
                        w_res = write_project_file(project_root, path, content)
                        file_step = {
                            "category": "file",
                            "title": f"Created file {path}",
                            "file_path": path,
                            "full_path": w_res.get("path", ""),
                            "size": w_res.get("size", 0),
                            "success": w_res.get("success", False),
                        }
                        all_accumulated_steps.append(file_step)
                        yield f"data: {json.dumps({'type': 'action_step', 'step': file_step}, ensure_ascii=False)}\n\n"
                        step_observations.append(f"[Файл '{path}' сохранен на диске ({w_res.get('size', 0)} байт)]")

                    elif a_type == "file_read":
                        path = act.get("path", "").strip()
                        r_res = read_project_file(project_root, path)
                        read_step = {
                            "category": "file_read",
                            "title": f"Read file {path}",
                            "file_path": path,
                            "success": r_res.get("success", False),
                            "output": r_res.get("content", r_res.get("error", "")),
                        }
                        all_accumulated_steps.append(read_step)
                        yield f"data: {json.dumps({'type': 'action_step', 'step': read_step}, ensure_ascii=False)}\n\n"
                        step_observations.append(f"[Содержимое файла '{path}']:\n{r_res.get('content', r_res.get('error', ''))}")

                    elif a_type == "cmd":
                        cmd_str = act.get("command", "").strip()
                        t_cmd_0 = time.time()
                        res_cmd = execute_shell_command(cmd_str, cwd=project_root)
                        cmd_dur = time.time() - t_cmd_0
                        cmd_step = {
                            "category": "cmd",
                            "title": f"Ran {cmd_str}",
                            "command": cmd_str,
                            "output": res_cmd["output"],
                            "code": res_cmd["code"],
                            "duration": f"{cmd_dur:.1f}s"
                        }
                        all_accumulated_steps.append(cmd_step)
                        yield f"data: {json.dumps({'type': 'action_step', 'step': cmd_step}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'terminal_cmd', 'sender': lead.get('name', 'Координатор'), 'command': cmd_str, 'output': res_cmd['output'], 'code': res_cmd['code']}, ensure_ascii=False)}\n\n"
                        step_observations.append(f"[Вывод команды `{cmd_str}` (код {res_cmd['code']})]:\n{res_cmd['output']}")

                    elif a_type == "spawn_agent":
                        s_name = act.get("name", "Субагент").strip()
                        s_role = act.get("role", "Исполнитель").strip()
                        s_icon = act.get("icon", "🤖").strip()
                        s_task = act.get("task", "").strip()
                        new_a = projects_manager.add_subagent(project_id, s_name, s_role, icon=s_icon)
                        if new_a:
                            yield f"data: {json.dumps({'type': 'agent_spawned', 'agent': new_a}, ensure_ascii=False)}\n\n"
                        actual_name = new_a.get("name", s_name) if new_a else s_name
                        actual_role = new_a.get("role", s_role) if new_a else s_role
                        actual_icon = new_a.get("icon", s_icon) if new_a else s_icon
                        spawn_step = {
                            "category": "spawn",
                            "title": f"Created agent {actual_icon} {actual_name}",
                            "name": actual_name,
                            "role": actual_role,
                            "icon": actual_icon,
                        }
                        all_accumulated_steps.append(spawn_step)
                        yield f"data: {json.dumps({'type': 'action_step', 'step': spawn_step}, ensure_ascii=False)}\n\n"
                        if new_a and s_task:
                            actions.append({
                                "type": "to_agent",
                                "recipient": actual_name,
                                "message": s_task
                            })

                    elif a_type in ("to_agent", "assign", "message_agent"):
                        a_name = act.get("recipient") or act.get("agent") or act.get("name", "")
                        a_task = act.get("message") or act.get("task") or ""
                        target_sub = projects_manager.find_subagent_by_name(project_id, a_name)
                        if not target_sub:
                            target_sub = projects_manager.add_subagent(project_id, a_name.strip(), "Исполнитель задачи")
                            if target_sub:
                                yield f"data: {json.dumps({'type': 'agent_spawned', 'agent': target_sub}, ensure_ascii=False)}\n\n"

                        sub_icon = target_sub.get("icon", "🤖")
                        sub_name = target_sub.get("name", "Субагент")
                        yield f"data: {json.dumps({'type': 'action_step_notify', 'message': f'Передаю задачу субагенту {sub_icon} {sub_name}...'}, ensure_ascii=False)}\n\n"

                        t_sub_0 = time.time()
                        sub_res = run_subagent_task_internal(project_id, target_sub["id"], a_task.strip(), thinking_enabled=thinking_enabled)
                        sub_dur = time.time() - t_sub_0

                        sub_step = {
                            "category": "subagent",
                            "title": f"Consulted {sub_icon} {target_sub['name']}",
                            "agent_id": target_sub["id"],
                            "agent_name": target_sub["name"],
                            "agent_icon": sub_icon,
                            "task": a_task.strip(),
                            "answer": sub_res.get("text", ""),
                            "duration": f"{sub_dur:.1f}s"
                        }
                        all_accumulated_steps.append(sub_step)
                        yield f"data: {json.dumps({'type': 'action_step', 'step': sub_step}, ensure_ascii=False)}\n\n"

                        created_files_names = []
                        for s_st in sub_res.get("steps", []):
                            if s_st.get("category") == "file":
                                created_files_names.append(s_st.get("file_path", ""))
                                all_accumulated_steps.append(s_st)
                                yield f"data: {json.dumps({'type': 'action_step', 'step': s_st}, ensure_ascii=False)}\n\n"
                            elif s_st.get("category") == "cmd":
                                all_accumulated_steps.append(s_st)
                                yield f"data: {json.dumps({'type': 'action_step', 'step': s_st}, ensure_ascii=False)}\n\n"
                            elif s_st.get("category") == "file_read":
                                all_accumulated_steps.append(s_st)
                                yield f"data: {json.dumps({'type': 'action_step', 'step': s_st}, ensure_ascii=False)}\n\n"

                        if created_files_names:
                            audit_obs = (
                                f"[ОТЧЁТ АУДИТА РУКОВОДИТЕЛЯ — УСПЕШНО]:\n"
                                f"Субагент {target_sub['name']} завершил задачу.\n"
                                f"Файлы физически сохранены на диске ({len(created_files_names)} шт.): {', '.join(created_files_names)}.\n"
                                f"Отчёт специалиста: {sub_res.get('text', '')}\n\n"
                                f"ИНСТРУКЦИЯ АУДИТОРУ:\n"
                                f"1. Проверь соответствие результата исходным требованиям пользователя.\n"
                                f"2. Если всё готово — сформулируй в поле `to_user` чисто пользовательское описание результата (что сделано и как пользоваться), а поле `actions` оставь пустым `[]`. НИКАКИХ СЛОВ О ШАГАХ!\n"
                                f"3. Если требуются доработки — укажи их субагенту через `to_agent`, а в `to_user` передай null."
                            )
                        else:
                            audit_obs = (
                                f"[ОТЧЁТ АУДИТА РУКОВОДИТЕЛЯ — ТРЕБУЕТСЯ ПРОВЕРКА]:\n"
                                f"Субагент {target_sub['name']} завершил ответ, однако на диске НЕ БЫЛО СОХРАНЕНО ни одного файла!\n"
                                f"Отчёт специалиста: {sub_res.get('text', '')}\n\n"
                                f"ИНСТРУКЦИЯ АУДИТОРУ:\n"
                                f"ВНИМАНИЕ! Если задача пользователя требовала создания или изменения файлов/кода — АУДИТ НЕ ПРОЙДЕН!\n"
                                f"Ты как Руководитель НЕ ДОЛЖЕН принимать такую работу. Отправь субагенту через `to_agent` строгое поручение внести изменения и сохранить файл через `file_write`.\n"
                                f"Поле `to_user` оставь null."
                            )
                        step_observations.append(audit_obs)

                # Check if Agent wants to finish (actions is empty)
                if not has_directives:
                    if parsed.get("to_user"):
                        sanitized_cand = sanitize_user_facing_text(parsed["to_user"])
                        if sanitized_cand:
                            last_clean_text = sanitized_cand
                            yield f"data: {json.dumps({'type': 'user_message_update', 'text': last_clean_text}, ensure_ascii=False)}\n\n"
                    has_subagent_run = any(s.get("category") == "subagent" for s in all_accumulated_steps)
                    has_file_writes = any(s.get("category") == "file" for s in all_accumulated_steps)
                    has_file_reads = any(s.get("category") == "file_read" for s in all_accumulated_steps)
                    first_agent_name = subagents[0]["name"] if subagents else "FrontendDev"

                    # SAFEGUARD 1: User requested an action/feature, but NO file written (and in multi-agent mode no subagent was called)!
                    is_action_task = any(w in user_prompt.lower() for w in [
                        "сделай", "создай", "добавь", "переделай", "напиши", "разработай", 
                        "реализуй", "построй", "покажи", "демонстрац", "исправь", "запрограммируй", "редуктор", "модел"
                    ])
                    if is_action_task and not has_file_writes and loop_idx < max_loop_steps:
                        if is_solo:
                            audit_fail_prompt = (
                                f"АКТУАЛЬНАЯ ЗАДАЧА ПОЛЬЗОВАТЕЛЯ:\n«{user_prompt}»\n\n"
                                "[ПРОВЕРКА ВЫПОЛНЕНИЯ — ЗАДАЧА ЕЩЁ НЕ ВЫПОЛНЕНА!]:\n"
                                f"Ты осмотрел директорию, но ещё НЕ СОЗДАЛ необходимые файлы для решения задачи «{user_prompt}»!\n"
                                "Файлы физически отсутствуют на диске. Ты НЕ МОЖЕШЬ рапортовать о готовности.\n"
                                "ТВОЁ ОБЯЗАТЕЛЬНОЕ ДЕЙСТВИЕ:\n"
                                "Напиши полный код решения и сохрани его на диск с помощью действия `file_write`!\n"
                                "Отвечай строго на русском языке в формате JSON с действием `file_write`:\n"
                                "```json\n"
                                "{\n"
                                f"  \"thought\": \"Создаю и сохраняю необходимый файл для выполнения задачи пользователя {user_prompt}\",\n"
                                "  \"actions\": [{\"type\": \"file_write\", \"path\": \"имя_файла.расширение\", \"content\": \"полный код/содержимое файла\"}],\n"
                                "  \"to_user\": null\n"
                                "}\n"
                                "```"
                            )
                            current_prompt = audit_fail_prompt
                            continue
                        elif not has_subagent_run:
                            audit_fail_prompt = (
                                f"АКТУАЛЬНАЯ ЗАДАЧА ПОЛЬЗОВАТЕЛЯ:\n«{user_prompt}»\n\n"
                                "[АУДИТ РУКОВОДИТЕЛЯ — ЗАДАЧА ЕЩЁ НЕ ВЫПОЛНЕНА!]:\n"
                                f"Ты выполнил команду осмотра, но ещё НЕ ПОРУЧИЛ реализацию задачи «{user_prompt}» ни одному специалисту!\n"
                                "Файлы для решения задачи ещё не созданы. Ты НЕ МОЖЕШЬ рапортовать о готовности.\n"
                                "ТВОЁ ОБЯЗАТЕЛЬНОЕ ДЕЙСТВИЕ:\n"
                                f"Немедленно поручи задачу субагенту {first_agent_name} через `to_agent`!\n"
                                "Отвечай строго на русском языке в формате JSON:\n"
                                "```json\n"
                                "{\n"
                                f"  \"thought\": \"Делегирую задачу специалисту {first_agent_name} с подробным ТЗ\",\n"
                                f"  \"actions\": [{{\"type\": \"to_agent\", \"recipient\": \"{first_agent_name}\", \"message\": \"Задача: {user_prompt}. Создай необходимый файл и обязательно сохрани его через file_write!\"}}],\n"
                                "  \"to_user\": null\n"
                                "}\n"
                                "```"
                            )
                            current_prompt = audit_fail_prompt
                            continue

                    # SAFEGUARD 2: If a subagent was consulted, read files, but never wrote any file:
                    if has_subagent_run and not has_file_writes and has_file_reads and loop_idx < max_loop_steps:
                        audit_fail_prompt = (
                            f"АКТУАЛЬНАЯ ЗАДАЧА ПОЛЬЗОВАТЕЛЯ:\n«{user_prompt}»\n\n"
                            "[АУДИТ РУКОВОДИТЕЛЯ — ТРЕБУЕТСЯ ДОРАБОТКА]:\n"
                            "Субагент прочитал файл, но не сохранил никаких изменений на диск!\n"
                            "Пользователь запросил изменения в проекте. Ты как Руководитель не можешь завершить задачу без сохранения файла.\n"
                            "Поручи субагенту через `to_agent` завершить работу и обязательно сохранить файл через `file_write`!\n"
                            "Отвечай строго на русском языке в формате JSON:\n"
                            "```json\n"
                            "{\n"
                            "  \"thought\": \"Поручаю субагенту внести изменения и сохранить файл\",\n"
                            f"  \"actions\": [{{\"type\": \"to_agent\", \"recipient\": \"{first_agent_name}\", \"message\": \"Внеси требуемые изменения по задаче '{user_prompt}' и обязательно сохрани файл через file_write\"}}],\n"
                            "  \"to_user\": null\n"
                            "}\n"
                            "```"
                        )
                        current_prompt = audit_fail_prompt
                        continue
                    break

                obs_text = "\n\n".join(step_observations) if step_observations else "Операции выполнены."
                if is_solo:
                    current_prompt = (
                        f"АКТУАЛЬНАЯ ЗАДАЧА ПОЛЬЗОВАТЕЛЯ:\n«{user_prompt}»\n\n"
                        f"[РЕЗУЛЬТАТЫ ВЫПОЛНЕНИЯ ВАШИХ ДЕЙСТВИЙ]:\n{obs_text}\n\n"
                        "ТВОЯ ЗАДАЧА КАК АВТОНОМНОГО ИНЖЕНЕРА:\n"
                        f"Оцени результаты выполнения действий по задаче: «{user_prompt}».\n"
                        "1. Если задача ещё не решена или файлы не созданы — продолжи выполнение через `actions` (`file_write`, `cmd`), а `to_user` укажи `null`.\n"
                        "2. Если всё готово и проверено — сформируй для пользователя красивый и понятный итоговый ответ в `to_user` (а `actions` оставь пустым `[]`).\n"
                        "СТРОЖАЙШЕ ЗАПРЕЩЕНО: писать в `to_user` промежуточные мысли вроде «Проверю файлы», «Мне нужно увидеть», «Давайте проверю». В `to_user` пиши ТОЛЬКО полезный готовый результат пользователю: что создано и как этим пользоваться!"
                    )
                else:
                    current_prompt = (
                        f"АКТУАЛЬНАЯ ЗАДАЧА ПОЛЬЗОВАТЕЛЯ:\n«{user_prompt}»\n\n"
                        f"[РЕЗУЛЬТАТЫ ДЕЙСТВИЙ И АУДИТ]:\n{obs_text}\n\n"
                        "ТВОЯ ЗАДАЧА КАК РУКОВОДИТЕЛЯ ПРОЕКТА:\n"
                        f"Проверь решение задачи: «{user_prompt}».\n"
                        "1. Если задача ещё не решена специалистом — поручи её через `actions` (`to_agent`), а `to_user` укажи `null`.\n"
                        "2. Если всё полностью готово и проверено — сформулируй для пользователя красивое описание готового результата в `to_user` (а `actions` оставь пустым `[]`).\n"
                        "СТРОЖАЙШЕ ЗАПРЕЩЕНО: писать в `to_user` промежуточные рассуждения («Проверю созданные файлы», «Выполню проверку»). В `to_user` пиши ТОЛЬКО конечный результат для пользователя: что сделано и как запускать!"
                    )

            # Loop finished
            created_files = [st for st in all_accumulated_steps if st.get("category") == "file" and st.get("success")]
            sanitized_final = sanitize_user_facing_text(last_clean_text)

            if created_files and (not sanitized_final or len(sanitized_final) < 20):
                files_list_str = "\n".join([f"• `{st.get('file_path')}`" for st in created_files])
                final_user_text = (
                    f"✅ **Все задачи успешно выполнены!**\n\n"
                    f"Созданы/обновлены файлы проекта ({len(created_files)} шт.):\n{files_list_str}\n\n"
                    f"Все файлы сохранены в рабочей папке: `{project_root}` и готовы к использованию."
                )
            else:
                final_user_text = sanitized_final or "Задача успешно выполнена командой проекта."
            full_thinking_joined = "\n\n".join(full_thinking_history)
            projects_manager.append_lead_message(
                project_id,
                "ASSISTANT",
                final_user_text,
                thinking=full_thinking_joined,
                steps=all_accumulated_steps,
                message_id=client._session_last_msg_ids.get(chat_id),
            )

            yield f"data: {json.dumps({'type': 'final_text', 'text': final_user_text, 'steps': all_accumulated_steps}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except (GeneratorExit, Exception) as e:
            if all_accumulated_steps or last_clean_text:
                interrupted_text = last_clean_text or "Выполнение было остановлено пользователем."
                try:
                    projects_manager.append_lead_message(
                        project_id,
                        "ASSISTANT",
                        interrupted_text,
                        thinking="\n\n".join(full_thinking_history),
                        steps=all_accumulated_steps,
                        message_id=client._session_last_msg_ids.get(chat_id),
                    )
                except Exception:
                    pass
            if isinstance(e, GeneratorExit):
                return
            err_data = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(err_data, ensure_ascii=False)}\n\n"

    return Response(generate_autonomous_sse(), mimetype="text/event-stream")


@app.route("/api/projects/<project_id>/agents/<agent_id>/execute", methods=["POST"])
def api_execute_agent_task(project_id, agent_id):
    """Executes a task autonomously using DeepSeek with the subagent's role persona in its own chat."""
    proj = projects_manager.get_project(project_id)
    if not proj:
        return jsonify({"success": False, "error": "Project not found"}), 404

    target_agent = None
    for a in proj.get("subagents", []):
        if a["id"] == agent_id:
            target_agent = a
            break

    if not target_agent:
        return jsonify({"success": False, "error": "Agent not found"}), 404

    task_desc = target_agent.get("current_task", "Выполни задачу")
    res = run_subagent_task_internal(project_id, agent_id, task_desc, thinking_enabled=True)
    return jsonify({
        "success": True,
        "agent_id": agent_id,
        "result": res.get("text", ""),
        "thinking": res.get("thinking", ""),
        "executed_commands": res.get("executed_commands", []),
        "steps": res.get("steps", [])
    })


if __name__ == "__main__":
    app.run(port=5000, debug=False)
