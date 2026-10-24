/**
 * Uroboros - Multi-Agent Studio & DeepSeek Reverse API Client
 * Strict Minimalist Design System with Light/Dark Themes and Zero Mock Projects.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Global State
  let activeProjectId = null;
  let activeProjectData = null;
  let activeView = "chat"; // "chat" | "mindmap"
  let isGenerating = false;
  let activeAbortController = null;
  let thinkingEnabled = false;
  let currentModel = "DeepSeek-V3";
  let attachedFiles = [];

  // Persistent in-flight generation tracker across chat switching
  let activeGeneration = {
    isGenerating: false,
    projectId: null,
    chatType: null, // "lead" | "subagent"
    subagentId: null,
    promptText: "",
    rawAccumulatedText: "",
    liveSteps: [],
    currentStatusText: "Готов к работе",
    activeAgentName: "",
    activeAgentIcon: "",
    startTime: null,
    timerInterval: null,
    userCardEl: null,
    assistantCardEl: null,
    treeContainerEl: null,
    mdBodyEl: null,
    footerEl: null,
  };

  function updateLiveActivity(statusText, agentName, agentIcon, isWorking, newStep = null) {
    activeGeneration.currentStatusText = statusText || activeGeneration.currentStatusText;
    if (agentName) activeGeneration.activeAgentName = agentName;
    if (agentIcon) activeGeneration.activeAgentIcon = agentIcon;

    const panel = document.getElementById("liveActivityPanel");
    const pulse = document.getElementById("liveActivityPulse");
    const badge = document.getElementById("liveActivityStatusBadge");
    const heroIcon = document.getElementById("liveHeroAgentIcon");
    const heroName = document.getElementById("liveHeroAgentName");
    const heroAction = document.getElementById("liveHeroAgentAction");
    const timerRow = document.getElementById("liveActivityTimerRow");
    const timerVal = document.getElementById("liveActivityTimer");
    const tabPulse = document.getElementById("tabAgentsPulseBadge");
    const miniFeed = document.getElementById("liveActivityStepsFeed");

    if (isWorking) {
      if (panel) panel.classList.add("is-active");
      if (pulse) pulse.classList.add("pulse");
      if (badge) {
        badge.className = "activity-badge working";
        badge.textContent = "В РАБОТЕ";
      }
      if (tabPulse) tabPulse.style.display = "inline-block";
      if (heroIcon) heroIcon.textContent = activeGeneration.activeAgentIcon || "⚡";
      if (heroName) heroName.textContent = activeGeneration.activeAgentName || "Агент";
      if (heroAction) heroAction.textContent = statusText || "Выполняется задача...";
      if (timerRow) timerRow.style.display = "flex";

      if (!activeGeneration.timerInterval && activeGeneration.startTime) {
        activeGeneration.timerInterval = setInterval(() => {
          if (!activeGeneration.isGenerating) {
            clearInterval(activeGeneration.timerInterval);
            activeGeneration.timerInterval = null;
            return;
          }
          const elapsedSec = Math.floor((Date.now() - activeGeneration.startTime) / 1000);
          const m = String(Math.floor(elapsedSec / 60)).padStart(2, "0");
          const s = String(elapsedSec % 60).padStart(2, "0");
          if (timerVal) timerVal.textContent = `${m}:${s}`;
        }, 1000);
      }

      if (newStep && miniFeed) {
        miniFeed.style.display = "flex";
        const stepEl = document.createElement("div");
        stepEl.className = "mini-step-item";
        let icon = "⚡";
        let text = newStep.title || "Действие";
        if (newStep.category === "file") {
          icon = "📁";
          text = `Создан ${newStep.file_path || ""}`;
        } else if (newStep.category === "file_read") {
          icon = "📄";
          text = `Прочитан ${newStep.file_path || ""}`;
        } else if (newStep.category === "cmd") {
          icon = "💻";
          text = `CMD: ${newStep.command || ""}`;
        } else if (newStep.category === "subagent") {
          icon = newStep.agent_icon || "🤖";
          text = `${newStep.agent_name || "Субагент"}: ${newStep.task || ""}`;
        } else if (newStep.category === "thought") {
          icon = "💭";
          text = "Рассуждения DeepThink";
        }
        const timeNow = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        stepEl.innerHTML = `
          <span class="mini-step-icon">${icon}</span>
          <span class="mini-step-text" title="${escapeHtml(text)}">${escapeHtml(text)}</span>
          <span class="mini-step-time">${timeNow}</span>
        `;
        miniFeed.appendChild(stepEl);
        while (miniFeed.children.length > 7) {
          miniFeed.removeChild(miniFeed.firstChild);
        }
        miniFeed.scrollTop = miniFeed.scrollHeight;
      }
    } else {
      if (panel) panel.classList.remove("is-active");
      if (pulse) pulse.classList.remove("pulse");
      if (badge) {
        badge.className = "activity-badge idle";
        badge.textContent = "ОЖИДАНИЕ";
      }
      if (tabPulse) tabPulse.style.display = "none";
      if (heroIcon) heroIcon.textContent = "🧠";
      if (heroName) heroName.textContent = "Все задачи завершены";
      if (heroAction) heroAction.textContent = statusText || "Команда готова к новым поручениям";
      if (timerRow) timerRow.style.display = "none";
      if (activeGeneration.timerInterval) {
        clearInterval(activeGeneration.timerInterval);
        activeGeneration.timerInterval = null;
      }
    }

    renderRightPanelAgentsAndTasks();
  }

  // DOM Elements - Top Bar & Tabs
  const tabBtnLeadChat = document.getElementById("tabBtnLeadChat");
  const tabBtnMindMap = document.getElementById("tabBtnMindMap");
  const viewLeadChat = document.getElementById("viewLeadChat");
  const viewMindMap = document.getElementById("viewMindMap");
  const topActiveProjectPill = document.getElementById("topActiveProjectPill");
  const topProjName = document.getElementById("topProjName");
  const topAuthStatusDot = document.getElementById("topAuthStatusDot");
  const appVersionBadge = document.getElementById("appVersionBadge");
  const btnThemeToggle = document.getElementById("btnThemeToggle");
  const themeLabelText = document.getElementById("themeLabelText");

  // DOM Elements - Projects
  const projectsList = document.getElementById("projectsList");
  const projectCountBadge = document.getElementById("projectCountBadge");
  const btnOpenNewProjectModal = document.getElementById("btnOpenNewProjectModal");
  const modalNewProject = document.getElementById("modalNewProject");
  const btnCloseNewProjectModal = document.getElementById("btnCloseNewProjectModal");
  const btnCancelNewProject = document.getElementById("btnCancelNewProject");
  const btnSubmitNewProject = document.getElementById("btnSubmitNewProject");
  const newProjectNameInput = document.getElementById("newProjectNameInput");
  const modeCardMulti = document.getElementById("modeCardMulti");
  const modeCardSolo = document.getElementById("modeCardSolo");
  let selectedNewProjectMode = "multi";

  // DOM Elements - Lead Chat
  const breadProjectName = document.getElementById("breadProjectName");
  const breadLeadName = document.getElementById("breadLeadName");
  const leadSubagentsCount = document.getElementById("leadSubagentsCount");
  const messagesContainer = document.getElementById("messagesContainer");
  const chatPromptInput = document.getElementById("chatPromptInput");
  const btnSendMessage = document.getElementById("btnSendMessage");
  const btnAttachFile = document.getElementById("btnAttachFile");
  const hiddenFileInput = document.getElementById("hiddenFileInput");
  const attachedChips = document.getElementById("attachedChips");
  const btnModelSelect = document.getElementById("btnModelSelect");
  const modelLabel = document.getElementById("modelLabel");
  const btnToggleReasoning = document.getElementById("btnToggleReasoning");
  const reasoningStatusLabel = document.getElementById("reasoningStatusLabel");
  const btnGoToMindMap = document.getElementById("btnGoToMindMap");

  // DOM Elements - Mind Map
  const mindmapProjectTitle = document.getElementById("mindmapProjectTitle");
  const mindmapStats = document.getElementById("mindmapStats");
  const mindMapCanvasContainer = document.getElementById("mindMapCanvasContainer");
  const mindMapSvgLayer = document.getElementById("mindMapSvgLayer");
  const mindMapNodesLayer = document.getElementById("mindMapNodesLayer");
  const btnOpenAddAgentModal = document.getElementById("btnOpenAddAgentModal");
  const btnRefreshMindMap = document.getElementById("btnRefreshMindMap");

  // DOM Elements - Subagent Modal
  const modalNewAgent = document.getElementById("modalNewAgent");
  const btnCloseNewAgentModal = document.getElementById("btnCloseNewAgentModal");
  const btnCancelNewAgent = document.getElementById("btnCancelNewAgent");
  const btnSubmitNewAgent = document.getElementById("btnSubmitNewAgent");
  const newAgentNameInput = document.getElementById("newAgentNameInput");
  const newAgentRoleInput = document.getElementById("newAgentRoleInput");
  const newAgentPromptInput = document.getElementById("newAgentPromptInput");

  // DOM Elements - Right Panel
  const rightTabBtns = document.querySelectorAll(".right-tabs-header .tab-btn");
  const tabContentAgents = document.getElementById("tabContentAgents");
  const tabContentTerminal = document.getElementById("tabContentTerminal");
  const tabContentFiles = document.getElementById("tabContentFiles");
  const rightSubagentsList = document.getElementById("rightSubagentsList");
  const rightAgentsBadge = document.getElementById("rightAgentsBadge");
  const rightTasksList = document.getElementById("rightTasksList");
  const rightTasksBadge = document.getElementById("rightTasksBadge");
  const networkLogsList = document.getElementById("networkLogsList");
  const logCountBadge = document.getElementById("logCountBadge");
  const uploadedFilesList = document.getElementById("uploadedFilesList");

  // DOM Elements - Settings
  const btnOpenSettings = document.getElementById("btnOpenSettings");
  const btnOpenSettingsTop = document.getElementById("btnOpenSettingsTop");
  const settingsModal = document.getElementById("settingsModal");
  const btnCloseSettings = document.getElementById("btnCloseSettings");
  const btnCancelSettings = document.getElementById("btnCancelSettings");
  const settingTokenInput = document.getElementById("settingTokenInput");
  const btnToggleTokenVisibility = document.getElementById("btnToggleTokenVisibility");
  const btnSaveToken = document.getElementById("btnSaveToken");
  const btnClearSession = document.getElementById("btnClearSession");
  const btnSettingsLaunchSelenium = document.getElementById("btnSettingsLaunchSelenium");
  const btnSettingsResetProfile = document.getElementById("btnSettingsResetProfile");
  const settingAuthIndicator = document.getElementById("settingAuthIndicator");
  const settingAuthText = document.getElementById("settingAuthText");
  const settingAuthSubtext = document.getElementById("settingAuthSubtext");

  // ===================================================================
  // 1. THEME SWITCHING (LIGHT & DARK THEMES)
  // ===================================================================
  function applyTheme(themeName) {
    document.documentElement.setAttribute("data-theme", themeName);
    localStorage.setItem("uroboros_theme", themeName);

    // Sync segmented buttons in Appearance tab of Settings modal
    const themeSegmented = document.getElementById("themeSegmented");
    if (themeSegmented) {
      themeSegmented.querySelectorAll(".settings-segmented-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.getAttribute("data-theme") === themeName);
      });
    }

    if (btnThemeToggle) {
      const isLight = themeName === "light";
      const iconSun = btnThemeToggle.querySelector(".icon-sun");
      const iconMoon = btnThemeToggle.querySelector(".icon-moon");
      if (iconSun && iconMoon) {
        iconSun.style.display = isLight ? "none" : "block";
        iconMoon.style.display = isLight ? "block" : "none";
      }
      if (themeLabelText) {
        themeLabelText.textContent = isLight ? "Темная" : "Светлая";
      }
    }

    // Inform backend to update Windows native titlebar theme
    fetch("/api/theme", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme: themeName }),
    }).catch(() => {});
  }

  const savedTheme = localStorage.getItem("uroboros_theme") || "dark";
  applyTheme(savedTheme);

  // Wire up theme buttons in Settings Appearance tab
  const themeSegmented = document.getElementById("themeSegmented");
  if (themeSegmented) {
    themeSegmented.querySelectorAll(".settings-segmented-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const theme = btn.getAttribute("data-theme");
        if (theme) applyTheme(theme);
      });
    });
  }

  if (btnThemeToggle) {
    btnThemeToggle.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "dark";
      const next = current === "dark" ? "light" : "dark";
      applyTheme(next);
    });
  }

  // ===================================================================
  // 2. MARKDOWN RENDERING
  // ===================================================================
  function renderMarkdown(text) {
    if (!text) return "";
    if (window.marked) {
      try {
        return window.marked.parse(text);
      } catch (e) {
        console.warn("Marked error:", e);
      }
    }
    return text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\n/g, "<br>");
  }

  // ===================================================================
  // 3. VIEW SWITCHING (CHAT vs MIND MAP)
  // ===================================================================
  function switchView(viewName) {
    activeView = viewName;
    if (viewName === "chat") {
      tabBtnLeadChat.classList.add("active");
      tabBtnMindMap.classList.remove("active");
      viewLeadChat.style.display = "flex";
      viewMindMap.style.display = "none";
    } else {
      tabBtnMindMap.classList.add("active");
      tabBtnLeadChat.classList.remove("active");
      viewMindMap.style.display = "flex";
      viewLeadChat.style.display = "none";
      renderMindMap();
    }
  }

  if (tabBtnLeadChat) tabBtnLeadChat.addEventListener("click", () => switchView("chat"));
  if (tabBtnMindMap) tabBtnMindMap.addEventListener("click", () => switchView("mindmap"));
  if (btnGoToMindMap) btnGoToMindMap.addEventListener("click", () => switchView("mindmap"));

  // ===================================================================
  // 4. PROJECTS MANAGEMENT (STARTS CLEAN FROM SCRATCH)
  // ===================================================================
  async function loadProjects() {
    try {
      const resp = await fetch("/api/projects");
      const data = await resp.json();
      const projects = data.projects || [];

      if (projectCountBadge) projectCountBadge.textContent = projects.length;
      projectsList.innerHTML = "";

      if (projects.length === 0) {
        projectsList.innerHTML = `
          <div style="text-align: center; color: var(--text-dim); padding: 36px 12px; font-size: 11.5px; line-height: 1.6;">
            Нет проектов.<br>Нажмите <strong>Создать проект</strong> выше, чтобы начать.
          </div>
        `;
        activeProjectId = null;
        activeProjectData = null;
        if (topActiveProjectPill) topActiveProjectPill.style.display = "none";
        renderEmptyProjectState();
        return;
      }

      projects.forEach((proj, idx) => {
        const item = document.createElement("div");
        item.className = "project-card-item" + (proj.id === activeProjectId ? " active" : "");
        item.setAttribute("data-id", proj.id);

        const isSolo = proj.mode === "solo";
        const modeBadge = isSolo
          ? `<span class="project-mode-badge solo" title="Режим: один агент всё делает самостоятельно">⚡ Соло</span>`
          : `<span class="project-mode-badge multi" title="Режим: супер-агент с субагентами">👥 Команда</span>`;

        item.innerHTML = `
          <div class="project-card-top">
            <span class="project-card-title">${escapeHtml(proj.name)}</span>
            <button class="project-delete-btn" title="Удалить проект">&#10005;</button>
          </div>
          <div class="project-card-meta">
            ${modeBadge}
            <span>${isSolo ? "1 агент" : `${proj.subagents_count || 0} суб.`}</span>
            <span>${proj.created_at || ""}</span>
          </div>
        `;

        item.addEventListener("click", (e) => {
          if (e.target.classList.contains("project-delete-btn")) return;
          selectProject(proj.id);
        });

        item.querySelector(".project-delete-btn").addEventListener("click", (e) => {
          e.stopPropagation();
          deleteProject(proj.id);
        });

        projectsList.appendChild(item);

        if (!activeProjectId && idx === 0) {
          selectProject(proj.id);
        }
      });
    } catch (e) {
      console.warn("Failed loading projects:", e);
    }
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/[&<>"']/g, (m) => {
      switch (m) {
        case "&": return "&amp;";
        case "<": return "&lt;";
        case ">": return "&gt;";
        case '"': return "&quot;";
        case "'": return "&#39;";
        default: return m;
      }
    });
  }

  function renderEmptyProjectState() {
    if (topActiveProjectPill) topActiveProjectPill.style.display = "none";
    if (breadProjectName) breadProjectName.textContent = "Проект не выбран";
    if (breadLeadName) breadLeadName.textContent = "Руководитель проекта";
    if (leadSubagentsCount) leadSubagentsCount.textContent = "0 субагентов";

    messagesContainer.innerHTML = `
      <div id="emptyFeedState" class="empty-feed-card">
        <div class="empty-title">Нет активного проекта</div>
        <p class="empty-subtitle">
          Создайте новый проект в боковой панели слева, чтобы начать диалог с Руководителем и координировать субагентов.
        </p>
      </div>
    `;

    if (rightSubagentsList) rightSubagentsList.innerHTML = `<div class="empty-hint">Проект не выбран</div>`;
    if (rightTasksList) rightTasksList.innerHTML = `<div class="empty-hint">Нет задач</div>`;
    if (rightAgentsBadge) rightAgentsBadge.textContent = "0";
    if (rightTasksBadge) rightTasksBadge.textContent = "0";

    if (activeView === "mindmap") {
      mindMapNodesLayer.innerHTML = `
        <div style="text-align: center; color: var(--text-dim); padding: 50px 20px; font-size: 13px;">
          Нет активного проекта. Создайте проект слева, чтобы увидеть структуру команды.
        </div>
      `;
      mindMapSvgLayer.innerHTML = "";
    }
  }

  async function selectProject(projectId) {
    activeProjectId = projectId;

    document.querySelectorAll(".project-card-item").forEach((el) => {
      el.classList.toggle("active", el.getAttribute("data-id") === projectId);
    });

    try {
      const resp = await fetch(`/api/projects/${projectId}`);
      const data = await resp.json();
      if (!data.success) return;

      activeProjectData = data.project;

      // Update Top Bar Pill
      if (topActiveProjectPill) {
        topActiveProjectPill.style.display = "flex";
        if (topProjName) topProjName.textContent = activeProjectData.name;
      }

      if (breadProjectName) breadProjectName.textContent = activeProjectData.name;
      const isSolo = activeProjectData.mode === "solo";
      const lead = activeProjectData.lead_agent || {};
      const defaultLeadName = isSolo ? "Агент (соло)" : "Руководитель проекта";
      if (breadLeadName) breadLeadName.textContent = lead.name || defaultLeadName;

      // Update top header tab button text
      const topTabSpan = document.querySelector("#tabBtnLeadChat span");
      if (topTabSpan) {
        topTabSpan.textContent = isSolo ? "Чат с агентом" : "Чат с руководителем";
      }

      // Hide/Show Quick Add Subagent button in top bar based on mode
      const btnQuickAddSubagent = document.getElementById("btnQuickAddSubagent");
      if (btnQuickAddSubagent) {
        btnQuickAddSubagent.style.display = isSolo ? "none" : "inline-flex";
      }

      const breadFolder = document.getElementById("breadProjectFolder");
      if (breadFolder) {
        const rootPath = activeProjectData.root_path || "d:\\Coding\\Uroboros";
        breadFolder.textContent = `📁 ${rootPath}`;
        breadFolder.title = `Рабочая папка проекта: ${rootPath}`;
      }

      const subagents = activeProjectData.subagents || [];

      if (leadSubagentsCount) {
        leadSubagentsCount.textContent = isSolo ? "⚡ Соло (1 агент)" : `${subagents.length} субагентов`;
      }

      // Update Mindmap Title
      if (mindmapProjectTitle) mindmapProjectTitle.textContent = `Интеллектуальная карта: ${activeProjectData.name}`;
      const activeTasksCount = (activeProjectData.tasks || []).filter((t) => t.status === "active").length;
      if (mindmapStats) {
        mindmapStats.textContent = isSolo
          ? `⚡ 1 Автономный агент • ${activeTasksCount} Активных задач`
          : `🧠 1 Руководитель • ${subagents.length} Субагентов • ${activeTasksCount} Активных задач`;
      }

      // Render Chat Tabs Bar and load active chat
      renderChatAgentsNav();
      switchActiveChat(activeChatType || "lead", activeSubagentId);

      // Render Right Panel
      renderRightPanelAgentsAndTasks();

      // If in Mind Map view, re-draw
      if (activeView === "mindmap") {
        renderMindMap();
      }
    } catch (err) {
      console.error("Error selecting project:", err);
    }
  }

  async function createProject(name, rootPath = "", mode = "multi") {
    try {
      const resp = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, root_path: rootPath, mode }),
      });
      if (!resp.ok) {
        const errText = await resp.text();
        throw new Error(`Сервер вернул ошибку ${resp.status}: ${errText.slice(0, 150)}`);
      }
      const data = await resp.json();
      if (data.success) {
        await loadProjects();
        selectProject(data.project.id);
      }
    } catch (err) {
      alert("Ошибка создания проекта: " + err.message);
    }
  }

  async function deleteProject(projectId) {
    if (!confirm("Удалить этот проект и всех его субагентов?")) return;
    try {
      await fetch(`/api/projects/${projectId}`, { method: "DELETE" });
      if (activeProjectId === projectId) {
        activeProjectId = null;
      }
      loadProjects();
    } catch (err) {
      alert("Ошибка удаления проекта: " + err);
    }
  }

  // ===================================================================
  // ===================================================================
  // 5. CHAT FEED, ACTION STEPS TREE & MULTI-AGENT ORCHESTRATION
  // ===================================================================
  let activeChatType = "lead"; // "lead" | "subagent"
  let activeSubagentId = null;

  function cleanUserFacingText(text) {
    if (!text) return "";
    let clean = text
      .replace(/```(?:json)?\s*\{[\s\S]*?\}\s*```/g, "")
      .replace(/<(?:to_user|user_message)>([\s\S]*?)<\/(?:to_user|user_message)>/g, "$1")
      .replace(/<to_agent[^>]*>[\s\S]*?<\/to_agent>/g, "")
      .replace(/<spawn_agent[^>]*>[\s\S]*?<\/spawn_agent>/g, "")
      .replace(/<file_write[^>]*>[\s\S]*?<\/file_write>/g, "")
      .replace(/<file_read[^>]*>[\s\S]*?<\/file_read>/g, "")
      .replace(/<cmd>[\s\S]*?<\/cmd>/g, "")
      .replace(/\[FILE_WRITE:\s*([^\r\n\]]+)\]([\s\S]*?)\[\/FILE_WRITE\]/g, "")
      .replace(/\[FILE_WRITE:\s*[^\|\]\r\n]+\s*\|\s*[\s\S]*?\]/g, "")
      .replace(/\[FILE_READ:\s*[^\]]+\]/g, "")
      .replace(/\[CMD:\s*[^\]]+\]/g, "")
      .replace(/\[ASSIGN:\s*[^\|\]]+\s*\|\s*[^\]]+\]/g, "")
      .replace(/\[SPAWN:\s*[^\]]+\]/g, "")
      .replace(/\[DONE\]/gi, "")
      .trim();

    if (clean.startsWith("{") && clean.endsWith("}")) {
      try {
        const obj = JSON.parse(clean);
        if (obj && (obj.to_user || obj.message_to_user || obj.user_message)) {
          clean = obj.to_user || obj.message_to_user || obj.user_message;
        }
      } catch (e) {}
    }

    // Strip forbidden robotic step commentary
    clean = clean
      .replace(/^шаг\s*\d+.*?(?:завершён|выполнен|пройден|успешно)[^.\n]*[.\n]?/gim, "")
      .replace(/(?:все\s+)?действия\s+по\s+предыдущему\s+шагу[^.\n]*[.\n]?/gim, "")
      .replace(/дополнительных\s+действий\s+специалистов\s+не\s+требуется[^.\n]*[.\n]?/gim, "")
      .replace(/поскольку\s+задача[,\s]+судя\s+по\s+всему[,\s]+полностью\s+решена[^.\n]*[.\n]?/gim, "")
      .replace(/(?:принято[!,.]?\s*)?(?:передал|передаю)\s+[^.\n]+?(?:ждите\s+результат|начинаю\s+работу|приступаю)[^.\n]*[.\n]?/gim, "");

    return clean.trim();
  }

  function buildActionStepsTreeElement(steps, isRunning = false, activeTitle = "") {
    const container = document.createElement("div");
    container.className = "action-steps-tree-container";

    const header = document.createElement("div");
    header.className = "action-steps-tree-header";

    const left = document.createElement("div");
    left.className = "tree-header-left";

    if (isRunning) {
      const pulseDot = document.createElement("span");
      pulseDot.className = "tree-pulse-dot";
      left.appendChild(pulseDot);
    }

    const titleSpan = document.createElement("span");
    titleSpan.className = "tree-title";
    const stepCount = steps ? steps.length : 0;
    titleSpan.textContent = activeTitle || (isRunning ? "Выполнение задачи..." : `Действия команды (${stepCount})`);
    left.appendChild(titleSpan);

    const chevron = document.createElement("span");
    chevron.className = "tree-chevron";
    chevron.textContent = "⌄";

    header.appendChild(left);
    header.appendChild(chevron);
    container.appendChild(header);

    header.addEventListener("click", () => {
      container.classList.toggle("collapsed");
    });

    const body = document.createElement("div");
    body.className = "action-steps-tree-body";

    if (steps && steps.length > 0) {
      steps.forEach((st) => {
        const stepItem = document.createElement("div");
        stepItem.className = "action-step-item";

        const summaryRow = document.createElement("div");
        summaryRow.className = "step-summary-row";

        let iconChar = "💡";
        if (st.category === "cmd") iconChar = "$";
        else if (st.category === "spawn") iconChar = st.icon || "🤖";
        else if (st.category === "subagent") iconChar = st.agent_icon || "🤖";
        else if (st.category === "file") iconChar = "📄";
        else if (st.category === "file_read") iconChar = "📖";

        const iconSpan = document.createElement("span");
        iconSpan.className = "step-icon";
        iconSpan.textContent = iconChar;

        const labelSpan = document.createElement("span");
        labelSpan.className = "step-label";
        labelSpan.textContent = st.title || "Операция";

        summaryRow.appendChild(iconSpan);
        summaryRow.appendChild(labelSpan);

        if (st.duration) {
          const durSpan = document.createElement("span");
          durSpan.className = "step-duration";
          durSpan.textContent = st.duration;
          summaryRow.appendChild(durSpan);
        }

        const stepChevron = document.createElement("span");
        stepChevron.className = "step-chevron";
        stepChevron.textContent = "›";
        summaryRow.appendChild(stepChevron);

        stepItem.appendChild(summaryRow);

        // Detail box if expandable
        if (st.thought || st.output !== undefined || st.answer || st.category === "file" || st.category === "file_read") {
          const detailBox = document.createElement("div");
          detailBox.className = "step-detail-box";
          detailBox.style.display = "none";

          if (st.thought) {
            const tPre = document.createElement("div");
            tPre.className = "step-thought-content";
            tPre.textContent = st.thought;
            detailBox.appendChild(tPre);
          } else if (st.category === "file") {
            const fBox = document.createElement("div");
            fBox.className = "step-file-box";
            fBox.innerHTML = `
              <div><strong>Файл создан:</strong> <code>${escapeHtml(st.file_path || st.title)}</code></div>
              ${st.size !== undefined ? `<div><strong>Размер:</strong> ${st.size} байт</div>` : ""}
              ${st.full_path ? `<div><strong>Полный путь:</strong> <span style="font-size:11px;opacity:0.8;">${escapeHtml(st.full_path)}</span></div>` : ""}
            `;
            detailBox.appendChild(fBox);
          } else if (st.output !== undefined) {
            const cPre = document.createElement("pre");
            cPre.className = "step-cmd-output";
            cPre.textContent = st.output;
            detailBox.appendChild(cPre);
          } else if (st.answer) {
            const sBox = document.createElement("div");
            sBox.className = "step-subagent-box";
            if (st.task) {
              const taskDiv = document.createElement("div");
              taskDiv.className = "step-subagent-task";
              taskDiv.innerHTML = `<strong>Задача:</strong> ${escapeHtml(st.task)}`;
              sBox.appendChild(taskDiv);
            }
            const ansDiv = document.createElement("div");
            ansDiv.className = "step-subagent-ans";
            ansDiv.textContent = st.answer;
            sBox.appendChild(ansDiv);

            if (st.agent_id) {
              const openChatBtn = document.createElement("button");
              openChatBtn.className = "step-subagent-open-chat-btn";
              openChatBtn.innerHTML = `💬 Открыть чат субагента`;
              openChatBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                switchActiveChat("subagent", st.agent_id);
              });
              sBox.appendChild(openChatBtn);
            }
            detailBox.appendChild(sBox);
          }

          stepItem.appendChild(detailBox);

          summaryRow.addEventListener("click", () => {
            const isExp = stepItem.classList.toggle("expanded");
            detailBox.style.display = isExp ? "block" : "none";
          });
        }

        body.appendChild(stepItem);
      });
    }

    container.appendChild(body);
    return container;
  }

  function renderHistoryMessages(messages, authorTitle = "Руководитель проекта", authorIcon = "🧠") {
    messagesContainer.innerHTML = "";

    if (!messages || messages.length === 0) {
      messagesContainer.innerHTML = `
        <div id="emptyFeedState" class="empty-feed-card">
          <div class="empty-title">Чат: ${escapeHtml(authorTitle)}</div>
          <p class="empty-subtitle">
            Задайте вопрос или поручите задачу. Команда специалистов автономно решит её и предоставит результат.
          </p>
        </div>
      `;
      return;
    }

    for (const msg of messages) {
      if (msg.role === "USER") {
        const userCard = document.createElement("div");
        userCard.className = "message-user-card";
        userCard.textContent = msg.text;
        messagesContainer.appendChild(userCard);
      } else {
        const assistantCard = document.createElement("div");
        assistantCard.className = "message-assistant-card";

        const titleRow = document.createElement("div");
        titleRow.className = "assistant-title-row";
        titleRow.innerHTML = `<span style="font-size: 15px;">${authorIcon}</span> <span>${escapeHtml(authorTitle)}:</span>`;
        assistantCard.appendChild(titleRow);

        // Render Action Steps Tree if available
        if (msg.steps && msg.steps.length > 0) {
          const isSolo = activeProjectData?.mode === "solo";
          const treeTitle = isSolo ? `Действия агента (${msg.steps.length})` : `Действия команды (${msg.steps.length})`;
          const treeEl = buildActionStepsTreeElement(msg.steps, false, treeTitle);
          assistantCard.appendChild(treeEl);
        } else if (msg.thinking) {
          const thinkingBox = document.createElement("details");
          thinkingBox.className = "thinking-expander visible";
          thinkingBox.innerHTML = `
            <summary>Размышления (DeepThink R1)</summary>
            <div class="thinking-text">${escapeHtml(msg.thinking)}</div>
          `;
          assistantCard.appendChild(thinkingBox);
        }

        // Clean user-facing text
        const cleanContent = cleanUserFacingText(msg.text);
        const mdBody = document.createElement("div");
        mdBody.className = "markdown-body";
        mdBody.innerHTML = renderMarkdown(cleanContent || "(Задача выполнена)");
        assistantCard.appendChild(mdBody);

        const footer = document.createElement("div");
        footer.className = "message-footer";
        footer.innerHTML = `<span>${msg.time || "только что"}</span> • <span class="copy-ans">Копировать</span>`;
        footer.querySelector(".copy-ans").addEventListener("click", () => {
          navigator.clipboard.writeText(cleanContent);
        });
        assistantCard.appendChild(footer);

        messagesContainer.appendChild(assistantCard);
      }
    }

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function renderChatAgentsNav() {
    const pillsContainer = document.getElementById("chatAgentsPills");
    if (!pillsContainer || !activeProjectData) return;

    pillsContainer.innerHTML = "";

    // 1. Lead / Main Agent Pill
    const isSolo = activeProjectData.mode === "solo";
    const leadPill = document.createElement("button");
    const isLeadActive = activeChatType === "lead";
    leadPill.className = `agent-chat-pill ${isLeadActive ? "active" : ""}`;
    leadPill.id = "pillAgentLead";
    const pillIcon = isSolo ? (activeProjectData.lead_agent?.icon || "⚡") : (activeProjectData.lead_agent?.icon || "🧠");
    const pillTitle = isSolo ? (activeProjectData.lead_agent?.name || "Агент") : "Руководитель";
    const isLeadWorking = activeGeneration.isGenerating && activeGeneration.chatType === "lead" && activeGeneration.projectId === activeProjectId;
    const workingBadgeHtml = isLeadWorking ? `<span class="pill-working-badge">⚡ В работе</span>` : "";

    leadPill.innerHTML = `
      <span class="pill-icon">${pillIcon}</span>
      <span class="pill-title">${escapeHtml(pillTitle)}</span>
      ${workingBadgeHtml}
    `;
    leadPill.addEventListener("click", () => {
      switchActiveChat("lead");
    });
    pillsContainer.appendChild(leadPill);

    // 2. Subagents Pills (only in multi-agent mode)
    if (!isSolo) {
      const subagents = activeProjectData.subagents || [];
      subagents.forEach((sa) => {
        const pill = document.createElement("button");
        const isSubActive = activeChatType === "subagent" && activeSubagentId === sa.id;
        pill.className = `agent-chat-pill ${isSubActive ? "active" : ""}`;
        pill.title = `${sa.name || "Субагент"} (${sa.role || ""})`.trim();
        const isThisSubWorking = activeGeneration.isGenerating && activeGeneration.chatType === "subagent" && activeGeneration.subagentId === sa.id && activeGeneration.projectId === activeProjectId;
        const subWorkingBadgeHtml = isThisSubWorking ? `<span class="pill-working-badge">⚡ В работе</span>` : "";

        pill.innerHTML = `
          <span class="pill-icon">${sa.icon || "🤖"}</span>
          <span class="pill-title">${escapeHtml(sa.name)}</span>
          ${subWorkingBadgeHtml}
        `;
        pill.addEventListener("click", () => {
          switchActiveChat("subagent", sa.id);
        });
        pillsContainer.appendChild(pill);
      });
    }
  }

  async function switchActiveChat(type, agentId = null) {
    activeChatType = type;
    activeSubagentId = agentId;

    renderChatAgentsNav();

    if (type === "lead") {
      const isSolo = activeProjectData?.mode === "solo";
      const defaultName = isSolo ? "Автономный агент" : "Руководитель проекта";
      const defaultIcon = isSolo ? "⚡" : "🧠";
      if (breadLeadName) breadLeadName.textContent = activeProjectData?.lead_agent?.name || defaultName;
      if (chatPromptInput) {
        chatPromptInput.placeholder = isSolo
          ? "Дайте задачу автономному агенту (создать файл, написать код, запустить скрипт)..."
          : "Дайте задачу или инструкцию Руководителю проекта...";
      }
      renderHistoryMessages(
        activeProjectData?.lead_agent?.history || [],
        activeProjectData?.lead_agent?.name || defaultName,
        activeProjectData?.lead_agent?.icon || defaultIcon
      );
    } else {
      const targetSubagent = (activeProjectData?.subagents || []).find((a) => a.id === agentId);
      if (!targetSubagent) return;
      if (breadLeadName) breadLeadName.textContent = `${targetSubagent.icon || "🤖"} ${targetSubagent.name} (${targetSubagent.role})`;
      if (chatPromptInput) chatPromptInput.placeholder = `Сообщение для субагента ${targetSubagent.name}...`;

      try {
        const resp = await fetch(`/api/projects/${activeProjectId}/agents/${agentId}/history`);
        const data = await resp.json();
        if (data.success) {
          targetSubagent.history = data.messages || [];
          renderHistoryMessages(data.messages || [], targetSubagent.name, targetSubagent.icon || "🤖");
        } else {
          renderHistoryMessages(targetSubagent.history || [], targetSubagent.name, targetSubagent.icon || "🤖");
        }
      } catch (e) {
        renderHistoryMessages(targetSubagent.history || [], targetSubagent.name, targetSubagent.icon || "🤖");
      }
    }

    // CHECK IF ACTIVE GENERATION IS CURRENTLY RUNNING!
    if (activeGeneration.isGenerating) {
      if (activeGeneration.projectId === activeProjectId) {
        if (activeGeneration.chatType === type && activeGeneration.subagentId === agentId) {
          // User switched TO the chat that is currently generating
          const emptyState = document.getElementById("emptyFeedState");
          if (emptyState) emptyState.remove();

          if (activeGeneration.userCardEl && !messagesContainer.contains(activeGeneration.userCardEl)) {
            messagesContainer.appendChild(activeGeneration.userCardEl);
          }
          if (activeGeneration.assistantCardEl && !messagesContainer.contains(activeGeneration.assistantCardEl)) {
            messagesContainer.appendChild(activeGeneration.assistantCardEl);
          }
          messagesContainer.scrollTop = messagesContainer.scrollHeight;
        } else {
          // User switched to a DIFFERENT chat while generation is running in background
          const existingBanner = messagesContainer.querySelector(".bg-generation-banner");
          if (existingBanner) existingBanner.remove();

          const banner = document.createElement("div");
          banner.className = "bg-generation-banner";
          banner.innerHTML = `
            <div class="bg-banner-left">
              <span class="live-activity-pulse-dot pulse"></span>
              <span>Сейчас в чате <strong>${escapeHtml(activeGeneration.activeAgentName)}</strong> выполняется задача: <em>${escapeHtml(activeGeneration.currentStatusText)}</em></span>
            </div>
            <button class="bg-banner-btn" id="btnJumpToActiveChat">Перейти в чат (${escapeHtml(activeGeneration.activeAgentName)})</button>
          `;
          banner.querySelector("#btnJumpToActiveChat").addEventListener("click", () => {
            switchActiveChat(activeGeneration.chatType, activeGeneration.subagentId);
          });
          messagesContainer.insertBefore(banner, messagesContainer.firstChild);
        }
      } else {
        // User switched to a DIFFERENT project while generation is running
        const existingBanner = messagesContainer.querySelector(".bg-generation-banner");
        if (existingBanner) existingBanner.remove();

        const banner = document.createElement("div");
        banner.className = "bg-generation-banner";
        banner.innerHTML = `
          <div class="bg-banner-left">
            <span class="live-activity-pulse-dot pulse"></span>
            <span>В проекте <strong>${escapeHtml(activeGeneration.activeProjectName || "активном")}</strong> агент <strong>${escapeHtml(activeGeneration.activeAgentName)}</strong> выполняет задачу: <em>${escapeHtml(activeGeneration.currentStatusText)}</em></span>
          </div>
          <button class="bg-banner-btn" id="btnJumpToActiveProject">Перейти в проект</button>
        `;
        banner.querySelector("#btnJumpToActiveProject").addEventListener("click", () => {
          selectProject(activeGeneration.projectId);
        });
        messagesContainer.insertBefore(banner, messagesContainer.firstChild);
      }
    }

    if (activeView !== "chat") {
      switchView("chat");
    }

    renderRightPanelAgentsAndTasks();
  }

  const btnQuickAddSubagent = document.getElementById("btnQuickAddSubagent");
  if (btnQuickAddSubagent) {
    btnQuickAddSubagent.addEventListener("click", () => {
      const modal = document.getElementById("modalNewAgent");
      if (modal) modal.style.display = "flex";
    });
  }

  // ===================================================================
  // 6. SEND MESSAGE (AUTONOMOUS MULTI-STEP SSE LOOP)
  // ===================================================================
  async function handleSendMessage() {
    if (isGenerating) {
      if (activeAbortController) {
        activeAbortController.abort();
        activeAbortController = null;
      }
      setGeneratingState(false);
      return;
    }

    const promptText = chatPromptInput.value.trim();
    if (!promptText && attachedFiles.length === 0) return;

    if (!activeProjectId) {
      alert("Сначала создайте или выберите проект слева.");
      return;
    }

    const emptyState = document.getElementById("emptyFeedState");
    if (emptyState) emptyState.remove();

    // 1. User Card
    const userCard = document.createElement("div");
    userCard.className = "message-user-card";
    userCard.textContent = promptText;
    if (attachedFiles.length > 0) {
      const filesTag = document.createElement("div");
      filesTag.style.cssText = "font-size: 11px; opacity: 0.7; margin-top: 5px;";
      filesTag.textContent = "Файлы: " + attachedFiles.map((f) => f.name).join(", ");
      userCard.appendChild(filesTag);
    }
    messagesContainer.appendChild(userCard);

    chatPromptInput.value = "";
    chatPromptInput.style.height = "auto";
    const refFileIds = attachedFiles.map((f) => f.id);
    attachedFiles = [];
    attachedChips.innerHTML = "";

    // 2. Assistant Card Skeleton
    const assistantCard = document.createElement("div");
    assistantCard.className = "message-assistant-card";

    const isSolo = activeProjectData?.mode === "solo";
    let authorName = isSolo ? (activeProjectData?.lead_agent?.name || "Агент проекта") : (activeProjectData?.lead_agent?.name || "Руководитель проекта");
    let authorIcon = isSolo ? (activeProjectData?.lead_agent?.icon || "⚡") : (activeProjectData?.lead_agent?.icon || "🧠");
    if (activeChatType === "subagent") {
      const curSub = (activeProjectData?.subagents || []).find((a) => a.id === activeSubagentId);
      if (curSub) {
        authorName = curSub.name;
        authorIcon = curSub.icon || "🤖";
      }
    }

    const titleRow = document.createElement("div");
    titleRow.className = "assistant-title-row";
    titleRow.innerHTML = `<span style="font-size: 15px;">${authorIcon}</span> <span>${escapeHtml(authorName)}:</span>`;
    assistantCard.appendChild(titleRow);

    // Live Action Steps Tree Container
    const liveSteps = [];
    let treeContainerEl = buildActionStepsTreeElement(liveSteps, true, "Запуск задачи...");
    assistantCard.appendChild(treeContainerEl);

    const mdBody = document.createElement("div");
    mdBody.className = "markdown-body";
    assistantCard.appendChild(mdBody);

    const footer = document.createElement("div");
    footer.className = "message-footer";
    footer.innerHTML = `<span>только что</span> • <span class="copy-ans">Копировать</span>`;
    assistantCard.appendChild(footer);

    messagesContainer.appendChild(assistantCard);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    setGeneratingState(true);
    activeAbortController = new AbortController();

    let rawAccumulatedText = "";
    const endpointUrl = activeChatType === "subagent"
      ? `/api/projects/${activeProjectId}/agents/${activeSubagentId}/message`
      : `/api/projects/${activeProjectId}/lead/message`;

    // Initialize global in-flight tracking so switching chats does not lose this generation
    activeGeneration = {
      isGenerating: true,
      projectId: activeProjectId,
      activeProjectName: activeProjectData?.name || "Проект",
      chatType: activeChatType,
      subagentId: activeSubagentId,
      promptText: promptText,
      rawAccumulatedText: "",
      liveSteps: liveSteps,
      currentStatusText: "Запуск задачи...",
      activeAgentName: authorName,
      activeAgentIcon: authorIcon,
      startTime: Date.now(),
      timerInterval: null,
      userCardEl: userCard,
      assistantCardEl: assistantCard,
      treeContainerEl: treeContainerEl,
      mdBodyEl: mdBody,
      footerEl: footer,
    };

    updateLiveActivity("Запуск задачи...", authorName, authorIcon, true);
    renderChatAgentsNav();

    try {
      const response = await fetch(endpointUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: promptText,
          thinking_enabled: thinkingEnabled,
          ref_file_ids: refFileIds,
        }),
        signal: activeAbortController.signal,
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data: ")) {
            const rawJson = trimmed.slice(6);
            if (rawJson === "[DONE]") break;
            try {
              const chunk = JSON.parse(rawJson);
              if (chunk.type === "chunk" || chunk.type === "text") {
                rawAccumulatedText += chunk.content;
                activeGeneration.rawAccumulatedText = rawAccumulatedText;
                mdBody.innerHTML = renderMarkdown(cleanUserFacingText(rawAccumulatedText));
                updateLiveActivity("Формирование ответа...", activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, true);
              } else if (chunk.type === "thinking") {
                updateLiveActivity("💭 DeepThink: анализирует задачу...", activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, true);
              } else if (chunk.type === "user_message_update") {
                rawAccumulatedText = chunk.text;
                activeGeneration.rawAccumulatedText = rawAccumulatedText;
                mdBody.innerHTML = renderMarkdown(cleanUserFacingText(chunk.text));
              } else if (chunk.type === "loop_step_start") {
                const stepTitle = `Шаг ${chunk.step}: анализ ситуации...`;
                updateLiveActivity(stepTitle, activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, true);
                const newTree = buildActionStepsTreeElement(liveSteps, true, "Координация работы...");
                treeContainerEl.replaceWith(newTree);
                treeContainerEl = newTree;
                activeGeneration.treeContainerEl = newTree;
              } else if (chunk.type === "action_step_notify") {
                updateLiveActivity(chunk.message, activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, true);
                const titleSpan = treeContainerEl.querySelector(".tree-title");
                if (titleSpan) titleSpan.textContent = chunk.message;
              } else if (chunk.type === "action_step") {
                liveSteps.push(chunk.step);
                activeGeneration.liveSteps = liveSteps;
                let actText = "Выполнение действия...";
                if (chunk.step.category === "file") {
                  actText = `📁 Создан файл: ${chunk.step.file_path}`;
                } else if (chunk.step.category === "file_read") {
                  actText = `📄 Прочитан файл: ${chunk.step.file_path}`;
                } else if (chunk.step.category === "cmd") {
                  actText = `💻 Команда: ${chunk.step.command}`;
                } else if (chunk.step.category === "subagent") {
                  actText = `🤖 Поручение: ${chunk.step.agent_name}`;
                }
                updateLiveActivity(actText, activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, true, chunk.step);
                const newTree = buildActionStepsTreeElement(liveSteps, true, "Выполнение задачи...");
                treeContainerEl.replaceWith(newTree);
                treeContainerEl = newTree;
                activeGeneration.treeContainerEl = newTree;
              } else if (chunk.type === "agent_spawned") {
                if (activeProjectData && chunk.agent) {
                  if (!activeProjectData.subagents) activeProjectData.subagents = [];
                  const existingIdx = activeProjectData.subagents.findIndex(a => a.id === chunk.agent.id);
                  if (existingIdx === -1) {
                    activeProjectData.subagents.push(chunk.agent);
                  } else {
                    activeProjectData.subagents[existingIdx] = chunk.agent;
                  }
                  renderChatAgentsNav();
                  renderRightPanelAgentsAndTasks();
                  if (activeView === "mindmap") {
                    renderMindMap();
                  }
                  const leadCountEl = document.getElementById("leadSubagentsCount");
                  if (leadCountEl) leadCountEl.textContent = `${activeProjectData.subagents.length} субагентов`;
                  if (rightAgentsBadge) rightAgentsBadge.textContent = activeProjectData.subagents.length;
                }
              } else if (chunk.type === "terminal_cmd") {
                logTerminal("cmd", chunk.command, chunk.sender || "Агент");
                logTerminal(chunk.code === 0 ? "output" : "error", chunk.output);
                updateLiveActivity(`💻 CMD: ${chunk.command}`, activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, true, { category: "cmd", command: chunk.command, title: chunk.command });
              } else if (chunk.type === "final_text") {
                rawAccumulatedText = chunk.text;
                activeGeneration.rawAccumulatedText = chunk.text;
                mdBody.innerHTML = renderMarkdown(cleanUserFacingText(chunk.text));
                if (chunk.steps && chunk.steps.length > 0) {
                  liveSteps.length = 0;
                  liveSteps.push(...chunk.steps);
                  activeGeneration.liveSteps = liveSteps;
                }
                updateLiveActivity("✅ Задача выполнена", activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, false);
              } else if (chunk.type === "error") {
                mdBody.innerHTML += `<div style="color: #ef4444; margin-top: 6px;">[Ошибка: ${chunk.message}]</div>`;
                updateLiveActivity(`Ошибка: ${chunk.message}`, activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, false);
              }
              messagesContainer.scrollTop = messagesContainer.scrollHeight;
            } catch (e) {}
          }
        }
      }

      // Finish generation state and display static completed tree
      const completedTreeTitle = isSolo ? `Действия агента (${liveSteps.length})` : `Действия команды (${liveSteps.length})`;
      const finalTree = buildActionStepsTreeElement(liveSteps, false, completedTreeTitle);
      treeContainerEl.replaceWith(finalTree);
      treeContainerEl = finalTree;
      activeGeneration.treeContainerEl = finalTree;

      footer.querySelector(".copy-ans").addEventListener("click", () => {
        navigator.clipboard.writeText(cleanUserFacingText(rawAccumulatedText));
      });

      // Refresh project state to update tabs and subagent counts
      const resp = await fetch(`/api/projects/${activeProjectId}`);
      const data = await resp.json();
      if (data.success) {
        activeProjectData = data.project;
        renderChatAgentsNav();
        renderRightPanelAgentsAndTasks();
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        mdBody.innerHTML += `<div style="color: #ef4444; margin-top: 6px;">[Ошибка сети: ${err.message}]</div>`;
        updateLiveActivity(`Ошибка сети: ${err.message}`, activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, false);
      }
    } finally {
      setGeneratingState(false);
      activeAbortController = null;
      activeGeneration.isGenerating = false;
      updateLiveActivity("Готов к работе", activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, false);
      const bgBanner = messagesContainer.querySelector(".bg-generation-banner");
      if (bgBanner) bgBanner.remove();
      renderChatAgentsNav();
      renderRightPanelAgentsAndTasks();
    }
  }

  function setGeneratingState(generating) {
    isGenerating = generating;
    if (generating) {
      btnSendMessage.classList.add("stop");
      btnSendMessage.innerHTML = `<span style="font-size: 10px;">■</span>`;
    } else {
      btnSendMessage.classList.remove("stop");
      btnSendMessage.innerHTML = `
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>
      `;
    }
  }

  if (btnSendMessage) btnSendMessage.addEventListener("click", handleSendMessage);

  if (chatPromptInput) {
    chatPromptInput.addEventListener("input", () => {
      chatPromptInput.style.height = "auto";
      chatPromptInput.style.height = Math.min(chatPromptInput.scrollHeight, 120) + "px";
    });

    chatPromptInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    });
  }

  if (btnModelSelect) {
    const models = ["DeepSeek-V3", "DeepSeek-R1 (Thinking)"];
    let mIdx = 0;
    btnModelSelect.addEventListener("click", () => {
      mIdx = (mIdx + 1) % models.length;
      currentModel = models[mIdx];
      modelLabel.textContent = currentModel;
      thinkingEnabled = currentModel.includes("Thinking") || currentModel.includes("R1");
      if (reasoningStatusLabel) {
        reasoningStatusLabel.textContent = thinkingEnabled ? "DeepThink: ВКЛ" : "DeepThink: Выкл";
      }
    });
  }

  if (btnToggleReasoning) {
    btnToggleReasoning.addEventListener("click", () => {
      thinkingEnabled = !thinkingEnabled;
      reasoningStatusLabel.textContent = thinkingEnabled ? "DeepThink: ВКЛ" : "DeepThink: Выкл";
    });
  }

  // ===================================================================
  // 6.2 ATTACH FILE (CLICK, MULTI-SELECT, DRAG & DROP, CTRL+V)
  // ===================================================================
  async function uploadAndAttachFile(file) {
    if (!file) return;

    let filename = file.name;
    if (!filename || filename === "blob" || filename === "image.png") {
      const ext = file.type ? file.type.split("/")[1] || "png" : "png";
      filename = `pasted_${Date.now()}.${ext}`;
    }

    const chip = document.createElement("div");
    chip.className = "file-chip loading";
    chip.innerHTML = `<span>⏳ ${escapeHtml(filename)}...</span>`;
    attachedChips.appendChild(chip);

    const formData = new FormData();
    formData.append("file", file, filename);

    try {
      const resp = await fetch("/api/upload", { method: "POST", body: formData });
      const data = await resp.json();
      if (data.success) {
        attachedFiles.push({ id: data.id, name: data.filename });
        chip.className = "file-chip";
        chip.innerHTML = `
          <span style="font-size: 11px;">📎</span>
          <span>${escapeHtml(data.filename)}</span>
          <span class="remove-file" title="Удалить">&#10005;</span>
        `;
        chip.querySelector(".remove-file").addEventListener("click", () => {
          chip.remove();
          attachedFiles = attachedFiles.filter((f) => f.id !== data.id);
        });
      } else {
        chip.remove();
        alert("Ошибка загрузки файла: " + (data.error || "Неизвестно"));
      }
    } catch (err) {
      chip.remove();
      alert("Сетевая ошибка при загрузке файла: " + err);
    }
  }

  // 1. Click to Attach Button & File Picker
  if (btnAttachFile && hiddenFileInput) {
    btnAttachFile.addEventListener("click", () => hiddenFileInput.click());
    hiddenFileInput.addEventListener("change", async (e) => {
      const files = Array.from(e.target.files || []);
      for (const file of files) {
        await uploadAndAttachFile(file);
      }
      hiddenFileInput.value = "";
    });
  }

  // 2. Ctrl+V Paste Event (Files, Documents, Screenshots)
  document.addEventListener("paste", async (e) => {
    const activeEl = document.activeElement;
    if (activeEl && activeEl.tagName === "INPUT" && activeEl.id !== "chatPromptInput") {
      return;
    }

    const items = e.clipboardData?.items;
    if (!items || items.length === 0) return;

    const fileList = [];
    for (const item of items) {
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) fileList.push(file);
      }
    }

    if (fileList.length > 0) {
      if (!e.clipboardData.getData("text/plain")) {
        e.preventDefault();
      }
      for (const file of fileList) {
        await uploadAndAttachFile(file);
      }
    }
  });

  // 3. Drag & Drop Files onto Chat
  const chatInputWrapper = document.getElementById("chatInputWrapper");
  const chatDragOverlay = document.getElementById("chatDragOverlay");
  const mainChatView = document.getElementById("viewLeadChat");

  if (mainChatView && chatInputWrapper) {
    let dragCounter = 0;

    ["dragenter"].forEach((eventName) => {
      window.addEventListener(eventName, (e) => {
        if (e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files")) {
          e.preventDefault();
          dragCounter++;
          if (chatDragOverlay) chatDragOverlay.style.display = "flex";
          chatInputWrapper.classList.add("drag-over");
        }
      });
    });

    ["dragover"].forEach((eventName) => {
      window.addEventListener(eventName, (e) => {
        if (e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files")) {
          e.preventDefault();
          e.dataTransfer.dropEffect = "copy";
        }
      });
    });

    ["dragleave"].forEach((eventName) => {
      window.addEventListener(eventName, (e) => {
        dragCounter--;
        if (dragCounter <= 0) {
          dragCounter = 0;
          if (chatDragOverlay) chatDragOverlay.style.display = "none";
          chatInputWrapper.classList.remove("drag-over");
        }
      });
    });

    window.addEventListener("drop", async (e) => {
      e.preventDefault();
      dragCounter = 0;
      if (chatDragOverlay) chatDragOverlay.style.display = "none";
      chatInputWrapper.classList.remove("drag-over");

      const files = Array.from(e.dataTransfer?.files || []);
      if (files.length > 0) {
        for (const file of files) {
          await uploadAndAttachFile(file);
        }
      }
    });
  }

  // ===================================================================
  // 7. MIND MAP
  // ===================================================================
  function renderMindMap() {
    if (!activeProjectData) {
      renderEmptyProjectState();
      return;
    }

    mindMapNodesLayer.innerHTML = "";
    mindMapSvgLayer.innerHTML = "";

    const lead = activeProjectData.lead_agent || { name: "Руководитель проекта", role: "Координация субагентов" };
    const subagents = activeProjectData.subagents || [];

    // Lead Node
    const leadCard = document.createElement("div");
    leadCard.className = "lead-agent-card";
    leadCard.id = "leadAgentNode";

    const leadIcon = lead.icon || "🧠";
    leadCard.innerHTML = `
      <div style="display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 24px; flex-shrink: 0;">${leadIcon}</span>
        <div style="min-width: 0;">
          <div class="lead-name">${escapeHtml(lead.name)}</div>
          <div class="lead-role">${escapeHtml(lead.role)}</div>
        </div>
      </div>
      <div class="lead-status-row">
        <span style="display: flex; align-items: center; gap: 5px;">
          <span class="status-dot"></span>
          <span>Координирует команду</span>
        </span>
        <button class="lead-chat-shortcut-btn" id="btnLeadNodeChat">В чат</button>
      </div>
    `;

    leadCard.querySelector("#btnLeadNodeChat").addEventListener("click", () => {
      switchView("chat");
    });

    mindMapNodesLayer.appendChild(leadCard);

    // Subagents Cluster
    const cluster = document.createElement("div");
    cluster.className = "subagents-cluster";
    cluster.id = "subagentsCluster";

    if (subagents.length === 0) {
      cluster.innerHTML = `
        <div style="text-align: center; color: var(--text-dim); padding: 24px; font-size: 12px;">
          В проекте пока нет субагентов.<br>
          Нажмите кнопку <strong>Назначить субагента</strong> вверху справа.
        </div>
      `;
    } else {
      subagents.forEach((agent) => {
        const agentCard = document.createElement("div");
        agentCard.className = "subagent-node-card";
        agentCard.setAttribute("data-agent-id", agent.id);

        let statusText = "Ожидание";
        if (agent.status === "working") statusText = "В работе";
        else if (agent.status === "done") statusText = "Завершено";

        const agentIcon = agent.icon || "🤖";
        agentCard.innerHTML = `
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 22px; flex-shrink: 0;">${agentIcon}</span>
            <div style="min-width: 0;">
              <div class="subagent-name-title">${escapeHtml(agent.name)}</div>
              <div class="subagent-role-title">${escapeHtml(agent.role)}</div>
            </div>
          </div>

          <div class="subagent-status-pill">
            <span class="status-dot" style="background-color: ${agent.status === "working" ? "var(--status-working)" : "var(--status-active)"};"></span>
            <span>${statusText}</span>
          </div>

          <div class="subagent-node-actions">
            <button class="subagent-action-btn chat-btn" style="color: #60a5fa;">💬 Чат</button>
            <button class="subagent-action-btn delete-btn" style="color: #ef4444;">Удалить</button>
          </div>
        `;

        agentCard.querySelector(".chat-btn").addEventListener("click", () => {
          switchView("chat");
          switchActiveChat("subagent", agent.id);
        });

        agentCard.querySelector(".delete-btn").addEventListener("click", () => {
          deleteSubagent(agent.id);
        });

        cluster.appendChild(agentCard);
      });
    }

    mindMapNodesLayer.appendChild(cluster);
    setTimeout(drawMindMapConnections, 60);
  }

  function drawMindMapConnections() {
    mindMapSvgLayer.innerHTML = "";
    const leadNode = document.getElementById("leadAgentNode");
    const container = document.getElementById("mindMapCanvasContainer");
    if (!leadNode || !container) return;

    const contRect = container.getBoundingClientRect();
    const leadRect = leadNode.getBoundingClientRect();

    const startX = leadRect.left + leadRect.width / 2 - contRect.left + container.scrollLeft;
    const startY = leadRect.bottom - contRect.top + container.scrollTop;

    const agentNodes = document.querySelectorAll(".subagent-node-card");
    agentNodes.forEach((node) => {
      const nodeRect = node.getBoundingClientRect();
      const endX = nodeRect.left + nodeRect.width / 2 - contRect.left + container.scrollLeft;
      const endY = nodeRect.top - contRect.top + container.scrollTop;

      const midY = (startY + endY) / 2;
      const pathD = `M ${startX} ${startY} C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${endY}`;

      const basePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      basePath.setAttribute("d", pathD);
      basePath.setAttribute("class", "mindmap-connection-path");
      mindMapSvgLayer.appendChild(basePath);

      const pulsePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      pulsePath.setAttribute("d", pathD);
      pulsePath.setAttribute("class", "mindmap-pulse-path");
      mindMapSvgLayer.appendChild(pulsePath);
    });
  }

  window.addEventListener("resize", () => {
    if (activeView === "mindmap") {
      drawMindMapConnections();
    }
  });

  if (btnRefreshMindMap) {
    btnRefreshMindMap.addEventListener("click", () => {
      selectProject(activeProjectId);
    });
  }

  async function executeAgentTask(agentId) {
    if (!activeProjectId) return;
    try {
      const resp = await fetch(`/api/projects/${activeProjectId}/agents/${agentId}/execute`, { method: "POST" });
      const data = await resp.json();
      if (data.success) {
        if (data.executed_commands && data.executed_commands.length > 0) {
          data.executed_commands.forEach((c) => {
            logTerminal("cmd", c.command, `Субагент [${agentId}]`);
            logTerminal(c.code === 0 ? "output" : "error", c.output);
          });
        }
        alert("Задача субагента успешно выполнена!");
        selectProject(activeProjectId);
      } else {
        alert("Ошибка выполнения: " + data.error);
      }
    } catch (e) {
      alert("Ошибка сети: " + e);
    }
  }

  async function deleteSubagent(agentId) {
    if (!confirm("Удалить субагента из проекта?")) return;
    try {
      await fetch(`/api/projects/${activeProjectId}/agents/${agentId}`, { method: "DELETE" });
      selectProject(activeProjectId);
    } catch (e) {
      alert("Ошибка: " + e);
    }
  }

  // ===================================================================
  // 8. RIGHT PANEL
  // ===================================================================
  rightTabBtns.forEach((tab) => {
    tab.addEventListener("click", () => {
      rightTabBtns.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const target = tab.getAttribute("data-tab");

      tabContentAgents.style.display = target === "agents" ? "block" : "none";
      tabContentTerminal.style.display = target === "terminal" ? "block" : "none";
      tabContentFiles.style.display = target === "files" ? "block" : "none";

      if (target === "terminal") {
        if (terminalLogWindow) terminalLogWindow.scrollTop = terminalLogWindow.scrollHeight;
      }
    });
  });

  // ===================================================================
  // 8.1 TERMINAL CONSOLE & COMMAND EXECUTION
  // ===================================================================
  const terminalLogWindow = document.getElementById("terminalLogWindow");
  const terminalCmdInput = document.getElementById("terminalCmdInput");
  const btnExecuteTerminalCmd = document.getElementById("btnExecuteTerminalCmd");
  const btnClearTerminal = document.getElementById("btnClearTerminal");

  function logTerminal(type, text, sender) {
    if (!terminalLogWindow) return;
    const line = document.createElement("div");
    line.className = `terminal-line ${type}`;

    const now = new Date();
    const timeStr = now.toTimeString().split(" ")[0];

    if (type === "cmd") {
      line.innerHTML = `<span style="color: var(--text-dim);">[${timeStr}]</span> <span style="color: var(--accent-primary); font-weight: 600;">[${escapeHtml(sender || "Shell")}]</span> $ <strong>${escapeHtml(text)}</strong>`;
    } else if (type === "output") {
      line.textContent = text;
    } else if (type === "error") {
      line.textContent = "[Ошибка] " + text;
    } else {
      line.textContent = text;
    }

    terminalLogWindow.appendChild(line);
    terminalLogWindow.scrollTop = terminalLogWindow.scrollHeight;
  }

  async function executeTerminalCommand(cmd) {
    const cleanCmd = (cmd || "").trim();
    if (!cleanCmd) return;
    logTerminal("cmd", cleanCmd, "Пользователь");
    if (terminalCmdInput) terminalCmdInput.value = "";

    try {
      const resp = await fetch("/api/terminal/exec", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          command: cleanCmd,
          project_id: activeProjectId,
          cwd: activeProjectData?.root_path,
        }),
      });
      const data = await resp.json();
      if (data.code === 0) {
        logTerminal("output", data.output);
      } else {
        logTerminal("error", data.output);
      }
    } catch (e) {
      logTerminal("error", "Сбой вызова API: " + e);
    }
  }

  if (btnExecuteTerminalCmd && terminalCmdInput) {
    btnExecuteTerminalCmd.addEventListener("click", () => {
      executeTerminalCommand(terminalCmdInput.value);
    });
    terminalCmdInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        executeTerminalCommand(terminalCmdInput.value);
      }
    });
  }

  if (btnClearTerminal && terminalLogWindow) {
    btnClearTerminal.addEventListener("click", () => {
      terminalLogWindow.innerHTML = `<div class="terminal-line system">[Система] Консоль очищена.</div>`;
    });
  }

  function renderRightPanelAgentsAndTasks() {
    if (!activeProjectData) {
      if (rightSubagentsList) rightSubagentsList.innerHTML = `<div class="empty-hint">Нет активного проекта</div>`;
      if (rightTasksList) rightTasksList.innerHTML = `<div class="empty-hint">Нет задач</div>`;
      if (rightAgentsBadge) rightAgentsBadge.textContent = "0";
      if (rightTasksBadge) rightTasksBadge.textContent = "0";
      return;
    }

    const isSolo = activeProjectData.mode === "solo";
    const subagents = activeProjectData.subagents || [];
    const tasks = activeProjectData.tasks || [];

    if (rightAgentsBadge) rightAgentsBadge.textContent = isSolo ? "1" : String(subagents.length + 1);
    if (rightTasksBadge) rightTasksBadge.textContent = tasks.length;

    if (!rightSubagentsList) return;
    rightSubagentsList.innerHTML = "";

    // 1. Lead / Solo Agent Card (Always shown at top)
    const isLeadGenWorking = activeGeneration.isGenerating && activeGeneration.projectId === activeProjectId && activeGeneration.chatType === "lead";
    const leadCard = document.createElement("div");
    leadCard.className = `right-agent-card ${isLeadGenWorking ? "working" : ""} ${activeChatType === "lead" ? "active-chat" : ""}`;
    const leadIcon = isSolo ? (activeProjectData.lead_agent?.icon || "⚡") : (activeProjectData.lead_agent?.icon || "🧠");
    const leadName = activeProjectData.lead_agent?.name || (isSolo ? "Автономный агент" : "Руководитель проекта");
    const leadRole = activeProjectData.lead_agent?.role || (isSolo ? "Автономный инженер (делает всё сам)" : "Архитектор и координатор");
    const leadStatusText = isLeadGenWorking ? `🔥 ${activeGeneration.currentStatusText}` : "⚪ Готов к приёму задач";
    const leadBadgeClass = isLeadGenWorking ? "working" : "idle";
    const leadBadgeText = isLeadGenWorking ? "В РАБОТЕ" : "ГОТОВ";

    leadCard.innerHTML = `
      <div class="right-agent-top">
        <div style="display: flex; align-items: center; gap: 6px; min-width: 0;">
          <span style="font-size: 14px; flex-shrink: 0;">${leadIcon}</span>
          <span style="font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(leadName)}</span>
        </div>
        <span class="agent-live-status-pill ${leadBadgeClass}">${leadBadgeText}</span>
      </div>
      <div style="font-size: 10.5px; color: var(--text-muted);">${escapeHtml(leadRole)}</div>
      <div style="font-size: 10px; color: ${isLeadGenWorking ? '#60a5fa' : 'var(--text-dim)'}; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(leadStatusText)}">
        ${escapeHtml(leadStatusText)}
      </div>
      <div style="margin-top: 6px;">
        <button class="right-agent-chat-btn" style="width: 100%; padding: 4px; font-size: 11px; background: ${activeChatType === 'lead' ? 'var(--accent-subtle)' : 'var(--badge-bg)'}; border: 1px solid ${activeChatType === 'lead' ? 'var(--accent-primary)' : 'var(--border-color)'}; border-radius: 4px; color: #60a5fa; cursor: pointer;">💬 Чат ${isSolo ? 'с агентом' : 'с руководителем'}</button>
      </div>
    `;
    leadCard.querySelector(".right-agent-chat-btn").addEventListener("click", () => {
      switchActiveChat("lead");
    });
    rightSubagentsList.appendChild(leadCard);

    // 2. Subagents List (Multi-Agent Mode)
    if (!isSolo) {
      if (subagents.length === 0) {
        const hint = document.createElement("div");
        hint.className = "empty-hint";
        hint.style.cssText = "margin-top: 6px; text-align: center; font-size: 11px;";
        hint.textContent = "Субагенты будут созданы руководителем или по кнопке +";
        rightSubagentsList.appendChild(hint);
      } else {
        subagents.forEach((a) => {
          const isSubGenWorking = activeGeneration.isGenerating && activeGeneration.projectId === activeProjectId && activeGeneration.chatType === "subagent" && activeGeneration.subagentId === a.id;
          const item = document.createElement("div");
          item.className = `right-agent-card ${isSubGenWorking ? "working" : ""} ${activeChatType === "subagent" && activeSubagentId === a.id ? "active-chat" : ""}`;
          const aIcon = a.icon || "🤖";

          let statusBadgeText = "ОЖИДАНИЕ";
          let statusBadgeClass = "idle";
          if (isSubGenWorking) {
            statusBadgeText = "В РАБОТЕ";
            statusBadgeClass = "working";
          } else if (a.status === "done" || a.status === "completed") {
            statusBadgeText = "ВЫПОЛНЕНО";
            statusBadgeClass = "done";
          }

          const currentTaskText = isSubGenWorking
            ? (activeGeneration.currentStatusText || "Выполняет назначенную задачу...")
            : (a.current_task && a.current_task !== "Ожидает назначения задачи" ? a.current_task : "Ожидает поручений");

          item.innerHTML = `
            <div class="right-agent-top">
              <div style="display: flex; align-items: center; gap: 6px; min-width: 0;">
                <span style="font-size: 14px; flex-shrink: 0;">${aIcon}</span>
                <span style="font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(a.name)}</span>
              </div>
              <span class="agent-live-status-pill ${statusBadgeClass}">${statusBadgeText}</span>
            </div>
            <div style="font-size: 10.5px; color: var(--text-muted);">${escapeHtml(a.role || "")}</div>
            <div style="font-size: 10px; color: ${isSubGenWorking ? '#60a5fa' : 'var(--text-dim)'}; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(currentTaskText)}">
              ${isSubGenWorking ? "🔥 " : ""}${escapeHtml(currentTaskText)}
            </div>
            <div style="margin-top: 6px;">
              <button class="right-agent-chat-btn" style="width: 100%; padding: 4px; font-size: 11px; background: ${activeChatType === 'subagent' && activeSubagentId === a.id ? 'var(--accent-subtle)' : 'var(--badge-bg)'}; border: 1px solid ${activeChatType === 'subagent' && activeSubagentId === a.id ? 'var(--accent-primary)' : 'var(--border-color)'}; border-radius: 4px; color: #60a5fa; cursor: pointer;">💬 Чат с субагентом</button>
            </div>
          `;
          item.querySelector(".right-agent-chat-btn").addEventListener("click", () => {
            switchActiveChat("subagent", a.id);
          });
          rightSubagentsList.appendChild(item);
        });
      }
    }

    // Tasks List
    if (rightTasksList) {
      rightTasksList.innerHTML = "";
      if (tasks.length === 0) {
        rightTasksList.innerHTML = `<div class="empty-hint">Нет активных задач</div>`;
      } else {
        tasks.forEach((t) => {
          const item = document.createElement("div");
          item.className = "task-item-row";
          item.innerHTML = `
            <span class="task-title-text" title="${escapeHtml(t.title)}">${escapeHtml(t.title)}</span>
            <span class="task-status-pill">${t.status}</span>
          `;
          rightTasksList.appendChild(item);
        });
      }
    }
  }

  // Hook Stop Button in Right Panel Live Activity
  const btnStopLiveActivity = document.getElementById("btnStopLiveActivity");
  if (btnStopLiveActivity) {
    btnStopLiveActivity.addEventListener("click", () => {
      if (activeAbortController) {
        activeAbortController.abort();
        activeAbortController = null;
      }
      setGeneratingState(false);
      activeGeneration.isGenerating = false;
      updateLiveActivity("Остановлено пользователем", activeGeneration.activeAgentName, activeGeneration.activeAgentIcon, false);
      const bgBanner = messagesContainer.querySelector(".bg-generation-banner");
      if (bgBanner) bgBanner.remove();
      renderChatAgentsNav();
      renderRightPanelAgentsAndTasks();
    });
  }

  // Network Logs
  async function loadNetworkLogs() {
    try {
      const resp = await fetch("/api/logs?limit=20");
      const data = await resp.json();
      const logs = data.logs || [];

      if (logCountBadge) logCountBadge.textContent = logs.length;
      networkLogsList.innerHTML = "";

      logs.forEach((log) => {
        const item = document.createElement("div");
        item.className = "log-entry";
        const status = log.status || "OK";

        item.innerHTML = `
          <div class="log-top-row">
            <span class="log-method">${log.method || "REQ"}</span>
            <span class="log-status">[${status}]</span>
          </div>
          <div class="log-url" title="${escapeHtml(log.url)}">${escapeHtml(log.url || "")}</div>
        `;
        networkLogsList.appendChild(item);
      });
    } catch (e) {}
  }

  setInterval(() => {
    if (tabContentTerminal && tabContentTerminal.style.display !== "none") {
      loadNetworkLogs();
    }
  }, 3500);

  // ===================================================================
  // 9. MODALS (CREATE PROJECT & ADD AGENT)
  // ===================================================================
  const newProjectFolderInput = document.getElementById("newProjectFolderInput");
  const btnBrowseProjectFolder = document.getElementById("btnBrowseProjectFolder");

  function setProjectModalMode(mode) {
    selectedNewProjectMode = mode;
    const radio = document.querySelector(`input[name="newProjectMode"][value="${mode}"]`);
    if (radio) radio.checked = true;
    if (mode === "solo") {
      modeCardSolo?.classList.add("active");
      modeCardMulti?.classList.remove("active");
    } else {
      modeCardMulti?.classList.add("active");
      modeCardSolo?.classList.remove("active");
    }
  }

  if (modeCardMulti) {
    modeCardMulti.addEventListener("click", () => setProjectModalMode("multi"));
  }
  if (modeCardSolo) {
    modeCardSolo.addEventListener("click", () => setProjectModalMode("solo"));
  }

  if (btnOpenNewProjectModal) {
    btnOpenNewProjectModal.addEventListener("click", () => {
      newProjectNameInput.value = "";
      if (newProjectFolderInput) newProjectFolderInput.value = "";
      setProjectModalMode("multi");
      modalNewProject.style.display = "flex";
      setTimeout(() => newProjectNameInput.focus(), 50);
    });
  }

  function closeNewProjectModal() {
    modalNewProject.style.display = "none";
  }

  if (btnCloseNewProjectModal) btnCloseNewProjectModal.addEventListener("click", closeNewProjectModal);
  if (btnCancelNewProject) btnCancelNewProject.addEventListener("click", closeNewProjectModal);

  if (btnBrowseProjectFolder) {
    btnBrowseProjectFolder.addEventListener("click", async () => {
      try {
        const resp = await fetch("/api/browse_folder", { method: "POST" });
        const data = await resp.json();
        if (data.success && data.path) {
          if (newProjectFolderInput) newProjectFolderInput.value = data.path;
        }
      } catch (e) {
        console.warn("Folder browse error:", e);
      }
    });
  }

  if (btnSubmitNewProject) {
    btnSubmitNewProject.addEventListener("click", async () => {
      const name = newProjectNameInput.value.trim();
      const folder = newProjectFolderInput ? newProjectFolderInput.value.trim() : "";
      const mode = selectedNewProjectMode || "multi";
      if (!name) {
        alert("Введите название проекта!");
        return;
      }
      await createProject(name, folder, mode);
      closeNewProjectModal();
    });
  }

  const newAgentIconInput = document.getElementById("newAgentIconInput");

  // Wire up emoji preset buttons in modal
  document.querySelectorAll(".emoji-preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (newAgentIconInput) newAgentIconInput.value = btn.textContent.trim();
    });
  });

  if (btnOpenAddAgentModal) {
    btnOpenAddAgentModal.addEventListener("click", () => {
      if (!activeProjectId) {
        alert("Сначала создайте проект!");
        return;
      }
      newAgentNameInput.value = "";
      newAgentRoleInput.value = "";
      newAgentPromptInput.value = "";
      if (newAgentIconInput) newAgentIconInput.value = "🤖";
      modalNewAgent.style.display = "flex";
      setTimeout(() => newAgentNameInput.focus(), 50);
    });
  }

  function closeNewAgentModal() {
    modalNewAgent.style.display = "none";
  }

  if (btnCloseNewAgentModal) btnCloseNewAgentModal.addEventListener("click", closeNewAgentModal);
  if (btnCancelNewAgent) btnCancelNewAgent.addEventListener("click", closeNewAgentModal);

  if (btnSubmitNewAgent) {
    btnSubmitNewAgent.addEventListener("click", async () => {
      const name = newAgentNameInput.value.trim();
      const role = newAgentRoleInput.value.trim();
      const prompt = newAgentPromptInput.value.trim();
      const icon = newAgentIconInput ? newAgentIconInput.value.trim() : "🤖";
      if (!name || !role) {
        alert("Введите имя и роль субагента!");
        return;
      }
      try {
        const resp = await fetch(`/api/projects/${activeProjectId}/agents`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            role,
            system_prompt: prompt,
            icon,
          }),
        });
        const data = await resp.json();
        if (data.success && data.agent) {
          closeNewAgentModal();
          if (activeProjectData) {
            if (!activeProjectData.subagents) activeProjectData.subagents = [];
            const existingIdx = activeProjectData.subagents.findIndex(a => a.id === data.agent.id);
            if (existingIdx === -1) {
              activeProjectData.subagents.push(data.agent);
            } else {
              activeProjectData.subagents[existingIdx] = data.agent;
            }
            renderChatAgentsNav();
            renderRightPanelAgentsAndTasks();
            if (activeView === "mindmap") {
              renderMindMap();
            }
            const leadCountEl = document.getElementById("leadSubagentsCount");
            if (leadCountEl) leadCountEl.textContent = `${activeProjectData.subagents.length} субагентов`;
            if (rightAgentsBadge) rightAgentsBadge.textContent = activeProjectData.subagents.length;
          }
          selectProject(activeProjectId);
        }
      } catch (err) {
        alert("Ошибка добавления субагента: " + err);
      }
    });
  }

  // ===================================================================
  // 10. SETTINGS & AUTH STATUS
  // ===================================================================
  async function loadAppVersion() {
    try {
      const resp = await fetch("/api/version");
      const data = await resp.json();
      if (appVersionBadge && data && data.version) {
        appVersionBadge.textContent = "v" + data.version;
        appVersionBadge.title = "Версия Uroboros: " + data.version;
      }
    } catch (e) {
      console.warn("Failed to load app version", e);
    }
  }

  async function loadSettingsData() {
    try {
      const resp = await fetch("/api/status");
      const data = await resp.json();

      const isAuthed = data.logged_in;
      if (topAuthStatusDot) {
        topAuthStatusDot.classList.toggle("offline", !isAuthed);
        topAuthStatusDot.title = isAuthed ? "Сессия активна" : "Требуется авторизация";
      }
      if (settingAuthIndicator) {
        settingAuthIndicator.classList.toggle("offline", !isAuthed);
      }

      if (settingAuthText) {
        settingAuthText.textContent = isAuthed
          ? "DeepSeek Web Сессия Активна"
          : "Сессия не найдена (Требуется вход)";
      }
      if (settingAuthSubtext) {
        settingAuthSubtext.textContent = isAuthed
          ? `Токен сохранен, куки: ${data.cookies_count} шт.`
          : "Войдите через браузер Chrome ниже";
      }

      const settingAuthTextNav = document.getElementById("settingAuthTextNav");
      const settingAuthSubtextNav = document.getElementById("settingAuthSubtextNav");
      if (settingAuthTextNav) {
        settingAuthTextNav.textContent = isAuthed ? "DeepSeek Web" : "Не авторизован";
      }
      if (settingAuthSubtextNav) {
        settingAuthSubtextNav.textContent = isAuthed ? (data.token_preview || "Подключено") : "Требуется вход";
      }

      if (settingTokenInput && !settingTokenInput.value) {
        settingTokenInput.value = data.token || "";
      }
    } catch (e) {}
  }

  function openSettings() {
    loadSettingsData();
    settingsModal.style.display = "flex";
  }

  function closeSettings() {
    settingsModal.style.display = "none";
  }

  if (btnOpenSettings) btnOpenSettings.addEventListener("click", openSettings);
  if (btnOpenSettingsTop) btnOpenSettingsTop.addEventListener("click", openSettings);
  if (btnCloseSettings) btnCloseSettings.addEventListener("click", closeSettings);
  loadAppVersion();
  if (btnCancelSettings) btnCancelSettings.addEventListener("click", closeSettings);

  if (settingsModal) {
    settingsModal.addEventListener("click", (e) => {
      if (e.target === settingsModal) closeSettings();
    });
  }

  // Settings Tabs Navigation (General, Session, Appearance, Models, Permissions)
  const settingsNavItems = document.querySelectorAll(".settings-nav-item");
  const settingsPanes = {
    general: document.getElementById("paneGeneral"),
    session: document.getElementById("paneSession"),
    appearance: document.getElementById("paneAppearance"),
    models: document.getElementById("paneModels"),
    permissions: document.getElementById("panePermissions"),
  };

  settingsNavItems.forEach((navItem) => {
    navItem.addEventListener("click", () => {
      const tabName = navItem.getAttribute("data-tab");
      settingsNavItems.forEach((item) => item.classList.remove("active"));
      navItem.classList.add("active");

      Object.keys(settingsPanes).forEach((key) => {
        if (settingsPanes[key]) {
          settingsPanes[key].style.display = key === tabName ? "block" : "none";
        }
      });
    });
  });

  // Generic Segmented Controls inside Settings (toggle active class)
  document.querySelectorAll(".settings-segmented").forEach((seg) => {
    if (seg.id === "themeSegmented") return; // Handled separately
    seg.querySelectorAll(".settings-segmented-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        seg.querySelectorAll(".settings-segmented-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
      });
    });
  });

  // Global Keyboard Shortcuts (Escape to close, Ctrl+, to open Settings)
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (settingsModal && settingsModal.style.display === "flex") {
        closeSettings();
      }
      if (modalNewProject && modalNewProject.style.display === "flex") {
        closeNewProjectModal();
      }
      if (modalNewAgent && modalNewAgent.style.display === "flex") {
        closeNewAgentModal();
      }
    }
    if ((e.ctrlKey || e.metaKey) && e.key === ",") {
      e.preventDefault();
      openSettings();
    }
  });

  if (btnToggleTokenVisibility && settingTokenInput) {
    btnToggleTokenVisibility.addEventListener("click", () => {
      settingTokenInput.type = settingTokenInput.type === "password" ? "text" : "password";
    });
  }

  if (btnSaveToken) {
    btnSaveToken.addEventListener("click", async () => {
      const token = settingTokenInput.value.trim();
      btnSaveToken.disabled = true;
      btnSaveToken.textContent = "Сохранение...";
      try {
        const resp = await fetch("/api/settings/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });
        const res = await resp.json();
        alert(res.message || "Токен сохранен!");
        loadSettingsData();
        closeSettings();
      } catch (err) {
        alert("Ошибка: " + err);
      } finally {
        btnSaveToken.disabled = false;
        btnSaveToken.textContent = "Сохранить токен";
      }
    });
  }

  if (btnClearSession) {
    btnClearSession.addEventListener("click", async () => {
      if (!confirm("Удалить сохраненную сессию и куки?")) return;
      try {
        await fetch("/api/settings/clear", { method: "POST" });
        loadSettingsData();
      } catch (e) {}
    });
  }

  if (btnSettingsLaunchSelenium) {
    btnSettingsLaunchSelenium.addEventListener("click", async () => {
      btnSettingsLaunchSelenium.disabled = true;
      btnSettingsLaunchSelenium.textContent = "Запуск Chrome...";
      try {
        const resp = await fetch("/api/auth/start_selenium", { method: "POST" });
        const res = await resp.json();
        alert(res.message);
      } catch (e) {
        alert("Ошибка запуска Chrome: " + e);
      } finally {
        setTimeout(() => {
          btnSettingsLaunchSelenium.disabled = false;
          btnSettingsLaunchSelenium.textContent = "Войти через Chrome";
          loadSettingsData();
        }, 3000);
      }
    });
  }

  if (btnSettingsResetProfile) {
    btnSettingsResetProfile.addEventListener("click", async () => {
      try {
        const resp = await fetch("/api/auth/reset_profile", { method: "POST" });
        const res = await resp.json();
        alert(res.message);
      } catch (e) {
        alert("Ошибка: " + e);
      }
    });
  }

  // ===================================================================
  // 11. INITIALIZATION
  // ===================================================================
  loadSettingsData();
  loadProjects();
  setInterval(loadSettingsData, 6000);
});
