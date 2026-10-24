"""Patch app.py and app.js to add web_fetch tool."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
app_path = ROOT / 'deepseek_gui' / 'app.py'
js_path = ROOT / 'deepseek_gui' / 'static' / 'js' / 'app.js'

WEB_BRANCH_SUB = r'''                elif a_type in ("web", "web_fetch"):
                    w_url = (act.get("url") or "").strip()
                    w_save = (act.get("save_to") or act.get("save_path") or "").strip() or None
                    w_res = web_fetch(w_url, save_path=w_save, project_root=project_root)
                    w_preview = w_res.get("preview", "")
                    web_step = {
                        "category": "web",
                        "title": f"Fetched {w_url}",
                        "url": w_url,
                        "final_url": w_res.get("final_url", w_url),
                        "status_code": w_res.get("status_code"),
                        "content_type": w_res.get("content_type", ""),
                        "size": w_res.get("size", 0),
                        "saved_path": w_res.get("saved_path"),
                        "save_error": w_res.get("save_error"),
                        "preview": w_preview,
                        "success": w_res.get("success", False),
                        "output": w_preview,
                    }
                    sub_steps.append(web_step)
                    turn_observations.append(
                        "[WEB " + w_url + " status=" + str(w_res.get('status_code'))
                        + " size=" + str(w_res.get('size', 0))
                        + " saved=" + str(w_res.get('saved_path')) + "]\n"
                        + w_preview[:4000]
                    )
'''

WEB_BRANCH_YIELD = r'''                    elif a_type in ("web", "web_fetch"):
                        w_url = (act.get("url") or "").strip()
                        w_save = (act.get("save_to") or act.get("save_path") or "").strip() or None
                        w_res = web_fetch(w_url, save_path=w_save, project_root=project_root)
                        w_preview = w_res.get("preview", "")
                        web_step = {
                            "category": "web",
                            "title": f"Fetched {w_url}",
                            "url": w_url,
                            "final_url": w_res.get("final_url", w_url),
                            "status_code": w_res.get("status_code"),
                            "content_type": w_res.get("content_type", ""),
                            "size": w_res.get("size", 0),
                            "saved_path": w_res.get("saved_path"),
                            "save_error": w_res.get("save_error"),
                            "preview": w_preview,
                            "success": w_res.get("success", False),
                            "output": w_preview,
                        }
                        all_accumulated_steps.append(web_step)
                        yield "data: " + json.dumps({"type": "action_step", "step": web_step}, ensure_ascii=False) + "\n\n"
                        turn_observations.append(
                            "[WEB " + w_url + " status=" + str(w_res.get('status_code'))
                            + " size=" + str(w_res.get('size', 0))
                            + " saved=" + str(w_res.get('saved_path')) + "]\n"
                            + w_preview[:4000]
                        )
'''

# ---------- app.py ----------
src = app_path.read_text(encoding='utf-8')

# 1. Import
if 'from .web_tool import web_fetch' not in src:
    marker = 'from .version import __version__'
    assert marker in src, 'version import not found'
    src = src.replace(marker, marker + '\nfrom .web_tool import web_fetch', 1)
    print('[PATCH] app.py: import web_fetch added')
else:
    print('[SKIP] app.py: import already present')

# 2. First branch (subagent internal, single-file). Insert right before 'elif a_type == "file_read":'
# with 16-space indent.
marker_sub = '                elif a_type == "file_read":\n'
if marker_sub in src:
    src = src.replace(marker_sub, WEB_BRANCH_SUB + marker_sub, 1)
    print('[PATCH] app.py: web branch inserted (subagent internal)')
else:
    print('[WARN] app.py: subagent-internal file_read marker not found')

# 3. Yield branches (two places with 20-space indent)
marker_yield = '                    elif a_type == "file_read":\n'
inserted = 0
while marker_yield in src and inserted < 2:
    src = src.replace(marker_yield, WEB_BRANCH_YIELD + marker_yield, 1)
    inserted += 1
    print(f'[PATCH] app.py: web branch inserted (yield #{inserted})')
if inserted == 0:
    print('[WARN] app.py: yield file_read markers not found')

app_path.write_text(src, encoding='utf-8', newline='\n')
print('[DONE] app.py updated')

# ---------- app.js ----------
js = js_path.read_text(encoding='utf-8')

# 1. Icon — find the exact block regardless of encoding issues by matching on 'else if (st.category === "file_read")'
import re as _re
m = _re.search(r'(\s*else if \(st\.category === "file_read"\) iconChar = "[^"]*";\n)', js)
if m and 'st.category === "web"' not in js:
    insert_at = m.end()
    js = js[:insert_at] + '        else if (st.category === "web") iconChar = "\uD83C\uDF10";\n' + js[insert_at:]
    print('[PATCH] app.js: web icon added')
else:
    print('[SKIP] app.js: web icon already present or marker not found')

# 2. Web detail block: insert before '} else if (st.output !== undefined) {'
web_detail_block = r'''          } else if (st.category === "web") {
            const wBox = document.createElement("div");
            wBox.className = "step-web-box";
            const wUrl = st.url || "";
            const wSafe = escapeHtml(wUrl);
            const wPreview = st.preview ? escapeHtml(String(st.preview).substring(0, 4000)) : "";
            wBox.innerHTML = "<div><strong>URL:</strong> <a href=\"" + wSafe + "\" target=\"_blank\" rel=\"noopener\">" + wSafe + "</a></div>"
              + (st.status_code !== undefined && st.status_code !== null ? "<div><strong>Status:</strong> " + st.status_code + "</div>" : "")
              + (st.content_type ? "<div><strong>Content-Type:</strong> " + escapeHtml(st.content_type) + "</div>" : "")
              + (st.size !== undefined ? "<div><strong>Size:</strong> " + st.size + " bytes</div>" : "")
              + (st.saved_path ? "<div><strong>Saved:</strong> <code>" + escapeHtml(st.saved_path) + "</code></div>" : "")
              + (wPreview ? "<pre class=\"step-web-preview\">" + wPreview + "</pre>" : "");
            detailBox.appendChild(wBox);
          } else if (st.output !== undefined) {
'''

if 'st.category === "web"' not in js:
    # Find a line '} else if (st.output !== undefined) {' and insert before it
    out_marker = '          } else if (st.output !== undefined) {\n'
    if out_marker in js:
        # The web_detail_block ends with '} else if (st.output !== undefined) {\n' so we need to replace out_marker by web_detail_block,
        # but that would duplicate. Better: insert web_detail_block WITHOUT the trailing marker at out_marker start.
        web_detail_body = web_detail_block[:-len('          } else if (st.output !== undefined) {\n')]
        js = js.replace(out_marker, web_detail_body + out_marker, 1)
        print('[PATCH] app.js: web detail block added')
    else:
        print('[WARN] app.js: output marker not found')
else:
    print('[SKIP] app.js: web detail already present')

# 3. Expand condition
if 'st.category === "web"' in js and 'st.category === "file_read" || st.category === "web"' not in js:
    marker_expand = 'st.category === "file_read") {'
    if marker_expand in js:
        js = js.replace(marker_expand, 'st.category === "file_read" || st.category === "web") {', 1)
        print('[PATCH] app.js: expandable condition updated')
    else:
        print('[WARN] app.js: expand marker not found')
else:
    print('[SKIP] app.js: expandable condition already includes web')

js_path.write_text(js, encoding='utf-8', newline='\n')
print('[DONE] app.js updated')
