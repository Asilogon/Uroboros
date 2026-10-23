import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
TRAFFIC_LOG_PATH = LOGS_DIR / "traffic.log"
JSONL_LOG_PATH = LOGS_DIR / "requests.jsonl"
FILES_DIR = LOGS_DIR / "files"


class TrafficLogger:
    """Manages logging of network requests, headers, bodies, responses, and files."""

    def __init__(self, logs_dir: Optional[Path] = None):
        self.logs_dir = Path(logs_dir) if logs_dir else LOGS_DIR
        self.traffic_log = self.logs_dir / "traffic.log"
        self.jsonl_log = self.logs_dir / "requests.jsonl"
        self.files_dir = self.logs_dir / "files"

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)

    def log(self, entry: Dict[str, Any], print_to_console: bool = False):
        """Record an intercepted request or response entry."""
        if not isinstance(entry, dict):
            return

        timestamp = entry.get("timestamp", datetime.now().isoformat())
        entry["logged_at"] = timestamp

        # 1. Append to JSONL for structured query
        try:
            with open(self.jsonl_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[Logger Error] Failed to write JSONL: {e}", file=sys.stderr)

        # 2. Append formatted entry to traffic.log
        try:
            formatted = self._format_entry(entry)
            with open(self.traffic_log, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
            if print_to_console:
                print(formatted)
        except Exception as e:
            print(f"[Logger Error] Failed to write traffic log: {e}", file=sys.stderr)

    def _format_entry(self, entry: Dict[str, Any]) -> str:
        kind = entry.get("kind", "event").upper()
        method = entry.get("method", "")
        url = entry.get("url", "")
        timestamp = entry.get("timestamp", "")
        req_id = entry.get("id", "")

        lines = [
            "=" * 80,
            f"[{timestamp}] [{kind}] {method} {url} (ID: {req_id})",
        ]

        if "headers" in entry and entry["headers"]:
            lines.append("--- Headers ---")
            for k, v in entry["headers"].items():
                # Obfuscate full tokens slightly in text log for safety, keeping first/last chars
                val_str = str(v)
                if k.lower() == "authorization" and len(val_str) > 25:
                    val_str = val_str[:15] + "..." + val_str[-8:]
                lines.append(f"  {k}: {val_str}")

        if "files" in entry and entry["files"]:
            lines.append("--- Attached Files ---")
            for f in entry["files"]:
                lines.append(
                    f"  File: {f.get('name')} | Size: {f.get('size')} bytes | Type: {f.get('type')}"
                )

        if "body" in entry and entry["body"] is not None:
            lines.append("--- Payload / Body ---")
            body = entry["body"]
            if isinstance(body, (dict, list)):
                try:
                    lines.append(json.dumps(body, indent=2, ensure_ascii=False))
                except Exception:
                    lines.append(str(body))
            else:
                lines.append(str(body))

        if "status" in entry:
            lines.append(
                f"--- Status: {entry.get('status')} {entry.get('statusText', '')} ---"
            )

        if "error" in entry:
            lines.append(f"--- Error: {entry['error']} ---")

        return "\n".join(lines)

    def get_recent_entries(
        self, limit: int = 20, api_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Retrieve recent log entries."""
        if not self.jsonl_log.exists():
            return []

        entries = []
        try:
            with open(self.jsonl_log, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    url = item.get("url", "")
                    if api_only and "/api/" not in url:
                        continue
                    entries.append(item)
                    if len(entries) >= limit:
                        break
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            print(f"[Logger Error] Reading logs: {e}", file=sys.stderr)

        return entries


# Default singleton instance
default_logger = TrafficLogger()
