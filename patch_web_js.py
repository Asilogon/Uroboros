"""Add web category rendering to app.js (icon=🌐, detail block, expandable)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
js_path = ROOT / 'deepseek_gui' / 'static' / 'js' / 'app.js'

with open(js_path, 'r', encoding='utf-8') as f:
    js = f.read()

# -------- 1. Icon --------
# Find the iconChar assignment chain for file_read.
# Match either encoding variant of the char on the file_read line.
import re

icon_pat = re.compile(
    r'(?P<line>\n\s*else if \(st\.category === "file_read"\) iconChar = "[^"]*";)'
)
m = icon_pat.search(js)
if m and 'st.category === "web"' not in js:
    insert_at = m.end()
    # 🌐 = U+1F310 (single code point, valid UTF-8)
    planet = '\U0001F310'
    new_line = f'\n        else if (st.category === "web") iconChar = "{planet}";'
    js = js[:insert_at] + new_line + js[insert_at:]
    print('[PATCH] app.js: web icon added')
else:
    print('[SKIP/WARN] app.js: web icon not added (already present or marker not found)')

# -------- 2. Detail block --------
# Insert a web detail branch right before the generic 'st.output !== undefined' branch
# inside buildActionStepsTreeElement.
# Locate the exact substring: '          } else if (st.output !== undefined) {'
out_marker = '          } else if (st.output !== undefined) {'
if 'st.category === "web"' not in js or out_marker in js:
    if 'st.category === "web"' not in js and out_marker in js:
        web_branch = (
            '          } else if (st.category === "web") {\n'
            '            const wBox = document.createElement("div");\n'
            '            wBox.className = "step-web-box";\n'
            '            const wUrl = st.url || "";\n'
            '            const wSafe = escapeHtml(wUrl);\n'
            '            const wPreview = st.preview ? escapeHtml(String(st.preview).substring(0, 4000)) : "";\n'
            '            wBox.innerHTML = "<div><strong>URL:</strong> <a href=\\\"" + wSafe + "\\\" target=\\\"_blank\\\" rel=\\\"noopener\\\">" + wSafe + "</a></div>"\n'
            '              + (st.status_code !== undefined && st.status_code !== null ? "<div><strong>Status:</strong> " + st.status_code + "</div>" : "")\n'
            '              + (st.content_type ? "<div><strong>Content-Type:</strong> " + escapeHtml(st.content_type) + "</div>" : "")\n'
            '              + (st.size !== undefined ? "<div><strong>Size:</strong> " + st.size + " bytes</div>" : "")\n'
            '              + (st.saved_path ? "<div><strong>Saved:</strong> <code>" + escapeHtml(st.saved_path) + "</code></div>" : "")\n'
            '              + (wPreview ? "<pre class=\\\"step-web-preview\\\">" + wPreview + "</pre>" : "");\n'
            '            detailBox.appendChild(wBox);\n'
            '          } else if (st.output !== undefined) {'
        )
        js = js.replace(out_marker, web_branch, 1)
        print('[PATCH] app.js: web detail block added')
    else:
        print('[SKIP] app.js: web detail block already present or marker missing')

# -------- 3. Expandable condition --------
# Make sure summaryRow click works: include 'web' in the expandable condition.
expand_old = 'st.category === "file_read") {'
expand_new = 'st.category === "file_read" || st.category === "web") {'
if expand_old in js and expand_new not in js:
    js = js.replace(expand_old, expand_new, 1)
    print('[PATCH] app.js: expandable condition updated')
else:
    print('[SKIP] app.js: expandable condition already updated or marker missing')

# -------- Write back --------
with open(js_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(js)
print('[DONE] app.js written')
print('Size:', js_path.stat().st_size, 'bytes')
