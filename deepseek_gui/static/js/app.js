/**
 * Uroboros - Client Logic & Settings Manager
 */

document.addEventListener("DOMContentLoaded", () => {
  let activeChatId = null;
  let attachedFiles = [];
  let isGenerating = false;
  let activeAbortController = null;
  let currentModel = "DeepSeek-V3";
  let thinkingEnabled = false;

  // DOM Elements
  const messagesContainer = document.getElementById("messagesContainer");
  const chatPromptInput = document.getElementById("chatPromptInput");
  const btnSendMessage = document.getElementById("btnSendMessage");
  const btnAttachFile = document.getElementById("btnAttachFile");
  const hiddenFileInput = document.getElementById("hiddenFileInput");
  const attachedChips = document.getElementById("attachedChips");
  const btnModelSelect = document.getElementById("btnModelSelect");
  const modelLabel = document.getElementById("modelLabel");
  const btnNewChat = document.getElementById("btnNewChat");
  const conversationsList = document.getElementById("conversationsList");
  const chatCountBadge = document.getElementById("chatCountBadge");
  const activeChatTitle = document.getElementById("activeChatTitle");
  const networkLogsList = document.getElementById("networkLogsList");
  const uploadedFilesList = document.getElementById("uploadedFilesList");
  const authStatusDot = document.getElementById("authStatusDot");

  // Settings Modal Elements
  const settingsModal = document.getElementById("settingsModal");
  const btnOpenSettings = document.getElementById("btnOpenSettings");
  const btnCloseSettings = document.getElementById("btnCloseSettings");
  const btnCancelSettings = document.getElementById("btnCancelSettings");
  const btnSaveToken = document.getElementById("btnSaveToken");
  const btnClearSession = document.getElementById("btnClearSession");
  const settingTokenInput = document.getElementById("settingTokenInput");
  const btnToggleTokenVisibility = document.getElementById("btnToggleTokenVisibility");
  const btnSettingsLaunchSelenium = document.getElementById("btnSettingsLaunchSelenium");
  const settingsAuthStatusText = document.getElementById("settingsAuthStatusText");
  const settingsCookieCount = document.getElementById("settingsCookieCount");
  const settingsSavedAt = document.getElementById("settingsSavedAt");

  // 1. TABS SWITCHING (RIGHT PANEL)
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = {
    terminal: document.getElementById("tabContentTerminal"),
    files: document.getElementById("tabContentFiles"),
    review: document.getElementById("tabContentReview"),
  };

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      const tabName = btn.getAttribute("data-tab");
      Object.keys(tabPanes).forEach((k) => {
        if (tabPanes[k]) {
          tabPanes[k].style.display = k === tabName ? "block" : "none";
        }
      });
    });
  });

  // 2. SETTINGS MODAL LOGIC (TOKEN & AUTH)
  async function loadSettingsData() {
    try {
      const resp = await fetch("/api/status");
      const data = await resp.json();

      if (settingTokenInput) {
        settingTokenInput.value = data.token || "";
      }
      if (settingsCookieCount) {
        settingsCookieCount.textContent = data.cookies_count || 0;
      }
      if (settingsSavedAt) {
        settingsSavedAt.textContent = data.saved_at || "-";
      }

      if (data.logged_in) {
        if (settingsAuthStatusText) {
          settingsAuthStatusText.textContent = "Авторизован (Active)";
          settingsAuthStatusText.style.color = "var(--accent-green)";
        }
        if (authStatusDot) authStatusDot.className = "status-indicator";
      } else {
        if (settingsAuthStatusText) {
          settingsAuthStatusText.textContent = "Не авторизован (Нужен токен или вход)";
          settingsAuthStatusText.style.color = "var(--accent-red)";
        }
        if (authStatusDot) authStatusDot.className = "status-indicator red";
      }
    } catch (e) {
      console.warn("Error fetching status:", e);
    }
  }

  if (btnOpenSettings) {
    btnOpenSettings.addEventListener("click", () => {
      loadSettingsData();
      settingsModal.style.display = "flex";
    });
  }

  function closeSettings() {
    settingsModal.style.display = "none";
  }

  if (btnCloseSettings) btnCloseSettings.addEventListener("click", closeSettings);
  if (btnCancelSettings) btnCancelSettings.addEventListener("click", closeSettings);

  // Close modal when clicking on backdrop
  if (settingsModal) {
    settingsModal.addEventListener("click", (e) => {
      if (e.target === settingsModal) closeSettings();
    });
  }

  // Toggle token input visibility
  if (btnToggleTokenVisibility && settingTokenInput) {
    btnToggleTokenVisibility.addEventListener("click", () => {
      if (settingTokenInput.type === "password") {
        settingTokenInput.type = "text";
        btnToggleTokenVisibility.textContent = "🔒";
      } else {
        settingTokenInput.type = "password";
        btnToggleTokenVisibility.textContent = "👁";
      }
    });
  }

  // Save Token
  if (btnSaveToken) {
    btnSaveToken.addEventListener("click", async () => {
      const token = settingTokenInput.value.trim();
      btnSaveToken.disabled = true;
      btnSaveToken.textContent = "Сохранение...";

      try {
        const resp = await fetch("/api/settings/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: token }),
        });
        const res = await resp.json();
        alert(res.message || "Токен сохранен!");
        loadSettingsData();
        closeSettings();
      } catch (err) {
        alert("Ошибка сохранения: " + err);
      } finally {
        btnSaveToken.disabled = false;
        btnSaveToken.textContent = "Сохранить токен";
      }
    });
  }

  // Clear Session
  if (btnClearSession) {
    btnClearSession.addEventListener("click", async () => {
      if (!confirm("Вы уверены, что хотите удалить сохраненные куки и токен?")) return;
      try {
        const resp = await fetch("/api/settings/clear", { method: "POST" });
        const res = await resp.json();
        alert(res.message || "Сессия очищена.");
        loadSettingsData();
      } catch (err) {
        alert("Ошибка: " + err);
      }
    });
  }

  // Launch Selenium inside settings
  if (btnSettingsLaunchSelenium) {
    btnSettingsLaunchSelenium.addEventListener("click", async () => {
      btnSettingsLaunchSelenium.disabled = true;
      btnSettingsLaunchSelenium.innerHTML = `<span>Запуск Chrome...</span>`;

      try {
        const resp = await fetch("/api/auth/start_selenium", { method: "POST" });
        const res = await resp.json();
        alert(res.message || "Браузер запущен. Залогиньтесь на сайте.");
      } catch (err) {
        alert("Ошибка запуска браузера: " + err);
      } finally {
        setTimeout(() => {
          btnSettingsLaunchSelenium.disabled = false;
          btnSettingsLaunchSelenium.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            <span>Войти через Selenium</span>
          `;
          loadSettingsData();
        }, 3000);
      }
    });
  }

  loadSettingsData();
  setInterval(loadSettingsData, 6000);

  // 3. CONVERSATIONS MANAGEMENT (START FROM SCRATCH)
  async function loadConversations() {
    try {
      const resp = await fetch("/api/chats");
      const data = await resp.json();
      const chats = data.chats || [];

      if (chatCountBadge) chatCountBadge.textContent = chats.length;
      conversationsList.innerHTML = "";

      if (chats.length === 0) {
        conversationsList.innerHTML = `
          <div class="empty-chats-hint">
            Нет диалогов.<br>Нажмите <strong>+ New Conversation</strong> выше, чтобы создать чат.
          </div>
        `;
        return;
      }

      chats.forEach((chat, idx) => {
        const item = document.createElement("div");
        item.className = "chat-item" + (chat.id === activeChatId ? " active" : "");
        item.setAttribute("data-id", chat.id);

        item.innerHTML = `
          <span class="chat-title-text" title="${chat.title}">${chat.title || "Новый диалог"}</span>
          <span class="chat-time-badge">${chat.updated_at || ""}</span>
          <button class="chat-delete-btn" title="Удалить диалог">&#10005;</button>
        `;

        item.querySelector(".chat-title-text").addEventListener("click", () => {
          selectChat(chat.id, chat.title);
        });

        item.querySelector(".chat-delete-btn").addEventListener("click", (e) => {
          e.stopPropagation();
          deleteChat(chat.id);
        });

        conversationsList.appendChild(item);

        // Select first chat if none selected
        if (!activeChatId && idx === 0) {
          selectChat(chat.id, chat.title);
        }
      });
    } catch (e) {
      console.warn("Failed loading chats:", e);
    }
  }

  function selectChat(chatId, title) {
    activeChatId = chatId;
    if (activeChatTitle) activeChatTitle.textContent = title || "Диалог";

    document.querySelectorAll(".chat-item").forEach((el) => {
      el.classList.toggle("active", el.getAttribute("data-id") === chatId);
    });

    // Clear feed for this chat
    messagesContainer.innerHTML = `
      <div style="text-align: center; color: var(--text-dim); margin-top: 50px; font-size: 13px;">
        Активный диалог: <strong>${title || "Новый диалог"}</strong><br>
        <span style="font-size: 11.5px;">Отправьте сообщение ниже.</span>
      </div>
    `;
  }

  async function createNewChat() {
    try {
      const resp = await fetch("/api/chats/new", { method: "POST" });
      const data = await resp.json();
      activeChatId = data.chat_id;
      if (activeChatTitle) activeChatTitle.textContent = data.title || "Новый диалог";

      messagesContainer.innerHTML = `
        <div style="text-align: center; color: var(--text-dim); margin-top: 50px; font-size: 13px;">
          Создан новый диалог (${activeChatId}).<br>
          <span style="font-size: 11.5px;">Отправьте сообщение ниже, чтобы начать общение.</span>
        </div>
      `;

      loadConversations();
    } catch (err) {
      alert("Ошибка создания чата: " + err);
    }
  }

  async function deleteChat(chatId) {
    if (!confirm("Удалить этот диалог?")) return;
    try {
      await fetch(`/api/chats/${chatId}`, { method: "DELETE" });
      if (activeChatId === chatId) {
        activeChatId = null;
        if (activeChatTitle) activeChatTitle.textContent = "New Conversation";
        messagesContainer.innerHTML = `
          <div class="empty-chats-hint">
            Диалог удален. Нажмите <strong>+ New Conversation</strong> для создания нового.
          </div>
        `;
      }
      loadConversations();
    } catch (err) {
      alert("Ошибка удаления: " + err);
    }
  }

  if (btnNewChat) {
    btnNewChat.addEventListener("click", createNewChat);
  }

  loadConversations();

  // 4. ATTACH FILES
  if (btnAttachFile && hiddenFileInput) {
    btnAttachFile.addEventListener("click", () => hiddenFileInput.click());

    hiddenFileInput.addEventListener("change", async () => {
      const file = hiddenFileInput.files[0];
      if (!file) return;

      const chip = document.createElement("div");
      chip.className = "file-chip";
      chip.innerHTML = `
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
        <span>${file.name} (загрузка...)</span>
      `;
      attachedChips.appendChild(chip);

      const formData = new FormData();
      formData.append("file", file);

      try {
        const resp = await fetch("/api/upload", { method: "POST", body: formData });
        const data = await resp.json();
        if (data.success) {
          attachedFiles.push({ id: data.id, name: data.filename });
          chip.innerHTML = `
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
            <span>${data.filename}</span>
            <span class="remove-file" title="Удалить">&#10005;</span>
          `;

          chip.querySelector(".remove-file").addEventListener("click", () => {
            chip.remove();
            attachedFiles = attachedFiles.filter((f) => f.id !== data.id);
          });

          if (uploadedFilesList) {
            const item = document.createElement("div");
            item.className = "log-item";
            item.innerHTML = `
              <div style="font-weight: 500; color: var(--text-main);">${data.filename}</div>
              <div style="font-size: 10px; color: var(--text-dim);">ID: ${data.id} | ${Math.round(data.size / 1024)} KB</div>
            `;
            uploadedFilesList.appendChild(item);
          }
        } else {
          chip.remove();
          alert("Ошибка загрузки файла: " + (data.error || "Неизвестно"));
        }
      } catch (err) {
        chip.remove();
        alert("Сетевая ошибка загрузки: " + err);
      }
      hiddenFileInput.value = "";
    });
  }

  // 5. AUTO-EXPAND TEXTAREA
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

  // 6. MODEL SELECTOR
  if (btnModelSelect) {
    const models = [
      "DeepSeek-V3",
      "DeepSeek-R1 (Thinking)",
      "DeepSeek-Chat",
    ];
    let modelIdx = 0;
    btnModelSelect.addEventListener("click", () => {
      modelIdx = (modelIdx + 1) % models.length;
      currentModel = models[modelIdx];
      modelLabel.textContent = currentModel;
      thinkingEnabled = currentModel.includes("Thinking") || currentModel.includes("R1");
    });
  }

  // 7. SEND MESSAGE / SSE STREAM
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

    if (!activeChatId) {
      await createNewChat();
    }

    // Remove empty state message if present
    const emptyState = document.getElementById("emptyFeedState");
    if (emptyState) emptyState.remove();

    // 1. Render User Message
    const userCard = document.createElement("div");
    userCard.className = "message-user-card";
    userCard.textContent = promptText;
    if (attachedFiles.length > 0) {
      const filesTag = document.createElement("div");
      filesTag.style.cssText = "font-size: 11px; color: var(--accent-blue); margin-top: 6px;";
      filesTag.textContent = "Файлы: " + attachedFiles.map((f) => f.name).join(", ");
      userCard.appendChild(filesTag);
    }
    messagesContainer.appendChild(userCard);

    // Clear input
    chatPromptInput.value = "";
    chatPromptInput.style.height = "auto";
    const refFileIds = attachedFiles.map((f) => f.id);
    attachedFiles = [];
    attachedChips.innerHTML = "";

    // 2. Render Assistant Message Skeleton
    const assistantCard = document.createElement("div");
    assistantCard.className = "message-assistant-card";

    const titleEl = document.createElement("div");
    titleEl.className = "assistant-title";
    titleEl.textContent = "Ответ " + currentModel + ":";
    assistantCard.appendChild(titleEl);

    // Thinking box
    const thinkingBox = document.createElement("div");
    thinkingBox.className = "thinking-expander";
    thinkingBox.innerHTML = `<strong>Размышления:</strong> <span class="thinking-text"></span>`;
    assistantCard.appendChild(thinkingBox);

    // Text output container
    const contentBox = document.createElement("div");
    contentBox.style.cssText = "white-space: pre-wrap; line-height: 1.6; color: var(--text-main); font-size: 13.5px;";
    assistantCard.appendChild(contentBox);

    // Footer
    const footerEl = document.createElement("div");
    footerEl.className = "message-footer";
    footerEl.innerHTML = `<span>только что</span> <span class="copy-ans" title="Copy">&#128203;</span> <span title="Like">&#128077;</span>`;
    assistantCard.appendChild(footerEl);

    footerEl.querySelector(".copy-ans").addEventListener("click", () => {
      navigator.clipboard.writeText(contentBox.innerText);
    });

    messagesContainer.appendChild(assistantCard);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    setGeneratingState(true);
    activeAbortController = new AbortController();

    try {
      const response = await fetch(`/api/chats/${activeChatId}/message`, {
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
              if (chunk.type === "thinking") {
                thinkingBox.classList.add("visible");
                thinkingBox.querySelector(".thinking-text").textContent += chunk.content;
              } else if (chunk.type === "text") {
                contentBox.textContent += chunk.content;
              } else if (chunk.type === "error") {
                contentBox.textContent += `\n[Ошибка: ${chunk.message}]`;
              }
              messagesContainer.scrollTop = messagesContainer.scrollHeight;
            } catch (e) {}
          }
        }
      }

      loadConversations();
    } catch (err) {
      if (err.name !== "AbortError") {
        contentBox.textContent += `\n[Ошибка соединения: ${err.message}]`;
      }
    } finally {
      setGeneratingState(false);
      activeAbortController = null;
    }
  }

  function setGeneratingState(generating) {
    isGenerating = generating;
    if (generating) {
      btnSendMessage.classList.add("stop");
      btnSendMessage.innerHTML = `<span style="font-size: 11px;">&#9632;</span>`;
      btnSendMessage.title = "Остановить генерацию";
    } else {
      btnSendMessage.classList.remove("stop");
      btnSendMessage.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>
      `;
      btnSendMessage.title = "Отправить сообщение";
    }
  }

  if (btnSendMessage) {
    btnSendMessage.addEventListener("click", handleSendMessage);
  }

  // 8. NETWORK LOGS POLLER
  async function pollLogs() {
    try {
      const resp = await fetch("/api/logs?limit=25");
      const data = await resp.json();
      if (!data.logs || !networkLogsList) return;

      networkLogsList.innerHTML = "";
      data.logs.forEach((log) => {
        const item = document.createElement("div");
        item.className = "log-item";

        const method = (log.method || "REQ").toUpperCase();
        const methodClass = method === "POST" ? "post" : "get";
        const status = log.status || (log.kind === "requests_client_request" ? "SENT" : "OK");
        const statusClass = (status >= 400 || log.error) ? "err" : "";
        const timeStr = (log.timestamp || "").split("T")[1]?.slice(0, 8) || "";

        item.innerHTML = `
          <div class="log-item-top">
            <div>
              <span class="log-method ${methodClass}">${method}</span>
              <span class="log-status ${statusClass}">[${status}]</span>
            </div>
            <span style="color: var(--text-dim); font-size: 10px;">${timeStr}</span>
          </div>
          <div class="log-url" title="${log.url}">${log.url || "-"}</div>
        `;

        item.addEventListener("click", () => {
          const detail = JSON.stringify(log, null, 2);
          alert(`Детали запроса (${method} ${log.url}):\n\n` + detail.slice(0, 1500));
        });

        networkLogsList.appendChild(item);
      });
    } catch (e) {}
  }

  pollLogs();
  setInterval(pollLogs, 2500);

  // 9. WINDOW CONTROLS (PYWEBVIEW INTEGRATION)
  const btnWinMinimize = document.getElementById("btnWinMinimize");
  const btnWinMaximize = document.getElementById("btnWinMaximize");
  const btnWinClose = document.getElementById("btnWinClose");

  if (btnWinMinimize) {
    btnWinMinimize.addEventListener("click", () => {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.minimize) {
        window.pywebview.api.minimize();
      }
    });
  }

  if (btnWinMaximize) {
    btnWinMaximize.addEventListener("click", () => {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_maximize) {
        window.pywebview.api.toggle_maximize();
      }
    });
  }

  if (btnWinClose) {
    btnWinClose.addEventListener("click", () => {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.close) {
        window.pywebview.api.close();
      } else {
        window.close();
      }
    });
  }
});
