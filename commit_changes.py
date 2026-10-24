"""Commit all tracked changes in the Uroboros repo using dulwich (no git.exe needed)."""
import sys
from pathlib import Path

from dulwich import porcelain
from dulwich.repo import Repo

ROOT = Path(__file__).resolve().parent

NAME = 'Uroboros Bot'
EMAIL = 'uroboros-bot@local'
MESSAGE = sys.argv[1] if len(sys.argv) > 1 else 'chore: bump version and add web tool'

repo = Repo(str(ROOT))

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

# 3. Stage the files we changed/created
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
    'patch_web_tool.py',
    'patch_web_js.py',
    'patch_web_js2.py',
    'restore_appjs.py',
    'test_web_tool.py',
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
