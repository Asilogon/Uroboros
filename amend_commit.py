"""Amend the latest commit message to [X.X.X] format, reading from file."""
import sys
from pathlib import Path

from dulwich.objects import Commit
from dulwich.repo import Repo

ROOT = Path(__file__).resolve().parent
repo = Repo(str(ROOT))

head_sha = repo.head()
old_commit = repo[head_sha]
print(f'[HEAD] {head_sha.decode()}')
print(f'[OLD MESSAGE]\n{old_commit.message.decode()}\n')

# Message can come from: (1) arg if it's a path to existing file, (2) arg as string, (3) default file
if len(sys.argv) >= 2:
    arg = sys.argv[1]
    p = Path(arg)
    if p.exists() and p.is_file():
        new_message = p.read_text(encoding='utf-8')
        print(f'[SOURCE] file: {arg}')
    else:
        new_message = arg
        print('[SOURCE] cli arg')
else:
    default_file = ROOT / 'new_commit_message.txt'
    if not default_file.exists():
        raise SystemExit('No message provided and new_commit_message.txt not found')
    new_message = default_file.read_text(encoding='utf-8')
    print(f'[SOURCE] default file: {default_file}')

print(f'[NEW MESSAGE]\n{new_message}\n')

# Create new commit
new_commit = Commit()
new_commit.tree = old_commit.tree
new_commit.parents = old_commit.parents
new_commit.author = old_commit.author
new_commit.committer = old_commit.committer
new_commit.commit_time = old_commit.commit_time + 1
new_commit.commit_timezone = old_commit.commit_timezone
new_commit.author_time = old_commit.author_time
new_commit.author_timezone = old_commit.author_timezone
new_commit.message = new_message.encode('utf-8')
new_commit.encoding = old_commit.encoding

repo.object_store.add_object(new_commit)
new_sha = new_commit.id
print(f'[NEW SHA] {new_sha.decode()}')

ref_name = b'refs/heads/feature/deepseek'
repo.refs[ref_name] = new_sha
print(f'[REF] {ref_name.decode()} -> {new_sha.decode()}')
print('[OK] commit amended')
