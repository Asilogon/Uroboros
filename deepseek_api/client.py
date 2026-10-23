import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

import requests

from .logger import TrafficLogger, default_logger
from .pow import PowSolver, default_pow_solver

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SESSION_FILE = DATA_DIR / "session.json"
BASE_URL = "https://chat.deepseek.com"


class DeepSeekAPIError(Exception):
    """Exception raised when DeepSeek API returns an error."""
    pass


class DeepSeekClient:
    """
    Unofficial Python API Client for DeepSeek Chat (chat.deepseek.com)
    Uses Python requests, authenticated with saved browser session/cookies.
    """

    def __init__(
        self,
        session_path: Optional[Union[str, Path]] = None,
        logger: Optional[TrafficLogger] = None,
        pow_solver: Optional[PowSolver] = None,
    ):
        self.session_path = Path(session_path) if session_path else SESSION_FILE
        self.logger = logger or default_logger
        self.pow_solver = pow_solver or default_pow_solver
        self.http = requests.Session()
        self.token: Optional[str] = None
        self.user_agent: str = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        )
        self.captured_headers: Dict[str, str] = {}
        self.load_session()

    def load_session(self, path: Optional[Union[str, Path]] = None) -> bool:
        """Loads cookies, auth tokens, and headers from session.json."""
        target_path = Path(path) if path else self.session_path
        if not target_path.exists():
            return False

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.token = data.get("token")
            if data.get("user_agent"):
                self.user_agent = data["user_agent"]

            self.captured_headers = data.get("captured_headers", {})

            # 1. Set Cookies
            cookies = data.get("cookies", [])
            for c in cookies:
                domain = c.get("domain", "chat.deepseek.com")
                # Remove leading dot if present for requests cookie jar compatibility
                if domain.startswith("."):
                    domain = domain[1:]
                self.http.cookies.set(
                    name=c["name"],
                    value=c["value"],
                    domain=domain,
                    path=c.get("path", "/"),
                )

            # 2. Base Headers
            self._update_default_headers()
            return True
        except Exception as e:
            print(f"[Client Warning] Failed loading session from {target_path}: {e}")
            return False

    def _update_default_headers(self):
        """Sets standard headers matching DeepSeek web client."""
        headers = {
            "Host": "chat.deepseek.com",
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Accept-Language": "ru,en;q=0.9",
            "x-client-platform": "web",
            "x-client-version": self.captured_headers.get("x-client-version", "1.0.0-always"),
            "x-app-version": self.captured_headers.get("x-app-version", "20241129.1"),
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self.http.headers.update(headers)

    def _log_request(self, method: str, url: str, headers: Dict, body: Any = None, files: Any = None) -> str:
        req_id = f"req_{int(time.time()*1000)%1000000}"
        file_info = None
        if files:
            file_info = []
            for k, v in files.items():
                fname = getattr(v, "name", str(v))
                file_info.append({"field": k, "name": fname})

        self.logger.log({
            "id": req_id,
            "kind": "requests_client_request",
            "method": method.upper(),
            "url": url,
            "headers": dict(headers),
            "body": body,
            "files": file_info,
        })
        return req_id

    def _log_response(self, req_id: str, method: str, url: str, resp: requests.Response, body: Any = None):
        self.logger.log({
            "id": req_id,
            "kind": "requests_client_response",
            "method": method.upper(),
            "url": url,
            "status": resp.status_code,
            "statusText": resp.reason,
            "headers": dict(resp.headers),
            "body": body,
        })

    def _request(
        self,
        method: str,
        path: str,
        json_data: Any = None,
        params: Any = None,
        files: Any = None,
        headers: Optional[Dict[str, str]] = None,
        stream: bool = False,
    ) -> requests.Response:
        url = f"{BASE_URL}{path}" if path.startswith("/") else path
        req_headers = dict(self.http.headers)
        if headers:
            req_headers.update(headers)

        req_id = self._log_request(method, url, req_headers, body=json_data, files=files)

        response = self.http.request(
            method=method,
            url=url,
            json=json_data,
            params=params,
            files=files,
            headers=req_headers,
            stream=stream,
            timeout=60,
        )

        if not stream:
            try:
                body_parsed = response.json()
            except Exception:
                body_parsed = response.text[:2000]
            self._log_response(req_id, method, url, response, body=body_parsed)
        else:
            self._log_response(req_id, method, url, response, body="[Streaming SSE Response]")

        return response

    def _ensure_pow_header(self, target_path: str = "/api/v0/chat/completion") -> Optional[str]:
        """Requests a PoW challenge from DeepSeek and computes the solution."""
        challenge_url = "/api/v0/chat/create_pow_challenge"
        try:
            resp = self._request("POST", challenge_url, json_data={"target_path": target_path})
            if resp.status_code == 200:
                data = resp.json()
                biz_data = data.get("data", {}).get("biz_data", {})
                challenge = biz_data.get("challenge")
                if challenge:
                    solved_header = self.pow_solver.solve_challenge(challenge, target_path=target_path)
                    return solved_header
        except Exception as e:
            print(f"[PoW Warning] Could not fetch/solve challenge: {e}")
        return None

    def get_user_info(self) -> Dict[str, Any]:
        """Fetches current user profile and session info."""
        resp = self._request("GET", "/api/v0/users/current")
        if resp.status_code != 200:
            raise DeepSeekAPIError(f"Failed to fetch user info: {resp.status_code} - {resp.text}")
        return resp.json()

    def create_chat(self, agent: str = "chat") -> str:
        """
        Creates a new chat session.
        Returns chat_session_id (UUID string).
        """
        payload = {"character_id": None}
        resp = self._request("POST", "/api/v0/chat_session/create", json_data=payload)
        data = resp.json()

        if data.get("code") != 0:
            raise DeepSeekAPIError(f"Error creating chat: {data.get('msg')} ({data})")

        chat_session_id = data["data"]["biz_data"]["id"]
        return chat_session_id

    def list_chats(self, page: int = 1, page_size: int = 30) -> List[Dict[str, Any]]:
        """
        Fetches list of existing chat sessions.
        """
        resp = self._request(
            "GET",
            "/api/v0/chat_session/fetch_page",
            params={"page": page, "page_size": page_size},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise DeepSeekAPIError(f"Error fetching chats: {data.get('msg')} ({data})")

        return data.get("data", {}).get("biz_data", {}).get("chat_sessions", [])

    def delete_chat(self, chat_session_id: str) -> bool:
        """
        Deletes a chat session by ID.
        """
        payload = {"chat_session_id": chat_session_id}
        resp = self._request("POST", "/api/v0/chat_session/delete", json_data=payload)
        data = resp.json()
        return data.get("code") == 0

    def get_chat_history(self, chat_session_id: str) -> List[Dict[str, Any]]:
        """
        Fetches messages in a specific chat session.
        """
        resp = self._request(
            "GET",
            "/api/v0/chat/history_messages",
            params={"chat_session_id": chat_session_id},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise DeepSeekAPIError(f"Error fetching history: {data.get('msg')} ({data})")

        return data.get("data", {}).get("biz_data", {}).get("chat_messages", [])

    def upload_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Uploads a file to DeepSeek file service.
        Returns file metadata dictionary including 'id'.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        filename = path.name
        with open(path, "rb") as f:
            files = {"file": (filename, f, "application/octet-stream")}
            resp = self._request(
                "POST",
                "/api/v0/file/upload",
                files=files,
            )

        data = resp.json()
        if data.get("code") != 0:
            raise DeepSeekAPIError(f"Error uploading file: {data.get('msg')} ({data})")

        file_biz = data.get("data", {}).get("biz_data", {})
        print(f"[Client] File uploaded: {filename} -> ID: {file_biz.get('id')}")
        return file_biz

    def send_message(
        self,
        chat_session_id: str,
        prompt: str,
        stream: bool = True,
        thinking_enabled: bool = False,
        search_enabled: bool = False,
        ref_file_ids: Optional[List[str]] = None,
        parent_message_id: Optional[str] = None,
    ) -> Union[Generator[Dict[str, Any], None, None], Dict[str, Any]]:
        """
        Sends a message to the chat.
        If stream=True, yields delta chunks:
          {"type": "text"|"thinking", "content": "..."}
        If stream=False, returns complete aggregated dict:
          {"text": "...", "thinking": "...", "full_response": {...}}
        """
        # 1. Prepare PoW header if needed
        pow_header = self._ensure_pow_header("/api/v0/chat/completion")
        extra_headers = {}
        if pow_header:
            extra_headers["x-ds-pow-response"] = pow_header

        payload = {
            "chat_session_id": chat_session_id,
            "parent_message_id": parent_message_id,
            "prompt": prompt,
            "ref_file_ids": ref_file_ids or [],
            "thinking_enabled": thinking_enabled,
            "search_enabled": search_enabled,
        }

        resp = self._request(
            "POST",
            "/api/v0/chat/completion",
            json_data=payload,
            headers=extra_headers,
            stream=True,
        )

        if resp.status_code != 200:
            raise DeepSeekAPIError(
                f"Completion error: HTTP {resp.status_code} - {resp.text}"
            )

        def event_stream_generator():
            full_text = []
            full_thinking = []

            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                line = line.strip()
                if line.startswith("data: "):
                    raw_data = line[6:].strip()
                    if raw_data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(raw_data)
                        choices = chunk.get("choices", [])
                        for choice in choices:
                            delta = choice.get("delta", {})
                            delta_type = delta.get("type", "text")
                            content = delta.get("content", "")

                            if content:
                                if delta_type == "thinking":
                                    full_thinking.append(content)
                                else:
                                    full_text.append(content)

                                yield {
                                    "type": delta_type,
                                    "content": content,
                                    "raw": chunk,
                                }
                    except json.JSONDecodeError:
                        continue

        if stream:
            return event_stream_generator()
        else:
            collected_text = []
            collected_thinking = []
            for item in event_stream_generator():
                if item["type"] == "thinking":
                    collected_thinking.append(item["content"])
                else:
                    collected_text.append(item["content"])

            return {
                "text": "".join(collected_text),
                "thinking": "".join(collected_thinking),
            }

    def stop_generation(self, chat_session_id: str, message_id: Optional[str] = None) -> bool:
        """Stops ongoing message generation."""
        payload = {"chat_session_id": chat_session_id}
        if message_id:
            payload["message_id"] = message_id
        resp = self._request("POST", "/api/v0/chat/stop_generate", json_data=payload)
        return resp.status_code == 200
