"""Commit all tracked changes in the Uroboros repo using dulwich (no git.exe needed)."""
import os
import sys
from pathlib import Path

from dulwich import porcelain
from dulwich.repo import Repo
from dulwich.objects import Commit

ROOT = Path(__file__).resolve().parent

NAME = 'Uroboros Bot'
EMAIL = 'uroboros-bot@local'
MESSAGE = sys.argv[1] if len(sys.argv) > 1 else 'chore: add app version badge (v0.0.1)'

repo_path = str(ROOT)
repo = Repo(repo_path)

# 1. Ensure user identity in config
cfg = repo.get_config()
try:
    cfg.set((b'user',), b'name', NAME.encode())
    cfg.set((b'user',), b'email', EMAIL.encode())
    cfg.write_to_path()
    print(f'[CONFIG] user.name={NAME!r}, user.email={EMAIL!r}')
except Exception as e:
    print(f'[WARN] could not write config: {e}')

# 2. Report current HEAD
head = repo.head()
print(f'[HEAD] {head.decode()}')

# Try to find feature/deepseek branch ref
refs = repo.get_refs()
print(f'[REFS] {sorted(k.decode() for k in refs.keys())}')

# 3. Stage all changes (porcelain.add respects .gitignore)
# We'll add specific files explicitly to be safe, plus report status
status = porcelain.status(repo)
print(f'[STATUS] staged={len(status.staged.get("add", []))} untracked={len(status.untracked)} unstaged={len(status.unstaged)}')
print(f'[STATUS] untracked files: {status.untracked[:20]}')
print(f'[STATUS] unstaged files: {status.unstaged[:20]}')

# Explicitly add the files we changed/created
files_to_add = [
    'VERSION',
    'deepseek_gui/version.py',
    'deepseek_gui/app.py',
    'deepseek_gui/templates/index.html',
    'deepseek_gui/static/css/style.css',
    'deepseek_gui/static/js/app.js',
    'create_branch_deepseek.ps1',
    'README_branch_deepseek.md',
    'apply_version_patch.py',
    'fix_js_version_init.py',
    'commit_changes.py',
]

for f in files_to_add:
    p = ROOT / f
    if p.exists():
        porcelain.add(repo, paths=[f])
        print(f'[ADD] {f}')
    else:
        print(f'[SKIP missing] {f}')

# 4. Commit
commit_sha = porcelain.commit(
    repo,
    message=MESSAGE.encode('utf-8'),
    author=f'{NAME} <{EMAIL}>'.encode(),
    committer=f'{NAME} <{EMAIL}>'.encode(),
)
print(f'[COMMIT] {commit_sha.decode()}')

# 5. Show new HEAD
print(f'[HEAD-AFTER] {repo.head().decode()}')
print('Done.')
