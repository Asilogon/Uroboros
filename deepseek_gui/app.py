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

SESSION_FILE = ROOT_DIR / "data" / "session.json"
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def api_status():
    logged_in = False
    saved_at = None
    cookies_count = 0
    token = None

    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            token = data.get("token")
            cookies = data.get("cookies", [])
            cookies_count = len(cookies)
            saved_at = data.get("saved_at")
            if token or cookies_count > 0:
                logged_in = True
        except Exception:
            pass

    return jsonify({
        "logged_in": logged_in,
        "token_preview": (token[:12] + "...") if token else None,
        "cookies_count": cookies_count,
        "saved_at": saved_at,
    })


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
        chats = client.list_chats(page=1, page_size=20)
        return jsonify({"success": True, "chats": chats})
    except Exception as e:
        # Return friendly fallback sample list if not authenticated yet
        return jsonify({
            "success": False,
            "error": str(e),
            "chats": [
                {
                    "id": "sample-uroboros-1",
                    "title": "DeepSeek API Automation With Selenium",
                    "updated_at": "4m ago",
                    "project": "Uroboros",
                    "active": True
                },
                {
                    "id": "sample-haircuts-1",
                    "title": "Untitled Conversation",
                    "updated_at": "16h",
                    "project": "Haircuts",
                    "active": False
                },
                {
                    "id": "sample-evo-1",
                    "title": "Fixing Avito Parser And UI",
                    "updated_at": "19h",
                    "project": "EVO",
                    "active": False
                },
                {
                    "id": "sample-evo-2",
                    "title": "Архитектура и Дизайн Проекта",
                    "updated_at": "3d",
                    "project": "EVO",
                    "active": False
                }
            ]
        })


@app.route("/api/chats/new", methods=["POST"])
def api_new_chat():
    client = get_client()
    try:
        chat_id = client.create_chat()
        return jsonify({"success": True, "chat_id": chat_id})
    except Exception as e:
        # Fallback offline generated id
        offline_id = f"chat_{int(time.time())}"
        return jsonify({"success": False, "error": str(e), "chat_id": offline_id})


@app.route("/api/chats/<chat_id>", methods=["DELETE"])
def api_delete_chat(chat_id):
    client = get_client()
    try:
        success = client.delete_chat(chat_id)
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/chats/<chat_id>/message", methods=["POST"])
def api_send_message(chat_id):
    data = request.json or {}
    prompt = data.get("prompt", "")
    thinking_enabled = data.get("thinking_enabled", False)
    ref_file_ids = data.get("ref_file_ids", [])

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
        # Fallback file id for offline simulation if not logged in
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
