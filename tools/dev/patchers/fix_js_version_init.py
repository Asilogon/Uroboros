"""Fix JS init placement for loadAppVersion and clean glued line."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
js_path = ROOT / 'deepseek_gui' / 'static' / 'js' / 'app.js'
src = js_path.read_text(encoding='utf-8')

# 1. Fix the glued line inside openSettings
bad = (
    '  function openSettings() {\n'
    '    loadSettingsData();\n'
    '    \n'
    '  loadAppVersion();settingsModal.style.display = "flex";\n'
    '  }\n'
)
good = (
    '  function openSettings() {\n'
    '    loadSettingsData();\n'
    '    settingsModal.style.display = "flex";\n'
    '  }\n'
)
if bad in src:
    src = src.replace(bad, good, 1)
    print('[FIX] cleaned glued openSettings body')
else:
    print('[WARN] openSettings glued pattern not matched, trying looser fix')
    # looser: replace just the glued line
    if 'loadAppVersion();settingsModal.style.display = "flex";' in src:
        src = src.replace(
            '  loadAppVersion();settingsModal.style.display = "flex";',
            '    settingsModal.style.display = "flex";',
            1,
        )
        print('[FIX] glued line replaced (loose)')

# 2. Ensure loadAppVersion() is called at app init (once)
# Find a spot where loadSettingsData() is called outside openSettings — typically on DOM ready / init block
# Look for a standalone call like: loadSettingsData(); (not inside function openSettings)
# We'll add loadAppVersion() once near the global initialization section if not already there.
if "\n  loadAppVersion();" not in src and "loadAppVersion();\n" not in src:
    # Strategy: find 'if (btnOpenSettings) btnOpenSettings.addEventListener("click", openSettings);'
    # and add an init call just after the last 'addEventListener("click", openSettings)' block
    anchor_marker = 'if (btnCloseSettings) btnCloseSettings.addEventListener("click", closeSettings);'
    if anchor_marker in src:
        # Insert after this line an explicit init call
        idx = src.index(anchor_marker) + len(anchor_marker)
        # find end of line
        nl = src.index('\n', idx)
        insert = '\n  loadAppVersion();'
        src = src[:nl] + insert + src[nl:]
        print('[ADD] loadAppVersion() called once during init (after closeSettings listener)')
    else:
        print('[WARN] init anchor not found, adding to end of file')
        src += '\n// Load version badge at startup\nloadAppVersion();\n'
else:
    print('[SKIP] loadAppVersion() already invoked outside openSettings (or within, verify manually)')

js_path.write_text(src, encoding='utf-8', newline='\n')
print('[OK] JS init fixed')
