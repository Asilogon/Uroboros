"""Compare current app.js with version in git HEAD (via dulwich)."""
from pathlib import Path
from dulwich.repo import Repo

ROOT = Path(__file__).resolve().parents[3]
REPO = Repo(str(ROOT))
head = REPO.head()
commit = REPO[head]

path_parts = ['deepseek_gui', 'static', 'js', 'app.js']
node = commit.tree
for part in path_parts:
    found = None
    for name, mode, sha in node.items():
        if name.decode() == part:
            found = sha
            break
    if found is None:
        print('PATH NOT IN HEAD:', part)
        raise SystemExit(1)
    node = REPO[found] if not hasattr(found, 'items') else found

# The last sha is blob
blob = REPO[found] if not hasattr(found, 'items') else None
# Simpler: use object_store.get_blob
blob = REPO.object_store[found]
head_src = blob.data.decode('utf-8', 'replace')
cur_src = (ROOT / 'deepseek_gui' / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')

print(f'HEAD size: {len(head_src)}, current size: {len(cur_src)}')

import difflib
diff = list(difflib.unified_diff(
    head_src.splitlines(keepends=True),
    cur_src.splitlines(keepends=True),
    fromfile='HEAD:app.js',
    tofile='WORKING:app.js',
    n=2,
))
print(f'=== DIFF ({len(diff)} lines) ===')
for line in diff:
    print(line, end='' if line.endswith('\n') else '\n')
