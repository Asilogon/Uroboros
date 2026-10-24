from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'deepseek_gui' / 'app.py'
src = APP.read_text(encoding='utf-8')

bad = "'thinking': '\","
good = "'thinking': '',"
if bad in src:
    src = src.replace(bad, good, 1)
    APP.write_text(src, encoding='utf-8', newline='\n')
    print('fixed quote')
else:
    print('quote pattern not found; inspect manually')

ast.parse(APP.read_text(encoding='utf-8'))
print('app.py parses OK')
