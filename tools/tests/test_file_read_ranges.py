"""Verify read_project_file pagination."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from deepseek_gui.app import read_project_file

# Whole file
r = read_project_file(str(ROOT), 'VERSION')
assert r['success'], r
print(f'[whole] total_lines={r["total_lines"]}, size={r["size"]}, content={r["content"]!r}')

# Range 1-3 of app.py
r = read_project_file(str(ROOT), 'deepseek_gui/app.py', start_line=1, end_line=3)
assert r['success'], r
print(f'[1-3] start={r["start_line"]} end={r["end_line"]} total={r["total_lines"]} trunc={r["truncated"]} next={r["next_start_line"]}')
print('  content (first 200 chars):')
print('  ', r['content'][:200].replace(chr(10), ' | '))

# Range 100-110
r = read_project_file(str(ROOT), 'deepseek_gui/app.py', start_line=100, end_line=110)
assert r['success'], r
print(f'[100-110] start={r["start_line"]} end={r["end_line"]} total={r["total_lines"]} trunc={r["truncated"]} next={r["next_start_line"]}')

# Only start_line
r = read_project_file(str(ROOT), 'deepseek_gui/app.py', start_line=1000)
assert r['success'], r
print(f'[1000-end] start={r["start_line"]} end={r["end_line"]} total={r["total_lines"]} trunc={r["truncated"]} next={r["next_start_line"]}')

# Out of bounds
r = read_project_file(str(ROOT), 'deepseek_gui/app.py', start_line=999999)
assert not r['success'], r
print(f'[out-of-bounds] error={r["error"]}')

# end_line < start_line
r = read_project_file(str(ROOT), 'deepseek_gui/app.py', start_line=100, end_line=50)
assert not r['success'], r
print(f'[bad-range] error={r["error"]}')

# Missing file
r = read_project_file(str(ROOT), 'nope.txt')
assert not r['success'], r
print(f'[missing] error={r["error"]}')

print()
print('ALL PAGINATION TESTS PASSED')
