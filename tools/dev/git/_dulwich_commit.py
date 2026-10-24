"""Create a commit via dulwich (no git.exe required).

Usage (internal, called by the autonomous engineer):
    python tools/dev/git/_dulwich_commit.py

Stages all changes and creates a commit with the project convention message.
"""
import sys
from pathlib import Path

from dulwich import porcelain
from dulwich.repo import Repo

ROOT = Path(__file__).resolve().parents[3]
REPO = Repo(str(ROOT))

HEADER = "[0.1.0] Инструменты перенесены в tools"
BODY = """Подробные изменения:
- Создана папка tools/ с подкаталогами dev/, tests/, setup/.
- dev/patchers — все разовые патчеры (patch_*.py, fix_js_version_init.py, apply_version_patch.py).
- dev/diagnostics — find_red.py, find_red_clusters.py, verify_cleanup.py.
- dev/git — помощники коммитов (commit.py, commit.ps1, setup_git.ps1), amend_commit.py, commit_changes.py, restore_appjs.py, create_branch_deepseek.ps1, install_git_windows.md.
- tests — test_web_tool.py.
- setup — install_env.ps1.
- ROOT-пути в перенесённых Python-утилитах исправлены на parents[N] под новую глубину вложенности.
- Добавлен tools/README.md с описанием назначения каждой утилиты.
- Удалена устаревшая папка scripts/, файл clear_out.log.
- VERSION повышен до 0.1.0."""
MESSAGE = (HEADER + "\n\n" + BODY).encode("utf-8")

# Stage everything, respecting .gitignore
porcelain.add(REPO, paths=None)

# Commit
commit_id = porcelain.commit(
    REPO,
    message=MESSAGE,
)
print("Commit created:", commit_id.decode())
print()
print("=== Last commit ===")
print(HEADER)
print()
print(BODY)
