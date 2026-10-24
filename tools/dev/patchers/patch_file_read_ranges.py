import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'deepseek_gui' / 'app.py'
src = APP.read_text(encoding='utf-8')
marker = '# === PATCHED: file_read_ranges ==='
if marker in src:
    print('Already patched; nothing to do.')
    sys.exit(0)

# ---------- STEP 1: Replace read_project_file with range-aware version ----------
m = re.search(r'def read_project_file\([\s\S]*?\n(?=def extract_file_writes)', src)
if not m:
    print('ERROR: cannot find read_project_file function')
    sys.exit(1)

# We'll build the new function as a list of lines to avoid escaping headaches.
new_fn_lines = [
    'def read_project_file(',
    '    project_root: str,',
    '    file_path: str,',
    '    start_line: Optional[int] = None,',
    '    end_line: Optional[int] = None,',
    ') -> Dict[str, Any]:',
    '    """Reads a file (or a slice of lines) relative to project root.',
    '',
    '    start_line / end_line are 1-based and INCLUSIVE. Both None -> whole file.',
    '    Returns dict with keys: success, path, rel_path, content, size,',
    '    total_lines, start_line, end_line, truncated, next_start_line.',
    '    """',
    '    try:',
    '        root = Path(project_root).resolve()',
    '        clean_rel = file_path.strip().lstrip("' + chr(47) + chr(92) + chr(92) + '")',
    '        target = (root / clean_rel).resolve()',
    '        if not target.exists():',
    '            return {',
    '                "success": False,',
    '                "path": file_path,',
    '                "rel_path": clean_rel,',
    '                "error": f"Файл \'{clean_rel}\' не найден на диске",',
    '            }',
    '        full_text = target.read_text(encoding="utf-8", errors="replace")',
    '        total_lines = full_text.count("\\n") + (1 if full_text and not full_text.endswith("\\n") else 0)',
    '        if total_lines == 0 and full_text:',
    '            total_lines = 1',
    '',
    '        if start_line is None and end_line is None:',
    '            return {',
    '                "success": True,',
    '                "path": str(target),',
    '                "rel_path": clean_rel,',
    '                "content": full_text,',
    '                "size": len(full_text.encode("utf-8")),',
    '                "total_lines": total_lines,',
    '                "start_line": 1 if total_lines else 0,',
    '                "end_line": total_lines,',
    '                "truncated": False,',
    '                "next_start_line": None,',
    '            }',
    '',
    '        try:',
    '            sl = int(start_line) if start_line is not None else 1',
    '        except (TypeError, ValueError):',
    '            sl = 1',
    '        try:',
    '            el = int(end_line) if end_line is not None else total_lines',
    '        except (TypeError, ValueError):',
    '            el = total_lines',
    '        if sl < 1:',
    '            sl = 1',
    '        if el < sl:',
    '            return {',
    '                "success": False,',
    '                "path": str(target),',
    '                "rel_path": clean_rel,',
    '                "total_lines": total_lines,',
    '                "error": f"end_line ({el}) < start_line ({sl})",',
    '            }',
    '        if sl > total_lines:',
    '            return {',
    '                "success": False,',
    '                "path": str(target),',
    '                "rel_path": clean_rel,',
    '                "total_lines": total_lines,',
    '                "error": f"start_line ({sl}) за пределами файла (всего строк: {total_lines})",',
    '            }',
    '        if el > total_lines:',
    '            el = total_lines',
    '',
    '        lines = full_text.splitlines(keepends=True)',
    '        slice_text = "".join(lines[sl - 1:el])',
    '        truncated = el < total_lines',
    '        return {',
    '            "success": True,',
    '            "path": str(target),',
    '            "rel_path": clean_rel,',
    '            "content": slice_text,',
    '            "size": len(slice_text.encode("utf-8")),',
    '            "total_lines": total_lines,',
    '            "start_line": sl,',
    '            "end_line": el,',
    '            "truncated": truncated,',
    '            "next_start_line": (el + 1) if truncated else None,',
    '        }',
    '    except Exception as e:',
    '        return {',
    '            "success": False,',
    '            "path": file_path,',
    '            "rel_path": file_path,',
    '            "error": str(e),',
    '        }',
    '',
    '',
]
new_fn = '\n'.join(new_fn_lines) + '\n'
src = src[:m.start()] + new_fn + src[m.end():]
print('STEP 1: read_project_file replaced')

# ---------- STEP 2: Update 3 read_project_file(project_root, path) call sites ----------
pattern = re.compile(r'(?P<ind>[ ]+)r_res = read_project_file\(project_root, path\)')
matches = list(pattern.finditer(src))
if len(matches) != 3:
    print(f'ERROR: expected 3 read_project_file call sites, found {len(matches)}')
    sys.exit(1)
for mm in reversed(matches):
    ind = mm.group('ind')
    repl = (
        ind + '_sl = act.get("start_line")\n'
        + ind + '_el = act.get("end_line")\n'
        + ind + 'r_res = read_project_file(project_root, path, start_line=_sl, end_line=_el)'
    )
    src = src[:mm.start()] + repl + src[mm.end():]
print('STEP 2: 3 read calls updated')

# ---------- STEP 3: Extend sub_steps dict ----------
old_a = (
    '                    sub_steps.append({\n'
    '                        "category": "file_read",\n'
    '                        "title": f"Read file {path}",\n'
    '                        "file_path": path,\n'
    '                        "success": r_res.get("success", False),\n'
    '                        "output": r_res.get("content", r_res.get("error", "")),\n'
    '                    })\n'
)
new_a = (
    '                    _title = (f"Read file {path} (lines {r_res.get(chr(39)+\'start_line\'+chr(39))}-{r_res.get(chr(39)+\'end_line\'+chr(39))})"\n'
    '                              if (_sl is not None or _el is not None) and r_res.get("success") else f"Read file {path}")\n'
    '                    sub_steps.append({\n'
    '                        "category": "file_read",\n'
    '                        "title": _title,\n'
    '                        "file_path": path,\n'
    '                        "start_line": r_res.get("start_line"),\n'
    '                        "end_line": r_res.get("end_line"),\n'
    '                        "total_lines": r_res.get("total_lines"),\n'
    '                        "success": r_res.get("success", False),\n'
    '                        "output": r_res.get("content", r_res.get("error", "")),\n'
    '                    })\n'
)
if old_a not in src:
    print('ERROR: sub_steps.append anchor not found')
    sys.exit(1)
src = src.replace(old_a, new_a, 1)
print('STEP 3: sub_steps dict extended')

# ---------- STEP 4: Extend read_step dicts (2 occurrences) ----------
old_bc = (
    '                        read_step = {\n'
    '                            "category": "file_read",\n'
    '                            "title": f"Read file {path}",\n'
    '                            "file_path": path,\n'
    '                            "success": r_res.get("success", False),\n'
    '                            "output": r_res.get("content", r_res.get("error", "")),\n'
    '                        }\n'
)
new_bc = (
    '                        _title = (f"Read file {path} (lines {r_res.get(chr(39)+\'start_line\'+chr(39))}-{r_res.get(chr(39)+\'end_line\'+chr(39))})"\n'
    '                                  if (_sl is not None or _el is not None) and r_res.get("success") else f"Read file {path}")\n'
    '                        read_step = {\n'
    '                            "category": "file_read",\n'
    '                            "title": _title,\n'
    '                            "file_path": path,\n'
    '                            "start_line": r_res.get("start_line"),\n'
    '                            "end_line": r_res.get("end_line"),\n'
    '                            "total_lines": r_res.get("total_lines"),\n'
    '                            "success": r_res.get("success", False),\n'
    '                            "output": r_res.get("content", r_res.get("error", "")),\n'
    '                        }\n'
)
n = src.count(old_bc)
if n != 2:
    print(f'ERROR: expected 2 read_step dicts, found {n}')
    sys.exit(1)
src = src.replace(old_bc, new_bc)
print('STEP 4: 2 read_step dicts extended')

# ---------- STEP 5: Add pagination hint to observations ----------
# site 1 (subagent blocking, indent 20)
old_h1 = '                    turn_observations.append(f"[Содержимое файла \'{path}\']:\\n{file_content}")\n'
if old_h1 in src:
    new_h1 = (
        '                    _hint = ""\n'
        '                    if r_res.get("truncated"):\n'
        '                        _hint = (f"\\n[Файл \'{path}\' показан частично: строки "\n'
        '                                 f"{r_res.get(chr(39)+\'start_line\'+chr(39))}-{r_res.get(chr(39)+\'end_line\'+chr(39))} из {r_res.get(chr(39)+\'total_lines\'+chr(39))}. "\n'
        '                                 f"Чтобы прочитать дальше, вызови file_read с start_line={r_res.get(chr(39)+\'next_start_line\'+chr(39))}.")\n'
        '                    turn_observations.append(f"[Содержимое файла \'{path}\']:\\n{file_content}{_hint}")\n'
    )
    src = src.replace(old_h1, new_h1, 1)
    print('STEP 5a: site1 hint added')
else:
    print('WARN: site1 hint anchor not found')

# site 2 (subagent SSE, indent 24)
old_h2 = '                        turn_observations.append(f"[Содержимое файла \'{path}\']:\\n{file_content}")\n'
if old_h2 in src:
    new_h2 = (
        '                        _hint = ""\n'
        '                        if r_res.get("truncated"):\n'
        '                            _hint = (f"\\n[Файл \'{path}\' показан частично: строки "\n'
        '                                     f"{r_res.get(chr(39)+\'start_line\'+chr(39))}-{r_res.get(chr(39)+\'end_line\'+chr(39))} из {r_res.get(chr(39)+\'total_lines\'+chr(39))}. "\n'
        '                                     f"Чтобы прочитать дальше, вызови file_read с start_line={r_res.get(chr(39)+\'next_start_line\'+chr(39))}.")\n'
        '                        turn_observations.append(f"[Содержимое файла \'{path}\']:\\n{file_content}{_hint}")\n'
    )
    src = src.replace(old_h2, new_h2, 1)
    print('STEP 5b: site2 hint added')
else:
    print('WARN: site2 hint anchor not found')

# site 3 (lead SSE, indent 24)
old_h3 = '                        step_observations.append(f"[Содержимое файла \'{path}\']:\\n{r_res.get(\'content\', r_res.get(\'error\', \'\'))}")\n'
if old_h3 in src:
    new_h3 = (
        '                        _hint = ""\n'
        '                        if r_res.get("truncated"):\n'
        '                            _hint = (f"\\n[Файл \'{path}\' показан частично: строки "\n'
        '                                     f"{r_res.get(chr(39)+\'start_line\'+chr(39))}-{r_res.get(chr(39)+\'end_line\'+chr(39))} из {r_res.get(chr(39)+\'total_lines\'+chr(39))}. "\n'
        '                                     f"Чтобы прочитать дальше, вызови file_read с start_line={r_res.get(chr(39)+\'next_start_line\'+chr(39))}.")\n'
        '                        step_observations.append(f"[Содержимое файла \'{path}\']:\\n{r_res.get(\'content\', r_res.get(\'error\', \'\'))}{_hint}")\n'
    )
    src = src.replace(old_h3, new_h3, 1)
    print('STEP 5c: site3 hint added')
else:
    print('WARN: site3 hint anchor not found')

# ---------- STEP 6: Extend JSON schema examples in prompts ----------
# Add start_line/end_line note after the file_read schema example
schema_needle = '        "      \\"type\\": \\"file_read\\",\\n"\n'
if schema_needle in src:
    schema_new = (
        '        "      \\"type\\": \\"file_read\\",\\n"\n'
        + '        "      \\"start_line\\": 1, \\"end_line\\": 500,   // ОПЦИОНАЛЬНО: диапазон строк (1-based, включительно)\\n"\n'
    )
    cnt = src.count(schema_needle)
    src = src.replace(schema_needle, schema_new)
    print(f'STEP 6: {cnt} schema examples extended')
else:
    print('WARN: file_read schema example not found')

# ---------- STEP 7: Add pagination note to text prompts ----------
note = (
    'ОПЦИОНАЛЬНО для больших файлов: `file_read` поддерживает постраничное чтение '
    'через поля `start_line` и `end_line` (1-based, включительно). Пример: '
    '{"type": "file_read", "path": "deepseek_gui/app.py", "start_line": 100, "end_line": 499}. '
    'Если в ответе помечено, что файл показан частично — дочитай следующий диапазон с start_line=next_start_line. '
    'Разбивай большие файлы на куски по 400-500 строк.'
)
inserted = 0
for needle in (
    'Проверяешь существующие файлы через `file_read`.',
    'Если нужно — лично прочитай созданный файл через `file_read` или проверь консольной командой через `cmd`.',
):
    if needle in src:
        src = src.replace(needle, needle + ' ' + note, 1)
        inserted += 1
print(f'STEP 7: text prompt notes inserted in {inserted} block(s)')

# ---------- Finalize ----------
src = marker + '\n' + src
APP.write_text(src, encoding='utf-8', newline='\n')
print()
print('OK: app.py patched for file_read pagination.')
