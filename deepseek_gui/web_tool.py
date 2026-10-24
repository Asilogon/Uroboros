"""Web fetch tool for Uroboros agents.

Allows agents to open web pages, read their content, and download data files
to the project workspace.
"""
from __future__ import annotations

import html
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import requests

DEFAULT_TIMEOUT = 20
MAX_PREVIEW_CHARS = 8000
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 UroborosAgent/0.0.1"
)


def _strip_html_to_text(raw: str) -> str:
    """Very light HTML -> text conversion (no external deps)."""
    # Remove scripts/styles
    raw = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<style[\s\S]*?</style>", " ", raw, flags=re.IGNORECASE)
    # Replace <br>/<p>/<div> with newlines
    raw = re.sub(r"<\s*(br|p|div|li|tr|h[1-6])\s*/?\s*>", "\n", raw, flags=re.IGNORECASE)
    # Strip all other tags
    raw = re.sub(r"<[^>]+>", " ", raw)
    # Decode entities
    raw = html.unescape(raw)
    # Collapse whitespace
    raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
    raw = re.sub(r"\n\s*\n+", "\n\n", raw)
    return raw.strip()


def _looks_like_html(content_type: str, body: bytes) -> bool:
    if "html" in content_type.lower() or "xml" in content_type.lower():
        return True
    head = body[:512].lower()
    return b"<html" in head or b"<!doctype" in head


def _safe_project_path(project_root: str, rel_path: str) -> Path:
    root = Path(project_root).resolve()
    target = (root / rel_path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError(f"Path escapes project root: {rel_path}")
    return target


def web_fetch(
    url: str,
    save_path: Optional[str] = None,
    project_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch a URL and return its content.

    Args:
        url: Target URL (must be http/https).
        save_path: Optional relative path inside project_root to save the raw body.
        project_root: Project root dir. If provided together with save_path, saves the file.

    Returns:
        Dict with keys: success, url, status_code, content_type, size, preview, saved_path,
        error (optional), final_url.
    """
    url = (url or "").strip()
    if not url:
        return {"success": False, "error": "Empty URL", "url": url}
    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        return {"success": False, "error": "URL must start with http:// or https://", "url": url}

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True,
        )
    except requests.RequestException as e:
        return {"success": False, "error": f"Network error: {e}", "url": url}

    body = resp.content or b""
    content_type = resp.headers.get("Content-Type", "") or ""
    size = len(body)

    # Save if requested
    saved_path = None
    save_error = None
    if save_path:
        if not project_root:
            save_error = "project_root not provided; cannot save file"
        else:
            try:
                target = _safe_project_path(project_root, save_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "wb") as f:
                    f.write(body)
                saved_path = str(target.relative_to(Path(project_root).resolve()))
            except Exception as e:
                save_error = f"Save error: {e}"

    # Build text preview
    is_html = _looks_like_html(content_type, body)
    if is_html:
        try:
            raw_text = body.decode(resp.encoding or "utf-8", errors="replace")
        except Exception:
            raw_text = body.decode("utf-8", errors="replace")
        text = _strip_html_to_text(raw_text)
    else:
        if content_type and not content_type.startswith(("text/", "application/json", "application/javascript", "application/xml")):
            text = f"[binary content: {content_type}, {size} bytes]"
        else:
            try:
                text = body.decode(resp.encoding or "utf-8", errors="replace")
            except Exception:
                text = body.decode("utf-8", errors="replace")

    preview = text[:MAX_PREVIEW_CHARS]

    result: Dict[str, Any] = {
        "success": resp.status_code < 400,
        "url": url,
        "final_url": resp.url,
        "status_code": resp.status_code,
        "content_type": content_type,
        "size": size,
        "preview": preview,
        "saved_path": saved_path,
    }
    if save_error:
        result["save_error"] = save_error
    if resp.status_code >= 400:
        result["error"] = f"HTTP {resp.status_code}"
    return result
