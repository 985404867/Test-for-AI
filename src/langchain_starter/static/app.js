(function () {
  const { createElement: h, useEffect, useMemo, useRef, useState } = React;
  const { createRoot } = ReactDOM;

  const initialMessages = [
    {
      role: "system",
      content: "欢迎使用 LangChain Starter。可以开启 Agent 模式，让模型自动调用联网搜索和本地知识库。",
    },
  ];

  /** 生成消息时间标签，供聊天记录和会话卡片展示。 */
  function nowLabel() {
    return new Date().toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  /** 拼接多个 CSS 类名，方便根据状态切换样式。 */
  function classNames(...values) {
    return values.filter(Boolean).join(" ");
  }

  /** 格式化会话更新时间，用于历史会话列表显示。 */
  function formatSessionTime(value) {
    if (!value) return "";
    const date = new Date(`${value.replace(" ", "T")}Z`);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleDateString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
    });
  }

  /** 从本地存储读取或创建浏览器会话 ID。 */
  function getOrCreateSessionId() {
    const key = "langchain-starter-session-id";
    let sessionId = localStorage.getItem(key);
    if (!sessionId) {
      sessionId = crypto.randomUUID();
      localStorage.setItem(key, sessionId);
    }
    return sessionId;
  }

  /** 主应用组件，负责会话管理、消息渲染和发送流程。 */
  function App() {
    const [config, setConfig] = useState({
      model: "loading",
      webSearchEnabled: true,
      webSearchProvider: "auto",
      agentModeEnabled: true,
    });
    const [messages, setMessages] = useState(initialMessages);
    const [input, setInput] = useState("");
    const [webSearch, setWebSearch] = useState(true);
    const [agentMode, setAgentMode] = useState(true);
    const [status, setStatus] = useState("就绪");
    const [isThinking, setIsThinking] = useState(false);
    const [sessionId, setSessionId] = useState(getOrCreateSessionId);
    const [sessions, setSessions] = useState([]);
    const [deletedSessions, setDeletedSessions] = useState([]);
    const [sessionQuery, setSessionQuery] = useState("");
    const listRef = useRef(null);
    const inputRef = useRef(null);
    const sessionStorageKey = "langchain-starter-session-id";

    const sessionsForList = useMemo(() => {
      if (sessions.some((session) => session.id === sessionId)) return sessions;
      return [
        {
          id: sessionId,
          title: "当前会话",
          updated_at: "",
        },
        ...sessions,
      ];
    }, [sessions, sessionId]);

    const normalizedQuery = sessionQuery.trim().toLowerCase();
    const filteredSessions = useMemo(() => {
      if (!normalizedQuery) return sessionsForList;
      return sessionsForList.filter((session) => {
        const haystack = `${session.title || ""} ${session.id || ""}`.toLowerCase();
        return haystack.includes(normalizedQuery);
      });
    }, [normalizedQuery, sessionsForList]);

    const filteredDeletedSessions = useMemo(() => {
      if (!normalizedQuery) return deletedSessions;
      return deletedSessions.filter((session) => {
        const haystack = `${session.title || ""} ${session.id || ""}`.toLowerCase();
        return haystack.includes(normalizedQuery);
      });
    }, [normalizedQuery, deletedSessions]);

    useEffect(() => {
      fetch("/api/config")
        .then((response) => response.json())
        .then((data) => {
          setConfig(data);
          const nextAgentMode = Boolean(data.agentModeEnabled);
          setAgentMode(nextAgentMode);
          setWebSearch(nextAgentMode ? false : Boolean(data.webSearchEnabled));
        })
        .catch(() => setStatus("配置读取失败"));
    }, []);

    /** 拉取未删除会话列表，用于侧边栏展示。 */
    async function refreshSessions() {
      try {
        const response = await fetch("/api/sessions");
        const data = await response.json();
        setSessions(Array.isArray(data.sessions) ? data.sessions : []);
      } catch {
        setStatus("历史会话读取失败");
      }
    }

    /** 拉取回收站会话列表，供恢复和永久删除使用。 */
    async function refreshDeletedSessions() {
      try {
        const response = await fetch("/api/sessions?deleted=1");
        const data = await response.json();
        setDeletedSessions(Array.isArray(data.sessions) ? data.sessions : []);
      } catch {
        setStatus("回收站读取失败");
      }
    }

    /** 读取指定会话消息并恢复到当前聊天窗口。 */
    async function loadSession(nextSessionId) {
      localStorage.setItem(sessionStorageKey, nextSessionId);
      setSessionId(nextSessionId);
      setStatus("正在读取历史...");
      try {
        const response = await fetch(`/api/session?sessionId=${encodeURIComponent(nextSessionId)}`);
        const data = await response.json();
        if (!Array.isArray(data.messages) || data.messages.length === 0) {
          setMessages(initialMessages);
          setStatus("就绪");
          return;
        }
        setMessages(
          data.messages.map((message) => ({
            id: `stored-${message.id}`,
            role: message.role,
            content: message.content,
            metadata: message.metadata || {},
            time: message.created_at,
          }))
        );
        setStatus("已恢复历史");
      } catch {
        setStatus("历史记录读取失败");
      }
    }

    useEffect(() => {
      loadSession(sessionId);
      refreshSessions();
      refreshDeletedSessions();
    }, []);

    useEffect(() => {
      const list = listRef.current;
      if (!list) return;
      list.scrollTo({ top: list.scrollHeight, behavior: "smooth" });
    }, [messages]);

    const conversationHistory = useMemo(
      () =>
        messages
          .filter((message) => message.role === "user" || message.role === "assistant")
          .map((message) => ({ role: message.role, content: message.content })),
      [messages]
    );

    const conversationCount = useMemo(
      () => messages.filter((message) => message.role === "user" || message.role === "assistant").length,
      [messages]
    );

    const currentModeLabel = agentMode ? "Agent 模式" : webSearch ? "联网搜索" : "纯聊天";
    const currentSessionTitle =
      sessionsForList.find((session) => session.id === sessionId)?.title || "新会话";

    /** 复制单条文本到系统剪贴板。 */
    async function copyText(text) {
      await navigator.clipboard.writeText(text);
      setStatus("已复制");
      window.setTimeout(() => setStatus("就绪"), 1200);
    }

    /** 复制当前会话的完整聊天记录。 */
    async function copyAll() {
      const transcript = messages
        .map((message) => {
          const label =
            message.role === "user"
              ? "你"
              : message.role === "assistant"
                ? "AI"
                : message.role === "tool"
                  ? "工具"
                  : "系统";
          return `${label}：\n${message.content}`;
        })
        .join("\n\n");
      await copyText(transcript);
    }

    /** 重命名当前或历史会话。 */
    async function renameSession(targetSession) {
      if (!targetSession?.id || isThinking) return;
      const currentTitle = targetSession.title || "新会话";
      const nextTitle = window.prompt("输入新的会话名称", currentTitle)?.trim();
      if (!nextTitle || nextTitle === currentTitle) return;

      try {
        const response = await fetch("/api/session", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sessionId: targetSession.id,
            title: nextTitle,
          }),
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        await Promise.all([refreshSessions(), refreshDeletedSessions()]);
        setStatus("会话已重命名");
      } catch (error) {
        setStatus(`重命名失败：${error.message}`);
      }
    }

    /** 新建一个空会话并切换过去。 */
    function startNewSession() {
      const nextSessionId = crypto.randomUUID();
      localStorage.setItem(sessionStorageKey, nextSessionId);
      setSessionId(nextSessionId);
      setMessages(initialMessages);
      setStatus("新对话");
      window.setTimeout(refreshSessions, 300);
      inputRef.current?.focus();
    }

    /** 切换到指定历史会话。 */
    function switchSession(nextSessionId) {
      if (!nextSessionId || nextSessionId === sessionId || isThinking) return;
      loadSession(nextSessionId);
    }

    /** 将会话移动到回收站。 */
    async function deleteSession(targetSession) {
      if (!targetSession?.id || isThinking) return;
      const title = targetSession.title || "新会话";
      if (!window.confirm(`确定删除「${title}」吗？`)) return;

      try {
        const response = await fetch(
          `/api/session?sessionId=${encodeURIComponent(targetSession.id)}`,
          { method: "DELETE" }
        );
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const remainingSessions = sessions.filter((session) => session.id !== targetSession.id);
        setSessions(remainingSessions);
        setDeletedSessions((current) => [
          {
            ...targetSession,
            deleted_at: new Date().toISOString(),
          },
          ...current.filter((session) => session.id !== targetSession.id),
        ]);

        if (targetSession.id === sessionId) {
          const nextSession = remainingSessions[0];
          if (nextSession) {
            await loadSession(nextSession.id);
          } else {
            startNewSession();
          }
        }

        setStatus("会话已删除");
        window.setTimeout(() => {
          refreshSessions();
          refreshDeletedSessions();
        }, 200);
      } catch (error) {
        setStatus(`删除失败：${error.message}`);
      }
    }

    /** 从回收站恢复会话。 */
    async function restoreSession(targetSession) {
      if (!targetSession?.id || isThinking) return;
      try {
        const response = await fetch("/api/session", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sessionId: targetSession.id,
            restore: true,
          }),
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        setDeletedSessions((current) => current.filter((session) => session.id !== targetSession.id));
        await refreshSessions();
        setStatus("已恢复会话");
      } catch (error) {
        setStatus(`恢复失败：${error.message}`);
      }
    }

    /** 永久删除回收站中的会话。 */
    async function purgeSession(targetSession) {
      if (!targetSession?.id || isThinking) return;
      const title = targetSession.title || "新会话";
      if (!window.confirm(`永久删除「${title}」吗？`)) return;

      try {
        const response = await fetch(
          `/api/session?sessionId=${encodeURIComponent(targetSession.id)}&purge=1`,
          { method: "DELETE" }
        );
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        setDeletedSessions((current) => current.filter((session) => session.id !== targetSession.id));
        setStatus("已永久删除");
      } catch (error) {
        setStatus(`永久删除失败：${error.message}`);
      }
    }

    /** 切换到 Agent 模式，并关闭联网搜索。 */
    function activateAgentMode() {
      setAgentMode(true);
      setWebSearch(false);
    }

    /** 切换到联网搜索模式，并关闭 Agent。 */
    function activateWebSearchMode() {
      setWebSearch(true);
      setAgentMode(false);
    }

    /** 发送消息并处理流式返回、工具调用和错误。 */
    async function sendMessage() {
      const question = input.trim();
      if (!question || isThinking) return;

      const assistantId = crypto.randomUUID();
      setInput("");
      setIsThinking(true);
      setStatus(agentMode ? "Agent 正在思考..." : webSearch ? "正在联网搜索..." : "正在生成回答...");
      setMessages((current) => [
        ...current,
        { role: "user", content: question, time: nowLabel() },
        {
          role: "assistant",
          content: "思考中...",
          pending: true,
          time: nowLabel(),
          id: assistantId,
        },
      ]);

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: question,
            webSearch,
            agentMode,
            sessionId,
            history: conversationHistory,
          }),
        });

        if (!response.ok || !response.body) {
          throw new Error(`请求失败：HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.trim()) continue;
            const event = JSON.parse(line);

            if (event.type === "status") {
              setStatus(event.content);
            } else if (event.type === "tool") {
              const toolName =
                event.tool === "web_search"
                  ? "联网搜索"
                  : event.tool === "local_knowledge_search"
                    ? "本地知识库"
                    : event.tool;
              const phase =
                event.phase === "start"
                  ? "开始调用"
                  : event.phase === "end"
                    ? "调用完成"
                    : "调用失败";
              const detail = event.error || event.preview || event.input || "";
              setMessages((current) => [
                ...current,
                {
                  role: "tool",
                  content: `${phase}：${toolName}\n输入：${event.input || ""}${detail ? `\n结果：${detail}` : ""}`,
                  tool: event.tool,
                  phase: event.phase,
                  time: nowLabel(),
                  id: crypto.randomUUID(),
                },
              ]);
              setStatus(`${phase}：${toolName}`);
            } else if (event.type === "chunk") {
              setMessages((current) =>
                current.map((message) =>
                  message.id === assistantId
                    ? {
                        ...message,
                        pending: false,
                        content: message.pending
                          ? event.content
                          : message.content + event.content,
                      }
                    : message
                )
              );
            } else if (event.type === "error") {
              throw new Error(event.content);
            }
          }
        }

        setStatus("就绪");
        refreshSessions();
      } catch (error) {
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId
              ? { ...message, content: `调用失败：${error.message}` }
              : message
          )
        );
        setStatus("调用失败");
      } finally {
        setIsThinking(false);
        inputRef.current?.focus();
      }
    }

    /** 处理输入框回车发送和 Shift+Enter 换行。 */
    function handleKeyDown(event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    }

    return h(
      "main",
      { className: "app-shell" },
      h(
        "section",
        { className: "window" },
        h(
          "aside",
          { className: "sidebar" },
          h("div", { className: "brand-block" }, [
            h("div", { className: "brand-mark", key: "mark" }, "AI"),
            h("div", { key: "copy" }, [
              h("h1", { key: "title" }, "LangChain Starter"),
              h("p", { key: "subtitle" }, config.model),
            ]),
          ]),
          h("label", { className: "session-search" }, [
            h("span", { key: "label" }, "搜索会话"),
            h("input", {
              key: "input",
              value: sessionQuery,
              placeholder: "按标题或 ID 搜索",
              onChange: (event) => setSessionQuery(event.target.value),
            }),
          ]),
          h(
            "button",
            {
              className: "new-chat-button",
              onClick: startNewSession,
              disabled: isThinking,
            },
            "+ 新对话"
          ),
          h("div", { className: "session-heading" }, "历史会话"),
          h(
            "nav",
            { className: "session-list", "aria-label": "历史会话" },
            filteredSessions.map((session) =>
              h(
                "div",
                {
                  className: classNames("session-row", session.id === sessionId && "active"),
                  key: session.id,
                },
                [
                  h(
                    "button",
                    {
                      className: "session-item",
                      onClick: () => switchSession(session.id),
                      disabled: isThinking,
                      key: "open",
                      title: session.title || "新会话",
                    },
                    [
                      h("span", { className: "session-title", key: "title" }, session.title || "新会话"),
                      h("span", { className: "session-time", key: "time" }, formatSessionTime(session.updated_at)),
                    ]
                  ),
                  h(
                    "button",
                    {
                      className: "session-rename",
                      onClick: () => renameSession(session),
                      disabled: isThinking,
                      key: "rename",
                      title: "重命名",
                      "aria-label": `重命名会话 ${session.title || "新会话"}`,
                    },
                    "✎"
                  ),
                  h(
                    "button",
                    {
                      className: "session-delete",
                      onClick: () => deleteSession(session),
                      disabled: isThinking,
                      key: "delete",
                      title: "删除会话",
                      "aria-label": `删除会话 ${session.title || "新会话"}`,
                    },
                    "×"
                  ),
                ]
              )
            )
          ),
          h("div", { className: "session-heading" }, "回收站"),
          h(
            "nav",
            { className: "session-list deleted", "aria-label": "回收站" },
            filteredDeletedSessions.length
              ? filteredDeletedSessions.map((session) =>
                  h(
                    "div",
                    {
                      className: "session-row deleted-row",
                      key: session.id,
                    },
                    [
                      h(
                        "button",
                        {
                          className: "session-item",
                          onClick: () => restoreSession(session),
                          disabled: isThinking,
                          key: "restore",
                          title: session.title || "已删除会话",
                        },
                        [
                          h("span", { className: "session-title", key: "title" }, session.title || "已删除会话"),
                          h(
                            "span",
                            { className: "session-time", key: "time" },
                            formatSessionTime(session.deleted_at || session.updated_at)
                          ),
                        ]
                      ),
                      h(
                        "button",
                        {
                          className: "session-purge",
                          onClick: () => purgeSession(session),
                          disabled: isThinking,
                          key: "purge",
                          title: "永久删除",
                          "aria-label": `永久删除会话 ${session.title || "已删除会话"}`,
                        },
                        "×"
                      ),
                    ]
                  )
                )
              : h("div", { className: "empty-state" }, "没有已删除的会话")
          ),
          h("div", { className: "sidebar-footer" }, [
            h("span", { key: "provider" }, `搜索源 ${config.webSearchProvider}`),
            h("span", { key: "status" }, status),
          ])
        ),
        h(
          "div",
          { className: "chat-workspace" },
          h(
            "header",
            { className: "chat-header" },
            h("div", { className: "current-chat" }, [
              h("span", { className: "current-label", key: "label" }, "当前会话"),
              h("strong", { key: "title" }, currentSessionTitle),
            ]),
            h("div", { className: "toolbar-actions" }, [
              h("span", { className: "mode-pill", key: "mode" }, currentModeLabel),
              h("span", { className: "count-pill", key: "count" }, `${conversationCount} 条消息`),
              h("button", { className: "ghost-button", onClick: copyAll, key: "copy" }, "复制全部"),
              h("span", { className: "status-pill", key: "status" }, status),
            ])
          ),
          h(
            "div",
            { className: "chat-panel", ref: listRef },
            messages.length <= 1
              ? h("div", { className: "empty-chat" }, [
                  h("div", { className: "empty-chat-title", key: "title" }, "开始一个新对话"),
                  h(
                    "div",
                    { className: "empty-chat-copy", key: "copy" },
                    "可以直接提问，也可以切换模式让模型自动调用工具。"
                  ),
                ])
              : null,
            messages.map((message, index) =>
              h(MessageBubble, {
                key: message.id || `${message.role}-${index}`,
                message,
                onCopy: copyText,
              })
            )
          ),
          h(
            "footer",
            { className: "composer" },
            h("div", { className: "mode-bar", role: "radiogroup", "aria-label": "模式切换" }, [
              h(
                "button",
                {
                  className: classNames("mode-chip", agentMode && "active"),
                  onClick: activateAgentMode,
                  type: "button",
                  key: "agent",
                },
                "Agent 模式"
              ),
              h(
                "button",
                {
                  className: classNames("mode-chip", webSearch && "active"),
                  onClick: activateWebSearchMode,
                  type: "button",
                  key: "web",
                },
                "联网搜索"
              ),
            ]),
            h("textarea", {
              ref: inputRef,
              value: input,
              placeholder: "给 LangChain Starter 发送消息",
              onChange: (event) => setInput(event.target.value),
              onKeyDown: handleKeyDown,
              disabled: isThinking,
            }),
            h(
              "button",
              {
                className: "send-button",
                onClick: sendMessage,
                disabled: isThinking || !input.trim(),
              },
              isThinking ? "生成中" : "发送"
            )
          )
        )
      )
    );
  }

  /** 单条消息气泡，统一渲染用户、AI、系统和工具结果。 */
  function MessageBubble({ message, onCopy }) {
    const label =
      message.role === "user"
        ? "你"
        : message.role === "assistant"
          ? "AI"
          : message.role === "tool"
            ? "工具"
            : "系统";
    const timeLabel = message.time ? message.time : "";
    const isTool = message.role === "tool";
    const toolTitle = message.tool === "web_search" ? "联网搜索" : message.tool === "local_knowledge_search" ? "本地知识库" : "工具调用";
    const phaseLabel =
      message.phase === "start"
        ? "开始"
        : message.phase === "end"
          ? "完成"
          : message.phase === "error"
            ? "失败"
            : "";

    return h(
      "article",
      { className: classNames("message-row", message.role) },
      h(
        "div",
        { className: "bubble" },
        h("div", { className: "bubble-meta" }, [
          h("span", { className: "bubble-label", key: "label" }, label),
          h("span", { className: "bubble-time", key: "time" }, timeLabel),
          h(
            "button",
            { key: "copy", onClick: () => onCopy(message.content), className: "copy-link" },
            "复制"
          ),
        ]),
        isTool
          ? h(
              "details",
              { className: "tool-details", open: message.phase !== "start" },
              [
                h("summary", { key: "summary" }, [
                  h("span", { className: "tool-badge", key: "badge" }, toolTitle),
                  phaseLabel ? h("span", { className: "tool-phase", key: "phase" }, phaseLabel) : null,
                ]),
                h("div", { className: "bubble-content tool-content", key: "content" }, message.content || " "),
              ]
            )
          : h(
              "div",
              {
                className: classNames("bubble-content", message.pending && "pending"),
              },
              message.content || " "
            )
      )
    );
  }

  createRoot(document.getElementById("root")).render(h(App));
})();
