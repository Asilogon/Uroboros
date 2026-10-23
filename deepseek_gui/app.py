import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

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


@app.route("/")
def index():
    return render_template("index.html")


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


@app.route("/api/auth/start_selenium", methods=["POST"])
def api_start_selenium():
    global browser_instance, browser_thread

    if browser_thread and browser_thread.is_alive():
        return jsonify({"status": "running", "message": "Браузер уже запущен и ожидает входа."})

    def run_browser():
        global browser_instance
        try:
            browser_instance = DeepSeekBrowser(headless=False)
            browser_instance.open_deepseek()
            browser_instance.start_traffic_monitor(print_traffic=False)
            browser_instance.wait_for_user_login(timeout_seconds=600, interactive=False)
        finally:
            if browser_instance:
                browser_instance.close()
                browser_instance = None

    browser_thread = threading.Thread(target=run_browser, daemon=True)
    browser_thread.start()

    return jsonify({
        "status": "started",
        "message": "Браузер Chrome успешно открыт. Войдите в DeepSeek в окне браузера.",
    })


@app.route("/api/chats", methods=["GET"])
def api_get_chats():
    client = get_client()
    try:
        remote_chats = client.list_chats(page=1, page_size=30)
        formatted = []
        for c in remote_chats:
            formatted.append({
                "id": c.get("id"),
                "title": c.get("title") or "Новый диалог",
                "updated_at": c.get("updated_at") or "недавно",
            })
        if formatted:
            save_local_chats(formatted)
            return jsonify({"success": True, "chats": formatted})
    except Exception:
        pass

    # Return local clean chats list
    local_chats = load_local_chats()
    return jsonify({"success": True, "chats": local_chats})


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


@app.route("/api/chats/<chat_id>/message", methods=["POST"])
def api_send_message(chat_id):
    data = request.json or {}
    prompt = data.get("prompt", "")
    thinking_enabled = data.get("thinking_enabled", False)
    ref_file_ids = data.get("ref_file_ids", [])

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
                prompt=prompt,
                stream=True,
                thinking_enabled=thinking_enabled,
                ref_file_ids=ref_file_ids,
            )
            for chunk in stream:
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
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

    client = get_client()
    try:
        biz_info = client.upload_file(temp_path)
        return jsonify({
            "success": True,
            "id": biz_info.get("id"),
            "filename": f.filename,
            "size": temp_path.stat().st_size,
        })
    except Exception as e:
        file_id = f"file_{int(time.time()*1000)}"
        return jsonify({
            "success": True,
            "id": file_id,
            "filename": f.filename,
            "size": temp_path.stat().st_size,
            "offline_note": str(e),
        })


@app.route("/api/logs", methods=["GET"])
def api_get_logs():
    limit = int(request.args.get("limit", 30))
    entries = default_logger.get_recent_entries(limit=limit, api_only=False)
    return jsonify({"success": True, "logs": entries})


if __name__ == "__main__":
    app.run(port=5000, debug=False)
