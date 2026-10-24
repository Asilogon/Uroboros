"""Restore deepseek_gui/static/js/app.js from git HEAD (via dulwich)."""
from pathlib import Path
from dulwich.repo import Repo

ROOT = Path(__file__).resolve().parent
repo = Repo(str(ROOT))

head = repo.head()
commit = repo[head]
tree = repo[commit.tree]
print(f'[HEAD] {head.decode()}')

# Walk tree to find deepseek_gui/static/js/app.js
path_parts = ['deepseek_gui', 'static', 'js', 'app.js']
node = tree
for part in path_parts:
    entries = node.items()
    found = None
    for name, mode, sha in entries:
        if name.decode() == part:
            found = sha
            break
    if found is None:
        raise SystemExit(f'Not found in HEAD tree: {part} at {path_parts}')
    obj = repo[found]
    if part == path_parts[-1]:
        blob_data = obj.data
    else:
        node = obj

out_path = ROOT / 'deepseek_gui' / 'static' / 'js' / 'app.js'
out_path.write_bytes(blob_data)
print(f'[RESTORED] {out_path} ({len(blob_data)} bytes)')
