/**
 * DeepSeek API Studio - Antigravity UI Client Logic
 */

document.addEventListener("DOMContentLoaded", () => {
  let activeChatId = "sample-uroboros-1";
  let attachedFiles = [];
  let isGenerating = false;
  let activeAbortController = null;
  let currentModel = "Gemini 3.8 Flash High";
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
  const btnLaunchSelenium = document.getElementById("btnLaunchSelenium");
  const networkLogsList = document.getElementById("networkLogsList");
  const uploadedFilesList = document.getElementById("uploadedFilesList");
  const authStatusDot = document.getElementById("authStatusDot");
  const cookieCount = document.getElementById("cookieCount");
  const tokenPreview = document.getElementById("tokenPreview");
  const sessionTime = document.getElementById("sessionTime");
  const authStatusText = document.getElementById("authStatusText");
  const btnCopyCode = document.getElementById("btnCopyCode");
  const codeSnippet = document.getElementById("codeSnippet");

  // 1. TABS SWITCHING (RIGHT PANEL)
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = {
    terminal: document.getElementById("tabContentTerminal"),
    files: document.getElementById("tabContentFiles"),
    auth: document.getElementById("tabContentAuth"),
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

  document.getElementById("btnOpenSettings")?.addEventListener("click", () => {
    // Switch to Selenium tab
    const authTabBtn = document.querySelector('.tab-btn[data-tab="auth"]');
    if (authTabBtn) authTabBtn.click();
  });

  document.getElementById("btnOpenReview")?.addEventListener("click", () => {
    const revTabBtn = document.querySelector('.tab-btn[data-tab="review"]');
    if (revTabBtn) revTabBtn.click();
  });

  // 2. CHECK STATUS (POLL)
  async function checkStatus() {
    try {
      const resp = await fetch("/api/status");
      const data = await resp.json();
      if (data.logged_in) {
        if (authStatusDot) authStatusDot.className = "status-indicator";
        if (authStatusText) {
          authStatusText.textContent = "Active";
          authStatusText.style.color = "var(--accent-green)";
        }
      } else {
        if (authStatusDot) authStatusDot.className = "status-indicator red";
        if (authStatusText) {
          authStatusText.textContent = "Offline / Need Login";
          authStatusText.style.color = "var(--accent-red)";
        }
      }

      if (cookieCount) cookieCount.textContent = data.cookies_count || 0;
      if (tokenPreview) tokenPreview.textContent = data.token_preview || "Нет";
      if (sessionTime) sessionTime.textContent = data.saved_at || "-";
    } catch (e) {
      console.warn("Status check failed", e);
    }
  }

  checkStatus();
  setInterval(checkStatus, 5000);

  // 3. LAUNCH SELENIUM
  if (btnLaunchSelenium) {
    btnLaunchSelenium.addEventListener("click", async () => {
      btnLaunchSelenium.disabled = true;
      btnLaunchSelenium.innerHTML = `<span>Запуск Chrome...</span>`;

      try {
        const resp = await fetch("/api/auth/start_selenium", { method: "POST" });
        const res = await resp.json();
        alert(res.message || "Браузер запущен. Залогиньтесь на сайте.");
      } catch (err) {
        alert("Ошибка запуска браузера: " + err);
      } finally {
        setTimeout(() => {
          btnLaunchSelenium.disabled = false;
          btnLaunchSelenium.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            <span>Войти через Selenium</span>
          `;
          checkStatus();
        }, 3000);
      }
    });
  }

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

          // Add to files tab
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
        alert("Сетевая ошибка загрузки файла: " + err);
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
      "Gemini 3.8 Flash High",
      "DeepSeek-V3",
      "DeepSeek-R1 (Thinking)",
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
      // Abort generation
      if (activeAbortController) {
        activeAbortController.abort();
        activeAbortController = null;
      }
      setGeneratingState(false);
      return;
    }

    const promptText = chatPromptInput.value.trim();
    if (!promptText && attachedFiles.length === 0) return;

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
    titleEl.textContent = "Ответ DeepSeek (" + currentModel + "):";
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
    footerEl.innerHTML = `<span>только что</span> <span title="Copy">&#128203;</span> <span title="Like">&#128077;</span>`;
    assistantCard.appendChild(footerEl);

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
        buffer = lines.pop(); // keep partial

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
            } catch (e) {
              // Ignore non-json lines
            }
          }
        }
      }
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
      btnSendMessage.innerHTML = `<span style="font-size: 11px;">&#9632;</span>`; // square stop icon
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

  // 8. NEW CHAT
  if (btnNewChat) {
    btnNewChat.addEventListener("click", async () => {
      try {
        const resp = await fetch("/api/chats/new", { method: "POST" });
        const data = await resp.json();
        activeChatId = data.chat_id;
        document.getElementById("activeChatTitle").textContent = "New Conversation";
        messagesContainer.innerHTML = `
          <div style="text-align: center; color: var(--text-dim); margin-top: 40px; font-size: 13px;">
            Создан новый диалог DeepSeek (${activeChatId}). Введите сообщение ниже.
          </div>
        `;
      } catch (err) {
        alert("Ошибка создания чата: " + err);
      }
    });
  }

  // 9. COPY CODE
  if (btnCopyCode && codeSnippet) {
    btnCopyCode.addEventListener("click", () => {
      navigator.clipboard.writeText(codeSnippet.innerText).then(() => {
        btnCopyCode.textContent = "✓";
        setTimeout(() => (btnCopyCode.textContent = "📋"), 1500);
      });
    });
  }

  // 10. NETWORK LOGS POLLER
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
    } catch (e) {
      // ignore poll error
    }
  }

  pollLogs();
  setInterval(pollLogs, 2500);
});
