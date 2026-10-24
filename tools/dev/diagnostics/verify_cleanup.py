"""Verify all references to removed features are gone."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

checks = [
    ('deepseek_gui/templates/index.html', [
        'top-agents',
        'topBtnMindMapAction',
        'btnGoToMindMap',
        'topAgentsDropdown',
        'topAgentsPanel',
    ]),
    ('deepseek_gui/static/js/app.js', [
        'topAgents',
        'selectedAgentIds',
        'btnGoToMindMap',
        'renderTopAgentsSelector',
        'topBtnMindMapAction',
        '_displaySubagents',
        '_refreshInSelectProject',
        '_emptyStateClearSelector',
    ]),
    ('deepseek_gui/static/css/style.css', [
        '.top-agents',
        '.top-mindmap-action-btn',
        'TOP BAR: MULTI-AGENTS',
    ]),
]

all_ok = True
for path_str, patterns in checks:
    p = ROOT / path_str
    content = p.read_text(encoding='utf-8')
    print(f'\n=== {path_str} ===')
    for pat in patterns:
        count = content.count(pat)
        status = 'OK' if count == 0 else 'LEFTOVER'
        if count != 0:
            all_ok = False
        print(f'  {status:9} "{pat}": {count}')

# Also verify the top-bar-right is back to clean form
idx = (ROOT / 'deepseek_gui/templates/index.html').read_text(encoding='utf-8')
clean_form = '<div class="top-bar-right"></div>'
if clean_form in idx:
    print(f'\n[OK] top-bar-right restored to clean form')
else:
    print(f'\n[WARN] top-bar-right not in expected clean form')
    all_ok = False

# Verify btnGoToMindMap block removed entirely (no dangling button)
if 'id="btnGoToMindMap"' in idx:
    print('[WARN] btnGoToMindMap id still present')
    all_ok = False
else:
    print('[OK] btnGoToMindMap fully removed')

print('\n' + ('ALL OK' if all_ok else 'SOME LEFTOVERS — check above'))
