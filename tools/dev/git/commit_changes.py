"""Commit all tracked changes in the Uroboros repo using dulwich.

Format: [X.X.X] Суть изменения\n\n<описание>\n"""
import sys
from pathlib import Path

from dulwich import porcelain
from dulwich.repo import Repo

ROOT = Path(__file__).resolve().parents[3]

NAME = 'Uroboros Bot'
EMAIL = 'uroboros-bot@local'

version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()

short_summary = sys.argv[1] if len(sys.argv) > 1 else 'Изменения'
description = sys.argv[2] if len(sys.argv) > 2 else ''

files_to_add = [
    'VERSION',
    'deepseek_gui/version.py',
    'deepseek_gui/web_tool.py',
    'deepseek_gui/app.py',
    'deepseek_gui/templates/index.html',
    'deepseek_gui/static/css/style.css',
    'deepseek_gui/static/js/app.js',
    'create_branch_deepseek.ps1',
    'README_branch_deepseek.md',
    'apply_version_patch.py',
    'fix_js_version_init.py',
    'commit_changes.py',
    'amend_commit.py',
    'COMMIT_CONVENTION.md',
    'patch_web_tool.py',
    'patch_web_js.py',
    'patch_web_js2.py',
    'restore_appjs.py',
    'test_web_tool.py',
    'patch_top_agents.py',
    'patch_top_agents_js.py',
    'patch_remove_top_agents.py',
    'find_red.py',
    'find_red_clusters.py',
    'verify_cleanup.py',
]

header = f'[{version}] {short_summary}'
body = description if description else f'Версия {version}.'
files_block = 'Files:\n' + '\n'.join(f'- {f}' for f in files_to_add if (ROOT / f).exists())
message = f'{header}\n\n{body}\n\nVersion: {version}\n{files_block}'

print('=' * 60)
print('COMMIT MESSAGE:')
print('=' * 60)
print(message)
print('=' * 60)

repo = Repo(str(ROOT))
cfg = repo.get_config()
try:
    cfg.set((b'user',), b'name', NAME.encode())
    cfg.set((b'user',), b'email', EMAIL.encode())
    cfg.write_to_path()
except Exception as e:
    print(f'[WARN] could not write config: {e}')

print(f'[HEAD-BEFORE] {repo.head().decode()}')

for f in files_to_add:
    p = ROOT / f
    if p.exists():
        porcelain.add(repo, paths=[f])
        print(f'[ADD] {f}')
    else:
        print(f'[SKIP missing] {f}')

commit_sha = porcelain.commit(
    repo,
    message=message.encode('utf-8'),
    author=f'{NAME} <{EMAIL}>'.encode(),
    committer=f'{NAME} <{EMAIL}>'.encode(),
)
print(f'[COMMIT] {commit_sha.decode()}')
print(f'[HEAD-AFTER] {repo.head().decode()}')
print('Done.')
