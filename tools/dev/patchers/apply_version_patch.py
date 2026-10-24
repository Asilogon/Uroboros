"""Apply version badge patch to Uroboros files."""
import io
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print(f'[WRITE] {path.relative_to(ROOT)}')


# -------- 1. VERSION file --------
write_file(ROOT / 'VERSION', '0.0.1\n')

# -------- 2. deepseek_gui/version.py --------
write_file(
    ROOT / 'deepseek_gui' / 'version.py',
    '# Uroboros version (single source of truth)\n__version__ = \'0.0.1\'\n'
)

# -------- 3. Patch app.py --------
app_path = ROOT / 'deepseek_gui' / 'app.py'
app_src = app_path.read_text(encoding='utf-8')

# 3a. Add version import after 'from .projects_manager import projects_manager'
if 'from .version import __version__' not in app_src:
    marker = 'from .projects_manager import projects_manager'
    assert marker in app_src, 'projects_manager import not found in app.py'
    app_src = app_src.replace(
        marker,
        marker + '\nfrom .version import __version__',
        1,
    )
    print('[PATCH] app.py: version import added')
else:
    print('[SKIP] app.py: version import already present')

# 3b. Add /api/version route before @app.route("/")
if '@app.route("/api/version"' not in app_src:
    route_marker = '@app.route("/")'
    assert route_marker in app_src, 'root route not found in app.py'
    version_route = (
        '@app.route("/api/version", methods=["GET"])\n'
        'def api_version():\n'
        '    """Returns the current application version."""\n'
        '    return jsonify({"version": __version__})\n'
        '\n\n'
    )
    app_src = app_src.replace(route_marker, version_route + route_marker, 1)
    print('[PATCH] app.py: /api/version route added')
else:
    print('[SKIP] app.py: /api/version route already present')

app_path.write_text(app_src, encoding='utf-8', newline='\n')

# -------- 4. Patch index.html --------
idx_path = ROOT / 'deepseek_gui' / 'templates' / 'index.html'
idx_src = idx_path.read_text(encoding='utf-8')

old_span = '<span id="authStatusDot" class="status-dot"></span>'
new_span = '<span id="appVersionBadge" class="app-version-badge" title="Версия Uroboros">v0.0.1</span>'

if old_span in idx_src:
    idx_src = idx_src.replace(old_span, new_span, 1)
    print('[PATCH] index.html: authStatusDot replaced with appVersionBadge')
elif 'appVersionBadge' in idx_src:
    print('[SKIP] index.html: already patched')
else:
    raise SystemExit('[ERROR] index.html: authStatusDot span not found')

idx_path.write_text(idx_src, encoding='utf-8', newline='\n')

# -------- 5. Patch style.css --------
css_path = ROOT / 'deepseek_gui' / 'static' / 'css' / 'style.css'
css_src = css_path.read_text(encoding='utf-8')

if '.app-version-badge' not in css_src:
    settings_btn_block = (
        '.settings-btn:hover {\n'
        '  color: var(--text-main);\n'
        '}\n'
    )
    assert settings_btn_block in css_src, '.settings-btn:hover block not found in style.css'
    badge_css = (
        '\n'
        '/* Application version badge (shown next to Settings button) */\n'
        '.app-version-badge {\n'
        '  font-size: 10.5px;\n'
        '  font-weight: 500;\n'
        '  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;\n'
        '  color: var(--text-muted);\n'
        '  background-color: var(--badge-bg);\n'
        '  border: 1px solid var(--border-color);\n'
        '  border-radius: 5px;\n'
        '  padding: 1px 7px;\n'
        '  letter-spacing: 0.2px;\n'
        '  user-select: none;\n'
        '  cursor: default;\n'
        '  flex-shrink: 0;\n'
        '  transition: color 0.12s ease, border-color 0.12s ease;\n'
        '}\n'
        '\n'
        '.app-version-badge:hover {\n'
        '  color: var(--text-main);\n'
        '  border-color: var(--border-light);\n'
        '}\n'
    )
    css_src = css_src.replace(settings_btn_block, settings_btn_block + badge_css, 1)
    print('[PATCH] style.css: .app-version-badge added')
else:
    print('[SKIP] style.css: .app-version-badge already present')

css_path.write_text(css_src, encoding='utf-8', newline='\n')

# -------- 6. Patch app.js --------
js_path = ROOT / 'deepseek_gui' / 'static' / 'js' / 'app.js'
js_src = js_path.read_text(encoding='utf-8')

# 6a. Replace const authStatusDot reference with appVersionBadge
old_decl = '  const authStatusDot = document.getElementById("authStatusDot");'
new_decl = '  const appVersionBadge = document.getElementById("appVersionBadge");'
if old_decl in js_src:
    js_src = js_src.replace(old_decl, new_decl, 1)
    print('[PATCH] app.js: const authStatusDot replaced with appVersionBadge')
elif 'const appVersionBadge' in js_src:
    print('[SKIP] app.js: appVersionBadge const already present')
else:
    print('[WARN] app.js: const authStatusDot line not found')

# 6b. Replace the authStatusDot usage block in loadSettingsData with nothing
old_usage = (
    '      if (authStatusDot) {\n'
    '        authStatusDot.classList.toggle("offline", !isAuthed);\n'
    '      }\n'
)
if old_usage in js_src:
    js_src = js_src.replace(old_usage, '', 1)
    print('[PATCH] app.js: authStatusDot usage block removed')
elif 'authStatusDot' not in js_src:
    print('[SKIP] app.js: no authStatusDot usage found')
else:
    print('[WARN] app.js: authStatusDot usage block not matched, manual check needed')

# 6c. Add loadAppVersion() function and call it
if 'async function loadAppVersion' not in js_src:
    # Insert after loadSettingsData function declaration line
    anchor = '  async function loadSettingsData() {'
    assert anchor in js_src, 'loadSettingsData anchor not found'
    version_fn = (
        '  async function loadAppVersion() {\n'
        '    try {\n'
        '      const resp = await fetch("/api/version");\n'
        '      const data = await resp.json();\n'
        '      if (appVersionBadge && data && data.version) {\n'
        '        appVersionBadge.textContent = "v" + data.version;\n'
        '        appVersionBadge.title = "Версия Uroboros: " + data.version;\n'
        '      }\n'
        '    } catch (e) {\n'
        '      console.warn("Failed to load app version", e);\n'
        '    }\n'
        '  }\n'
        '\n'
    )
    js_src = js_src.replace(anchor, version_fn + anchor, 1)
    print('[PATCH] app.js: loadAppVersion() added')
else:
    print('[SKIP] app.js: loadAppVersion already present')

# Find where loadSettingsData is called on init and add loadAppVersion() alongside
if 'loadAppVersion();' not in js_src:
    # Try to find a call to loadSettingsData();
    m = re.search(r'(\b)(loadSettingsData\(\);)(\s*)', js_src)
    if m:
        insert_at = m.end()
        js_src = js_src[:insert_at] + '\n  loadAppVersion();' + js_src[insert_at:]
        print('[PATCH] app.js: loadAppVersion() call added after loadSettingsData()')
    else:
        # Fallback: append init at end of DOMContentLoaded or document ready
        if 'DOMContentLoaded' in js_src:
            print('[WARN] app.js: could not find loadSettingsData() call; version fetch will still run when loadSettingsData is called')
        else:
            print('[WARN] app.js: no obvious init call; please verify')
else:
    print('[SKIP] app.js: loadAppVersion() call already present')

js_path.write_text(js_src, encoding='utf-8', newline='\n')

print('\n[OK] Patch applied successfully.')
