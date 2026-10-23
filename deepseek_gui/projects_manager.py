"""
Projects & Multi-Agent Management Module for Uroboros
Strict, clean project hierarchy with Lead Agent orchestration and Subagents.
"""
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
PROJECTS_FILE = DATA_DIR / "projects.json"
LOGS_DIR = DATA_DIR / "logs"


def get_default_projects() -> List[Dict[str, Any]]:
    # Start clean from scratch with no pre-populated mock projects
    return []


STOP_WORDS = {'и', 'в', 'на', 'с', 'по', 'для', 'о', 'об', 'от', 'к', 'из', 'у', 'за', 'под', 'над', 'при'}
GENERIC_TITLES = {'разработчик', 'специалист', 'инженер', 'эксперт', 'агент', 'мастер', 'создатель', 'автор'}


def sanitize_agent_name(name: str, max_words: int = 3, max_len: int = 30) -> str:
    """Enforces very short, clean names for subagents (1-3 words, max 30 chars)."""
    if not name or not name.strip():
        return "Субагент"

    raw = name.strip('\'"` \t\r\n')
    # Remove leading emoji/symbols
    raw = re.sub(r'^[^\w\sа-яА-ЯёЁ]+', '', raw).strip()

    # Cut at parentheses or brackets: "Разработчик (Python)" -> "Разработчик"
    clean = re.split(r'[\(\[\{]', raw)[0].strip()

    # If empty before parenthesis (e.g. "(Playwright Dev)"), look inside
    if not clean:
        m_par = re.search(r'[\(\[]([^\)\]]+)[\)\]]', raw)
        if m_par:
            clean = m_par.group(1).strip()

    # Cut at separators like comma, dash, colon, semicolon, slash, pipe
    clean = re.split(r'[,;:|/\\—–]|(?:\s+-\s+)', clean)[0].strip()

    # Cut at introductory conjunctions / verbs
    clean = re.split(r'(?i)\s+(?:который|которая|которое|которые|созда[её]т|делает|пишет|отвечает|для|по|с\s+целью)\b', clean)[0].strip()

    words = clean.split()
    if not words:
        return "Субагент"

    # If phrase starts with generic title + adjective + noun:
    # e.g. "Разработчик браузерного модуля" -> "Браузерный модуль"
    if len(words) >= 3 and words[0].lower() in GENERIC_TITLES:
        w1 = words[1].lower()
        if w1.endswith('ого') and len(w1) > 4:
            adj = words[1][:-3] + 'ый'
            noun = words[2]
            if noun.lower().endswith('я') and len(noun) > 2:
                noun = noun[:-1] + 'ь'
            words = [adj.capitalize(), noun]
        elif w1.endswith('его') and len(w1) > 4:
            adj = words[1][:-3] + 'ий'
            noun = words[2]
            if noun.lower().endswith('я') and len(noun) > 2:
                noun = noun[:-1] + 'ь'
            words = [adj.capitalize(), noun]

    selected = words[:max_words] if len(words) > max_words else words

    # Strip trailing stop words (e.g. "Тестировщик API и" -> "Тестировщик API")
    while selected and selected[-1].lower() in STOP_WORDS:
        selected.pop()

    res = ' '.join(selected)

    # If longer than max_len, trim words
    if len(res) > max_len:
        while len(res) > max_len and len(selected) > 1:
            selected.pop()
            while selected and selected[-1].lower() in STOP_WORDS:
                selected.pop()
            res = ' '.join(selected)
        if len(res) > max_len:
            res = res[:max_len].strip()

    res = res.strip('.,;:-_()[]{} ')
    return res or "Субагент"


def get_default_agent_icon(name: str = "", role: str = "") -> str:
    """Smart heuristic to assign a thematic emoji icon based on subagent name and role."""
    text = f"{name} {role}".lower()
    if any(w in text for w in ["браузер", "browser", "playwright", "selenium", "chrome", "web"]):
        return "🌐"
    if any(w in text for w in ["аудит", "audit", "инспект", "контрол", "проверк"]):
        return "📋"
    if any(w in text for w in ["реверс", "reverse", "сеть", "трафик", "инспектор", "протокол"]):
        return "⚡"
    if any(w in text for w in ["парсер", "parser", "скрейпер", "парс", "crawl", "сбор"]):
        return "🕷️"
    if any(w in text for w in ["бэкенд", "backend", "сервер", "api", "база", "db", "sql"]):
        return "💻"
    if any(w in text for w in ["тест", "qa", "test", "капч", "валидац"]):
        return "🔍"
    if any(w in text for w in ["защит", "безопасн", "security", "waf", "шифр"]):
        return "🛡️"
    if any(w in text for w in ["фронт", "дизайн", "ui", "gui", "интерфейс"]):
        return "🎨"
    if any(w in text for w in ["данн", "data", "аналит", "статистик"]):
        return "📊"
    if any(w in text for w in ["архитект", "лид", "lead", "стратег"]):
        return "🧠"
    if any(w in text for w in ["оптимиз", "ускорен", "perf", "speed"]):
        return "🚀"
    return "🤖"


class ProjectsManager:
    def __init__(self, filepath: Optional[Path] = None):
        self.filepath = filepath or PROJECTS_FILE
        self._ensure_init()

    def _ensure_init(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not self.filepath.exists():
            self.save_all([])

    def load_all(self) -> List[Dict[str, Any]]:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save_all(self, projects: List[Dict[str, Any]]):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(projects, f, indent=2, ensure_ascii=False)

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        projects = self.load_all()
        for p in projects:
            if p["id"] == project_id:
                if not p.get("root_path"):
                    p["root_path"] = str(ROOT_DIR)
                return p
        return None

    def create_project(self, name: str, description: str = "", icon: str = "", root_path: str = "", mode: str = "multi", *args, **kwargs) -> Dict[str, Any]:
        projects = self.load_all()
        new_id = f"proj_{int(time.time()*1000)%1000000}"
        clean_name = name.strip() or "Новый проект"
        clean_root = root_path.strip() if root_path and root_path.strip() else str(ROOT_DIR)
        try:
            clean_root = str(Path(clean_root).resolve())
        except Exception:
            pass

        is_solo = (mode == "solo")
        lead_name = f"Агент ({clean_name})" if is_solo else f"Руководитель ({clean_name})"
        lead_role = "Автономный инженер (всё делает самостоятельно)" if is_solo else "Архитектор и координатор субагентов"
        lead_icon = "⚡" if is_solo else "🧠"

        new_project = {
            "id": new_id,
            "name": clean_name,
            "mode": "solo" if is_solo else "multi",
            "description": description.strip(),
            "root_path": clean_root,
            "icon": icon.strip() or ("⚡" if is_solo else "📁"),
            "status": "active",
            "created_at": time.strftime("%Y-%m-%d"),
            "lead_agent": {
                "id": f"lead_{new_id}",
                "name": lead_name,
                "role": lead_role,
                "icon": lead_icon,
                "model": "DeepSeek-V3",
                "status": "active",
                "chat_session_id": None,
                "history": [],
            },
            "subagents": [],
            "tasks": [],
        }
        projects.insert(0, new_project)
        self.save_all(projects)
        return new_project

    def delete_project(self, project_id: str) -> bool:
        projects = self.load_all()
        filtered = [p for p in projects if p["id"] != project_id]
        if len(filtered) != len(projects):
            self.save_all(filtered)
            # Delete project logs folder on project deletion
            proj_log_dir = LOGS_DIR / project_id
            if proj_log_dir.exists():
                shutil.rmtree(proj_log_dir, ignore_errors=True)
            return True
        return False

    def add_subagent(
        self,
        project_id: str,
        name: str,
        role: str,
        system_prompt: str = "",
        color: str = "#3b82f6",
        icon: str = "",
        *args,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        projects = self.load_all()
        for p in projects:
            if p["id"] == project_id:
                agent_id = f"subagent_{int(time.time()*1000)%1000000}"
                clean_name = sanitize_agent_name(name)
                # If name was long and provided details while role is default/generic, save those details to role
                if (not role or role.strip() in ("Исполнитель", "Исполнитель задач", "Исполнитель задачи", "Специалист")) and name.strip() != clean_name:
                    clean_role = name.strip().split('\n')[0][:80]
                    role = clean_role
                clean_icon = icon.strip() if icon and icon.strip() else get_default_agent_icon(clean_name, role)
                new_agent = {
                    "id": agent_id,
                    "name": clean_name,
                    "role": role.strip(),
                    "icon": clean_icon,
                    "color": color,
                    "system_prompt": system_prompt.strip() or f"Ты — {clean_name}, выполняешь роль: {role}.",
                    "status": "idle",
                    "current_task": "Ожидает назначения задачи",
                    "progress": 0,
                    "chat_session_id": None,
                    "history": [],
                }
                p.setdefault("subagents", []).append(new_agent)
                self.save_all(projects)
                return new_agent
        return None

    def remove_subagent(self, project_id: str, agent_id: str) -> bool:
        projects = self.load_all()
        for p in projects:
            if p["id"] == project_id:
                p["subagents"] = [a for a in p.get("subagents", []) if a["id"] != agent_id]
                self.save_all(projects)
                # Remove specific agent log file if exists
                proj_log_dir = LOGS_DIR / project_id
                if proj_log_dir.exists():
                    for f in proj_log_dir.glob(f"*{agent_id}*"):
                        try:
                            f.unlink()
                        except Exception:
                            pass
                return True
        return False

    def update_agent_task(
        self,
        project_id: str,
        agent_id: str,
        task: str,
        status: str = "working",
        progress: int = 50,
    ) -> bool:
        projects = self.load_all()
        for p in projects:
            if p["id"] == project_id:
                for a in p.get("subagents", []):
                    if a["id"] == agent_id:
                        a["current_task"] = task
                        a["status"] = status
                        a["progress"] = progress
                        existing = [t for t in p.get("tasks", []) if t.get("title") == task and t.get("agent_id") == agent_id]
                        if not existing:
                            p.setdefault("tasks", []).append({
                                "id": f"t_{int(time.time()*1000)%100000}",
                                "agent_id": agent_id,
                                "title": task,
                                "status": "active" if status == "working" else "completed",
                            })
                        self.save_all(projects)
                        return True
        return False

    def get_subagent(self, project_id: str, agent_id: str) -> Optional[Dict[str, Any]]:
        p = self.get_project(project_id)
        if not p:
            return None
        for a in p.get("subagents", []):
            if a["id"] == agent_id:
                return a
        return None

    def find_subagent_by_name(self, project_id: str, query: str) -> Optional[Dict[str, Any]]:
        p = self.get_project(project_id)
        if not p:
            return None
        q = query.strip().lower()
        subagents = p.get("subagents", [])
        
        # 1. Exact match or ID match
        for a in subagents:
            a_name = a["name"].lower()
            if a_name == q or a["id"].lower() == q:
                return a
                
        # 2. Direct substring match (either query in name or name in query)
        for a in subagents:
            a_name = a["name"].lower()
            if q in a_name or a_name in q:
                return a
                
        # 3. Clean sanitized query match
        clean_q = sanitize_agent_name(query).lower()
        for a in subagents:
            a_name = a["name"].lower()
            if clean_q == a_name or clean_q in a_name or a_name in clean_q:
                return a

        # 4. Role match
        for a in subagents:
            a_role = a.get("role", "").lower()
            if q in a_role or a_role in q or clean_q in a_role:
                return a

        # 5. Meaningful keyword overlap
        q_words = {w for w in re.findall(r'\w+', q) if len(w) >= 3 and w not in STOP_WORDS}
        for a in subagents:
            a_words = {w for w in re.findall(r'\w+', a["name"].lower() + " " + a.get("role", "").lower()) if len(w) >= 3 and w not in STOP_WORDS}
            if q_words & a_words:
                return a

        return None

    def _write_agent_log(
        self,
        project_id: str,
        filename: str,
        role: str,
        text: str,
        thinking: str = "",
        steps: Optional[List[Dict[str, Any]]] = None,
    ):
        """Appends formatted message log for a specific agent in data/logs/<project_id>/."""
        try:
            proj_log_dir = LOGS_DIR / project_id
            proj_log_dir.mkdir(parents=True, exist_ok=True)
            log_path = proj_log_dir / filename

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            lines = [
                f"\n{'='*70}",
                f"[{timestamp}] [{role}]",
            ]
            if thinking and thinking.strip():
                lines.append(f"\n[РАЗМЫШЛЕНИЯ]:\n{thinking.strip()}")
            if steps:
                lines.append("\n[ДЕЙСТВИЯ]:")
                for s in steps:
                    cat = s.get("category", "action")
                    title = s.get("title", "")
                    lines.append(f"  • [{cat}] {title}")
            lines.append(f"\n[СООБЩЕНИЕ]:\n{text.strip()}\n")

            with open(log_path, "a", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as e:
            print(f"Error writing agent log {filename}: {e}")

    def append_lead_message(self, project_id: str, role: str, text: str, thinking: str = "", steps: Optional[List[Dict[str, Any]]] = None, message_id: Optional[int] = None):
        projects = self.load_all()
        for p in projects:
            if p["id"] == project_id:
                if message_id is not None:
                    p["lead_agent"]["last_message_id"] = message_id
                p["lead_agent"].setdefault("history", []).append({
                    "role": role,
                    "text": text,
                    "thinking": thinking,
                    "steps": steps or [],
                    "time": time.strftime("%H:%M"),
                })
                self.save_all(projects)
                self._write_agent_log(project_id, "lead_agent.log", role, text, thinking, steps)
                return

    def append_subagent_message(self, project_id: str, agent_id: str, role: str, text: str, thinking: str = "", steps: Optional[List[Dict[str, Any]]] = None, message_id: Optional[int] = None):
        projects = self.load_all()
        for p in projects:
            if p["id"] == project_id:
                for a in p.get("subagents", []):
                    if a["id"] == agent_id:
                        if message_id is not None:
                            a["last_message_id"] = message_id
                        a.setdefault("history", []).append({
                            "role": role,
                            "text": text,
                            "thinking": thinking,
                            "steps": steps or [],
                            "time": time.strftime("%H:%M"),
                        })
                        self.save_all(projects)
                        safe_name = re.sub(r'[^a-zA-Zа-яА-Я0-9_-]', '_', a.get("name", "subagent")).strip('_') or "subagent"
                        filename = f"{safe_name}_{agent_id}.log"
                        self._write_agent_log(project_id, filename, role, text, thinking, steps)
                        return

    def set_subagent_chat_session(self, project_id: str, agent_id: str, chat_session_id: str):
        projects = self.load_all()
        for p in projects:
            if p["id"] == project_id:
                for a in p.get("subagents", []):
                    if a["id"] == agent_id:
                        a["chat_session_id"] = chat_session_id
                        self.save_all(projects)
                        return


projects_manager = ProjectsManager()
