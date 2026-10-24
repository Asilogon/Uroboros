"""Add multi-agent selector logic + Mind Map action handler to app.js."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
js_path = ROOT / 'deepseek_gui' / 'static' / 'js' / 'app.js'

js = js_path.read_text(encoding='utf-8')

# ---------- 1. DOM refs + state ----------
anchor1 = '  const btnGoToMindMap = document.getElementById("btnGoToMindMap");'
if 'topAgentsDropdownBtn' in js:
    print('[SKIP] DOM refs already present')
else:
    assert anchor1 in js, 'DOM refs anchor not found'
    new_refs = anchor1 + '''

  // DOM Elements - Top Bar: Agents selector + Mind Map button
  const topAgentsDropdown = document.getElementById("topAgentsDropdown");
  const topAgentsDropdownBtn = document.getElementById("topAgentsDropdownBtn");
  const topAgentsPanel = document.getElementById("topAgentsPanel");
  const topAgentsList = document.getElementById("topAgentsList");
  const topAgentsCount = document.getElementById("topAgentsCount");
  const topAgentsSelectAll = document.getElementById("topAgentsSelectAll");
  const topAgentsSelectNone = document.getElementById("topAgentsSelectNone");
  const topBtnMindMapAction = document.getElementById("topBtnMindMapAction");

  // State: selected agents (empty Set = show all)
  let selectedAgentIds = new Set();'''
    js = js.replace(anchor1, new_refs, 1)
    print('[PATCH] DOM refs + state inserted')

# ---------- 2. renderTopAgentsSelector function + handlers ----------
anchor2 = '  if (btnGoToMindMap) btnGoToMindMap.addEventListener("click", () => switchView("mindmap"));'
if 'function renderTopAgentsSelector' in js:
    print('[SKIP] renderTopAgentsSelector already present')
else:
    assert anchor2 in js, 'handlers anchor not found'
    new_block = anchor2 + '''

  // ===================================================================
  // 3b. TOP BAR: AGENTS MULTI-SELECTOR + MIND MAP BUTTON
  // ===================================================================
  function renderTopAgentsSelector() {
    if (!topAgentsList) return;
    topAgentsList.innerHTML = "";

    if (!activeProjectData) {
      topAgentsList.innerHTML = '<div class="top-agents-empty">Нет активного проекта</div>';
      updateTopAgentsCount();
      return;
    }

    const lead = activeProjectData.lead_agent || null;
    const subagents = activeProjectData.subagents || [];
    const allAgents = [];
    if (lead && lead.id) {
      allAgents.push({ id: lead.id, name: lead.name || "Лид", role: lead.role || "", icon: lead.icon || "👤", isLead: true });
    }
    subagents.forEach((a) => {
      allAgents.push({ id: a.id, name: a.name || "Агент", role: a.role || "", icon: a.icon || "🤖", isLead: false });
    });

    // Drop selectedAgentIds entries that no longer exist in project
    const validIds = new Set(allAgents.map((a) => a.id));
    Array.from(selectedAgentIds).forEach((id) => {
      if (!validIds.has(id)) selectedAgentIds.delete(id);
    });

    if (allAgents.length === 0) {
      topAgentsList.innerHTML = '<div class="top-agents-empty">В проекте нет агентов</div>';
      updateTopAgentsCount();
      return;
    }

    allAgents.forEach((agent) => {
      const row = document.createElement("label");
      row.className = "top-agent-row" + (agent.isLead ? " is-lead" : "");
      row.setAttribute("data-agent-id", agent.id);

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = selectedAgentIds.has(agent.id);
      cb.addEventListener("change", () => {
        if (cb.checked) selectedAgentIds.add(agent.id);
        else selectedAgentIds.delete(agent.id);
        updateTopAgentsCount();
      });

      const iconSpan = document.createElement("span");
      iconSpan.className = "top-agent-icon";
      iconSpan.textContent = agent.icon;

      const info = document.createElement("span");
      info.className = "top-agent-info";
      const nameDiv = document.createElement("div");
      nameDiv.className = "top-agent-name";
      nameDiv.textContent = agent.name;
      const roleDiv = document.createElement("div");
      roleDiv.className = "top-agent-role";
      roleDiv.textContent = agent.role || "";
      info.appendChild(nameDiv);
      info.appendChild(roleDiv);

      row.appendChild(cb);
      row.appendChild(iconSpan);
      row.appendChild(info);

      row.addEventListener("click", (e) => {
        // Prevent double-toggle when clicking directly on checkbox
        if (e.target === cb) return;
        e.preventDefault();
        cb.checked = !cb.checked;
        if (cb.checked) selectedAgentIds.add(agent.id);
        else selectedAgentIds.delete(agent.id);
        updateTopAgentsCount();
      });

      topAgentsList.appendChild(row);
    });

    updateTopAgentsCount();
  }

  function updateTopAgentsCount() {
    if (!topAgentsCount) return;
    const n = selectedAgentIds.size;
    topAgentsCount.textContent = String(n);
    topAgentsCount.classList.toggle("zero", n === 0);
  }

  function openTopAgentsPanel() {
    if (!topAgentsPanel || !topAgentsDropdownBtn) return;
    topAgentsPanel.style.display = "flex";
    topAgentsDropdownBtn.classList.add("open");
  }

  function closeTopAgentsPanel() {
    if (!topAgentsPanel || !topAgentsDropdownBtn) return;
    topAgentsPanel.style.display = "none";
    topAgentsDropdownBtn.classList.remove("open");
  }

  function toggleTopAgentsPanel() {
    if (!topAgentsPanel) return;
    if (topAgentsPanel.style.display === "flex") closeTopAgentsPanel();
    else openTopAgentsPanel();
  }

  if (topAgentsDropdownBtn) {
    topAgentsDropdownBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleTopAgentsPanel();
    });
  }

  // Close panel on outside click
  document.addEventListener("click", (e) => {
    if (!topAgentsDropdown) return;
    if (!topAgentsDropdown.contains(e.target)) closeTopAgentsPanel();
  });

  if (topAgentsSelectAll) {
    topAgentsSelectAll.addEventListener("click", () => {
      if (!activeProjectData) return;
      const lead = activeProjectData.lead_agent;
      const subs = activeProjectData.subagents || [];
      if (lead && lead.id) selectedAgentIds.add(lead.id);
      subs.forEach((a) => selectedAgentIds.add(a.id));
      renderTopAgentsSelector();
    });
  }

  if (topAgentsSelectNone) {
    topAgentsSelectNone.addEventListener("click", () => {
      selectedAgentIds.clear();
      renderTopAgentsSelector();
    });
  }

  if (topBtnMindMapAction) {
    topBtnMindMapAction.addEventListener("click", () => {
      closeTopAgentsPanel();
      switchView("mindmap");
    });
  }'''
    js = js.replace(anchor2, new_block, 1)
    print('[PATCH] renderTopAgentsSelector + handlers inserted')

# ---------- 3. Filter subagents in renderMindMap ----------
old_filter = '      subagents.forEach((agent) => {'
new_filter = '      const _filteredSubagents = (selectedAgentIds.size === 0) ? subagents : subagents.filter((a) => selectedAgentIds.has(a.id));\n      _filteredSubagents.forEach((agent) => {'
if 'const _filteredSubagents' in js:
    print('[SKIP] renderMindMap filter already present')
else:
    if old_filter in js:
        js = js.replace(old_filter, new_filter, 1)
        print('[PATCH] renderMindMap subagents filter added')
    else:
        print('[WARN] renderMindMap subagents.forEach not found')

# Also fix the empty-check inside renderMindMap to account for filter
old_empty_check = '    if (subagents.length === 0) {'
new_empty_check = '    const _displaySubagents = (selectedAgentIds.size === 0) ? subagents : subagents.filter((a) => selectedAgentIds.has(a.id));\n    if (_displaySubagents.length === 0) {'
if '_displaySubagents' in js:
    print('[SKIP] empty-check already updated')
else:
    if old_empty_check in js:
        js = js.replace(old_empty_check, new_empty_check, 1)
        print('[PATCH] renderMindMap empty-check updated')
    else:
        print('[WARN] renderMindMap empty-check not found')

# Reuse _displaySubagents instead of _filteredSubagents — actually keep _displaySubagents for both.
# Replace 'const _filteredSubagents = ...' line to reference _displaySubagents for consistency.
js = js.replace(
    '      const _filteredSubagents = (selectedAgentIds.size === 0) ? subagents : subagents.filter((a) => selectedAgentIds.has(a.id));\n      _filteredSubagents.forEach((agent) => {',
    '      _displaySubagents.forEach((agent) => {',
    1,
)

# ---------- 4. Refresh selector in selectProject ----------
anchor4 = '      activeProjectData = data.project;'
if 'renderTopAgentsSelector();' in js and '_refreshInSelectProject' in js:
    print('[SKIP] selectProject refresh already present')
else:
    if anchor4 in js:
        js = js.replace(
            anchor4,
            anchor4 + '\n      // _refreshInSelectProject\n      selectedAgentIds.clear();\n      renderTopAgentsSelector();',
            1,
        )
        print('[PATCH] selectProject: refresh selector added')
    else:
        print('[WARN] selectProject anchor not found')

# ---------- 5. Clear selector in empty state ----------
if 'function renderEmptyProjectState' in js:
    # Insert cleanup at start of function body (right after opening brace)
    old_open = '  function renderEmptyProjectState() {'
    new_open = '  function renderEmptyProjectState() {\n    // _emptyStateClearSelector\n    selectedAgentIds.clear();\n    renderTopAgentsSelector();'
    if '_emptyStateClearSelector' in js:
        print('[SKIP] empty state cleanup already present')
    else:
        if old_open in js:
            js = js.replace(old_open, new_open, 1)
            print('[PATCH] renderEmptyProjectState: cleanup added')
        else:
            print('[WARN] renderEmptyProjectState not found')

# ---------- 6. Initial render after app init ----------
if 'renderTopAgentsSelector();' in js:
    print('[INFO] renderTopAgentsSelector has call sites: OK')

js_path.write_text(js, encoding='utf-8', newline='\n')
print('[DONE] app.js updated')
print('Size:', js_path.stat().st_size, 'bytes')
