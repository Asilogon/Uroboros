"""Remove previously added top-bar agents selector, Mind Map action button, and btnGoToMindMap."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
html_path = ROOT / 'deepseek_gui' / 'templates' / 'index.html'
css_path = ROOT / 'deepseek_gui' / 'static' / 'css' / 'style.css'
js_path = ROOT / 'deepseek_gui' / 'static' / 'js' / 'app.js'

# ==========================================================
# 1. INDEX.HTML: revert top-bar-right block
# ==========================================================
html = html_path.read_text(encoding='utf-8')

start_marker = '    <!-- RIGHT: TOP BAR - AGENTS SELECTOR + MIND MAP ACTION -->'
end_marker = '    </div>\n  </header>'

if start_marker in html:
    # Find block boundaries
    start_idx = html.index(start_marker)
    # Find the closing '    </div>' that precedes '</header>'
    end_idx = html.index(end_marker, start_idx)
    # Replace whole block (up to and including the closing div + newline) with clean empty div
    clean_block = '    <!-- RIGHT: CLEAN TOP BAR -->\n    <div class="top-bar-right"></div>\n'
    html = html[:start_idx] + clean_block + html[end_idx:]
    print('[PATCH] index.html: top-bar-right restored to empty')
else:
    print('[SKIP] index.html: no matching block (already reverted)')

# Remove btnGoToMindMap button from chat header
# Search for the button and its enclosing context.
btn_pattern = re.compile(r'\s*<button class="icon-btn" id="btnGoToMindMap"[^>]*>[\s\S]*?</button>', re.DOTALL)
if 'id="btnGoToMindMap"' in html:
    html = btn_pattern.sub('', html, count=1)
    print('[PATCH] index.html: btnGoToMindMap removed')
else:
    print('[SKIP] index.html: btnGoToMindMap not found (already removed)')

html_path.write_text(html, encoding='utf-8', newline='\n')
print('[DONE] index.html updated')

# ==========================================================
# 2. STYLE.CSS: remove .top-agents-* and .top-mindmap-action-btn block
# ==========================================================
css = css_path.read_text(encoding='utf-8')

start_css = '/* =====================================================================\n   TOP BAR: MULTI-AGENTS SELECTOR + MIND MAP ACTION\n   ===================================================================== */'
if start_css in css:
    # The block continues until end of file (we appended it last). Verify by looking for a specific end-marker.
    # It ends with the last style rule (.top-mindmap-action-btn:hover). We'll cut from start_css to the end of the file.
    start_idx = css.index(start_css)
    css = css[:start_idx].rstrip() + '\n'
    print('[PATCH] style.css: top-agents CSS block removed')
else:
    print('[SKIP] style.css: no matching CSS block (already removed)')

css_path.write_text(css, encoding='utf-8', newline='\n')
print('[DONE] style.css updated')

# ==========================================================
# 3. APP.JS: remove renderTopAgentsSelector, state, DOM refs, handlers, filters
# ==========================================================
js = js_path.read_text(encoding='utf-8')

# 3a. Remove DOM refs block
refs_block_start = '  // DOM Elements - Top Bar: Agents selector + Mind Map button'
refs_block_end = '  let selectedAgentIds = new Set();'
if refs_block_start in js:
    i = js.index(refs_block_start)
    j = js.index(refs_block_end, i) + len(refs_block_end)
    js = js[:i] + js[j:]
    # Remove the extra newline left over
    js = js.replace('\n\n\n', '\n\n')
    print('[PATCH] app.js: DOM refs + selectedAgentIds state removed')
else:
    print('[SKIP] app.js: DOM refs already gone')

# 3b. Remove the whole "3b. TOP BAR" section
section_start = '  // ===================================================================\n  // 3b. TOP BAR: AGENTS MULTI-SELECTOR + MIND MAP BUTTON\n  // ==================================================================='
if section_start in js:
    i = js.index(section_start)
    # Find end: the closing block of the section — last handler is topBtnMindMapAction, then next section marker.
    # We'll end at the beginning of "// 4. PROJECTS" comment or similar.
    next_section_pat = re.search(r'\n\s*// =+\s*\n\s*// 4\.', js[i:])
    if next_section_pat:
        end_rel = next_section_pat.start()
        end = i + end_rel
    else:
        # Fallback: cut to next occurrence of '// 4. PROJECTS'
        fallback = js.find('// 4. PROJECTS', i)
        end = fallback if fallback > 0 else len(js)
    js = js[:i] + js[end:]
    print('[PATCH] app.js: top-agents section removed')
else:
    print('[SKIP] app.js: top-agents section not found')

# 3c. Remove renderMindMap filter line
js = js.replace(
    '    const _displaySubagents = (selectedAgentIds.size === 0) ? subagents : subagents.filter((a) => selectedAgentIds.has(a.id));\n',
    '',
)
js = js.replace('_displaySubagents.forEach((agent) => {', 'subagents.forEach((agent) => {')
js = js.replace('if (_displaySubagents.length === 0) {', 'if (subagents.length === 0) {')
print('[PATCH] app.js: renderMindMap filter reverted')

# 3d. Remove selectProject refresh calls
js = js.replace(
    '      // _refreshInSelectProject\n      selectedAgentIds.clear();\n      renderTopAgentsSelector();\n',
    '',
)
print('[PATCH] app.js: selectProject refresh removed')

# 3e. Remove renderEmptyProjectState cleanup
js = js.replace(
    '  function renderEmptyProjectState() {\n    // _emptyStateClearSelector\n    selectedAgentIds.clear();\n    renderTopAgentsSelector();\n',
    '  function renderEmptyProjectState() {\n',
)
print('[PATCH] app.js: empty state cleanup removed')

# 3f. Remove btnGoToMindMap listener (safe — it now references a non-existent element).
#     btnGoToMindMap const will be null; the existing `if (btnGoToMindMap)` guard keeps it safe. Leave as is.

# 3g. Also remove btnGoToMindMap DOM ref line? Leave it as null-safe; but cleaner to remove.
js = js.replace('  const btnGoToMindMap = document.getElementById("btnGoToMindMap");\n', '')
js = js.replace('  if (btnGoToMindMap) btnGoToMindMap.addEventListener("click", () => switchView("mindmap"));\n', '')
print('[PATCH] app.js: btnGoToMindMap ref + handler removed')

js_path.write_text(js, encoding='utf-8', newline='\n')
print('[DONE] app.js updated')
print('Size:', js_path.stat().st_size, 'bytes')
