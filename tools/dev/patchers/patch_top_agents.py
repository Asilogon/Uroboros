"""Add multi-agent selector and Mind Map action button to top bar."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
html_path = ROOT / 'deepseek_gui' / 'templates' / 'index.html'
css_path = ROOT / 'deepseek_gui' / 'static' / 'css' / 'style.css'
js_path = ROOT / 'deepseek_gui' / 'static' / 'js' / 'app.js'

# ==========================================================
# 1. INDEX.HTML
# ==========================================================
html = html_path.read_text(encoding='utf-8')

old_block = '    <!-- RIGHT: CLEAN TOP BAR -->\n    <div class="top-bar-right"></div>\n'
if 'id="topAgentsDropdown"' in html:
    print('[SKIP] index.html: already patched')
else:
    if old_block not in html:
        raise SystemExit('[ERROR] index.html: top-bar-right block not found')
    new_block = '''    <!-- RIGHT: TOP BAR - AGENTS SELECTOR + MIND MAP ACTION -->
    <div class="top-bar-right">
      <!-- Multi-select agents dropdown -->
      <div class="top-agents-dropdown" id="topAgentsDropdown">
        <button class="top-agents-trigger" id="topAgentsDropdownBtn" title="Выбрать агентов для отображения">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
          <span class="top-agents-trigger-label">Агенты</span>
          <span class="top-agents-count" id="topAgentsCount">0</span>
          <svg class="top-agents-caret" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
        <div class="top-agents-panel" id="topAgentsPanel" style="display: none;">
          <div class="top-agents-panel-header">
            <span>Выбор агентов</span>
            <div class="top-agents-panel-actions">
              <button type="button" class="top-agents-mini-btn" id="topAgentsSelectAll">Все</button>
              <button type="button" class="top-agents-mini-btn" id="topAgentsSelectNone">Сброс</button>
            </div>
          </div>
          <div class="top-agents-list" id="topAgentsList">
            <div class="top-agents-empty">Нет активного проекта</div>
          </div>
        </div>
      </div>

      <!-- Mind Map action button -->
      <button class="top-mindmap-action-btn" id="topBtnMindMapAction" title="Открыть Mind Map по выбранным агентам">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"/>
          <circle cx="5" cy="6" r="2.5"/>
          <circle cx="19" cy="6" r="2.5"/>
          <circle cx="5" cy="18" r="2.5"/>
          <circle cx="19" cy="18" r="2.5"/>
          <line x1="7" y1="8" x2="10" y2="10.5"/>
          <line x1="17" y1="8" x2="14" y2="10.5"/>
          <line x1="7" y1="16" x2="10" y2="13.5"/>
          <line x1="17" y1="16" x2="14" y2="13.5"/>
        </svg>
        <span>Mind Map</span>
      </button>
    </div>
'''
    html = html.replace(old_block, new_block, 1)
    html_path.write_text(html, encoding='utf-8', newline='\n')
    print('[PATCH] index.html: top bar right extended')

# ==========================================================
# 2. STYLE.CSS
# ==========================================================
css = css_path.read_text(encoding='utf-8')

if '.top-agents-dropdown' in css:
    print('[SKIP] style.css: already patched')
else:
    # Append at end of file (safe — new selectors, no conflicts)
    css_add = '''

/* =====================================================================
   TOP BAR: MULTI-AGENTS SELECTOR + MIND MAP ACTION
   ===================================================================== */
.top-bar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.top-agents-dropdown {
  position: relative;
}

.top-agents-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 5px;
  color: var(--text-muted);
  font-family: inherit;
  font-size: 11.5px;
  padding: 4px 9px;
  cursor: pointer;
  transition: all 0.12s ease;
}

.top-agents-trigger:hover {
  color: var(--text-main);
  border-color: var(--border-light);
  background-color: var(--border-subtle);
}

.top-agents-trigger.open {
  color: var(--text-main);
  border-color: var(--border-light);
  background-color: var(--border-subtle);
}

.top-agents-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 15px;
  padding: 0 4px;
  border-radius: 8px;
  background-color: var(--accent-primary);
  color: #fff;
  font-size: 9.5px;
  font-weight: 700;
  line-height: 1;
}

.top-agents-count.zero {
  background-color: var(--badge-bg);
  color: var(--text-dim);
}

.top-agents-caret {
  transition: transform 0.15s ease;
}

.top-agents-trigger.open .top-agents-caret {
  transform: rotate(180deg);
}

.top-agents-panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 260px;
  max-height: 360px;
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
  z-index: 500;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.top-agents-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border-color);
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 600;
}

.top-agents-panel-actions {
  display: flex;
  gap: 6px;
}

.top-agents-mini-btn {
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-muted);
  font-family: inherit;
  font-size: 10.5px;
  padding: 2px 7px;
  cursor: pointer;
  transition: all 0.12s ease;
}

.top-agents-mini-btn:hover {
  color: var(--text-main);
  border-color: var(--border-light);
}

.top-agents-list {
  overflow-y: auto;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.top-agents-empty {
  padding: 18px 10px;
  text-align: center;
  color: var(--text-dim);
  font-size: 11.5px;
}

.top-agent-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 5px;
  cursor: pointer;
  transition: background-color 0.12s ease;
}

.top-agent-row:hover {
  background-color: var(--border-subtle);
}

.top-agent-row input[type="checkbox"] {
  accent-color: var(--accent-primary);
  margin: 0;
  flex-shrink: 0;
}

.top-agent-row .top-agent-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.top-agent-row .top-agent-info {
  min-width: 0;
  flex: 1;
}

.top-agent-row .top-agent-name {
  font-size: 11.5px;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.top-agent-row .top-agent-role {
  font-size: 10px;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.top-agent-row.is-lead .top-agent-name::after {
  content: " (лид)";
  color: var(--text-dim);
  font-size: 9.5px;
  font-weight: normal;
}

.top-mindmap-action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 5px;
  color: var(--text-muted);
  font-family: inherit;
  font-size: 11.5px;
  padding: 4px 10px;
  cursor: pointer;
  transition: all 0.12s ease;
}

.top-mindmap-action-btn:hover {
  color: var(--text-main);
  border-color: var(--border-light);
  background-color: var(--border-subtle);
}
'''
    css = css.rstrip() + css_add
    css_path.write_text(css, encoding='utf-8', newline='\n')
    print('[PATCH] style.css: top bar styles appended')

print('[DONE] HTML + CSS updated')
