"""Insert web detail block into buildActionStepsTreeElement (robust)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
js_path = ROOT / 'deepseek_gui' / 'static' / 'js' / 'app.js'

with open(js_path, 'r', encoding='utf-8') as f:
    js = f.read()

if 'step-web-box' in js:
    print('[SKIP] web detail block already present')
else:
    # Find '} else if (st.output !== undefined) {' (line-level)
    needle = '} else if (st.output !== undefined) {'
    idx = js.find(needle)
    if idx < 0:
        raise SystemExit('[ERROR] marker not found')
    # Find the start of the current line (to preserve indentation)
    line_start = js.rfind('\n', 0, idx) + 1
    # Determine indentation
    j = line_start
    while j < len(js) and js[j] in ' \t':
        j += 1
    indent = js[line_start:j]
    # Build web block with the same indent (indent + '  ' for deeper body)
    inner = indent + '  '
    web_block = (
        indent + '} else if (st.category === "web") {\n'
        + inner + 'const wBox = document.createElement("div");\n'
        + inner + 'wBox.className = "step-web-box";\n'
        + inner + 'const wUrl = st.url || "";\n'
        + inner + 'const wSafe = escapeHtml(wUrl);\n'
        + inner + 'const wPreview = st.preview ? escapeHtml(String(st.preview).substring(0, 4000)) : "";\n'
        + inner + 'wBox.innerHTML = "<div><strong>URL:</strong> <a href=\\\"" + wSafe + "\\\" target=\\\"_blank\\\" rel=\\\"noopener\\\">" + wSafe + "</a></div>"\n'
        + inner + '  + (st.status_code !== undefined && st.status_code !== null ? "<div><strong>Status:</strong> " + st.status_code + "</div>" : "")\n'
        + inner + '  + (st.content_type ? "<div><strong>Content-Type:</strong> " + escapeHtml(st.content_type) + "</div>" : "")\n'
        + inner + '  + (st.size !== undefined ? "<div><strong>Size:</strong> " + st.size + " bytes</div>" : "")\n'
        + inner + '  + (st.saved_path ? "<div><strong>Saved:</strong> <code>" + escapeHtml(st.saved_path) + "</code></div>" : "")\n'
        + inner + '  + (wPreview ? "<pre class=\\\"step-web-preview\\\">" + wPreview + "</pre>" : "");\n'
        + inner + 'detailBox.appendChild(wBox);\n'
    )
    new_js = js[:line_start] + web_block + js[line_start:]
    with open(js_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_js)
    print('[PATCH] web detail block inserted')
    print('Size:', js_path.stat().st_size, 'bytes')
