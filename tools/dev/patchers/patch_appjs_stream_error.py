"""Patch app.js SSE loop to keep an error state after stream incomplete."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JS = ROOT / 'deepseek_gui' / 'static' / 'js' / 'app.js'
src = JS.read_text(encoding='utf-8')
marker = '// PATCHED: hadStreamError'
if marker in src:
    print('Already patched; nothing to do.')
    raise SystemExit(0)

# (1) declare flag before the while loop
old_decl = '      let buffer = "";\n\n      while (true) {\n        const { value, done } = await reader.read();'
new_decl = '      let buffer = "";\n      let hadStreamError = false;  // PATCHED: hadStreamError\n\n      while (true) {\n        const { value, done } = await reader.read();'
if old_decl not in src:
    print('ERROR: while-loop declaration anchor not found.')
    raise SystemExit(1)
src = src.replace(old_decl, new_decl, 1)

# (2) set hadStreamError when chunk.type === 'error'
old_err = (
    '              } else if (chunk.type === "error") {\n'
    '                mdBody.innerHTML += `<div style="color: #ef4444; margin-top: 6px;">[Ошибка: ${chunk.message}]</div>`;\n'
    '                updateLiveActivity(`Ошибка: ${chunk.message}`, activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, false);\n'
    '              }'
)
new_err = (
    '              } else if (chunk.type === "error") {\n'
    '                hadStreamError = true;\n'
    '                const errKind = chunk.kind || "error";\n'
    '                const errMsg = chunk.message || "Неизвестная ошибка";\n'
    '                mdBody.innerHTML += `<div style="color: #ef4444; margin-top: 6px;"><strong>[${errKind === "connection_lost" ? "Соединение потеряно" : "Ошибка"}]</strong> ${errMsg}</div>`;\n'
    '                updateLiveActivity(`Ошибка: ${errMsg}`, activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, false);\n'
    '              }'
)
# Try to replace the ORIGINAL error branch (may have garbled text due to encoding). Fall back to regex.
import re
pat = re.compile(r'\}\s*else if \(chunk\.type === "error"\) \{[\s\S]*?updateLiveActivity\([^\n]*?;\s*\}')
if old_err in src:
    src = src.replace(old_err, new_err, 1)
else:
    # fallback: replace just the line with hadStreamError inside the error branch, using the FIRST occurrence of chunk.type === "error" inside the SSE loop
    # Locate the SSE loop's error branch by finding the substring up to the next '}}'
    idx = src.find('} else if (chunk.type === "error") {')
    if idx == -1:
        print('ERROR: error-branch anchor not found.')
        raise SystemExit(1)
    end_idx = src.find('\n              }', idx + 10)
    if end_idx == -1:
        print('ERROR: end of error-branch not found.')
        raise SystemExit(1)
    # Get the original block
    block = src[idx:end_idx]
    # Replace block with new one but keep the same opening condition
    replacement = new_err[2:]  # strip leading 2 spaces so '{...' aligns
    src = src[:idx] + replacement + src[end_idx:]

# (3) after loop, only show 'Готово' if no stream error
old_finish = (
    '      // Finish generation state and display static completed tree\n'
    '      const completedTreeTitle = isSolo ? `Действия инженера (${liveSteps.length})` : `Действия координатора (${liveSteps.length})`;\n'
    '      const finalTree = buildActionStepsTreeElement(liveSteps, false, completedTreeTitle);\n'
    '      treeContainerEl.replaceWith(finalTree);\n'
    '      treeContainerEl = finalTree;\n'
    '      activeGeneration.treeContainerEl = finalTree;\n'
)
if old_finish not in src:
    # Encoding likely CP1251/UTF8 mismatch on RU strings. Use a simpler ASCII-only anchor.
    # Anchor on '// Finish generation state' and the two following const/assignment lines
    import re as _re
    m = _re.search(r'[ \t]*// Finish generation state and display static completed tree\r?\n', src)
    if not m:
        print('ERROR: finish-state anchor not found.')
        raise SystemExit(1)
    # Insert a conditional block BEFORE the existing finish block
    insert_at = m.start()
    guard_block = (
        '      if (hadStreamError) {\n'
        '        updateLiveActivity("Ошибка: соединение с DeepSeek потеряно", activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, false);\n'
        '        activeGeneration.streamErrored = true;\n'
        '      } else {\n'
    )
    # We need to close the else block at the end of the finish-block. Find the next blank-line boundary after 'activeGeneration.treeContainerEl = finalTree;'
    end_marker = _re.search(r'activeGeneration\.treeContainerEl = finalTree;\r?\n', src[insert_at:])
    if not end_marker:
        print('ERROR: end of finish block not found.')
        raise SystemExit(1)
    close_at = insert_at + end_marker.end()
    src = src[:insert_at] + guard_block + src[insert_at:close_at] + '      }\n' + src[close_at:]
else:
    # Will not run for CP1251 file, left for reference.
    new_finish = (
        '      if (hadStreamError) {\n'
        '        updateLiveActivity("Ошибка: соединение с DeepSeek потеряно", activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, false);\n'
        '        activeGeneration.streamErrored = true;\n'
        '      } else {\n'
        '        // Finish generation state and display static completed tree\n'
        '        const completedTreeTitle = isSolo ? `Действия инженера (${liveSteps.length})` : `Действия координатора (${liveSteps.length})`;\n'
        '        const finalTree = buildActionStepsTreeElement(liveSteps, false, completedTreeTitle);\n'
        '        treeContainerEl.replaceWith(finalTree);\n'
        '        treeContainerEl = finalTree;\n'
        '        activeGeneration.treeContainerEl = finalTree;\n'
        '      }\n'
    )
    src = src.replace(old_finish, new_finish, 1)

JS.write_text(src, encoding='utf-8', newline='\n')
print('OK: app.js patched for stream-error handling.')
