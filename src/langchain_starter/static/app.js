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

  function LoginScreen({ onLogin }) {
    const [username, setUsername] = useState("admin");
    const [password, setPassword] = useState("123456");
    const [error, setError] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);

    function handleSubmit(event) {
      event.preventDefault();
      if (!username.trim() || !password.trim()) {
        setError("请输入账号和密码");
        return;
      }
      localStorage.setItem("langchain-starter-authenticated", "1");
      localStorage.setItem("langchain-starter-user", username.trim());
      setIsSubmitting(true);
      window.setTimeout(() => onLogin(username.trim()), 180);
    }

    return h(
      "main",
      { className: "login-page" },
      h(
        "section",
        { className: "login-shell" },
        h("div", { className: "login-visual" }, [
          h("div", { className: "login-brand", key: "brand" }, [
            h("span", { className: "login-mark", key: "mark" }, "AI"),
            h("span", { key: "name" }, "AI 工作台"),
          ]),
          h("h1", { key: "title" }, "登录首页"),
          h("p", { key: "copy" }, "登录后进入主页导航，可以打开常用搜索入口，也可以进入 AGENT 系统。"),
        ]),
        h(
          "form",
          { className: "login-form", onSubmit: handleSubmit },
          h("div", { className: "form-heading" }, [
            h("span", { key: "eyebrow" }, "WELCOME"),
            h("h2", { key: "title" }, "账号登录"),
          ]),
          h("label", { className: "field" }, [
            h("span", { key: "label" }, "账号"),
            h("input", {
              key: "input",
              value: username,
              autoComplete: "username",
              placeholder: "请输入账号",
              onChange: (event) => setUsername(event.target.value),
            }),
          ]),
          h("label", { className: "field" }, [
            h("span", { key: "label" }, "密码"),
            h("input", {
              key: "input",
              value: password,
              type: "password",
              autoComplete: "current-password",
              placeholder: "请输入密码",
              onChange: (event) => setPassword(event.target.value),
            }),
          ]),
          error ? h("div", { className: "login-error" }, error) : null,
          h("button", { className: "login-button", type: "submit", disabled: isSubmitting }, isSubmitting ? "正在进入..." : "登录")
        )
      )
    );
  }

  function NavigationScreen({ onOpenAgent }) {
    const [isOpeningAgent, setIsOpeningAgent] = useState(false);

    /** 进入 Agent 前提供短暂的视觉缓冲，避免页面跳转突兀。 */
    function handleOpenAgent() {
      if (isOpeningAgent) return;
      setIsOpeningAgent(true);
      window.setTimeout(onOpenAgent, 180);
    }

    return h(
      "main",
      { className: "nav-page" },
      h(
        "section",
        { className: "nav-shell" },
        [
          h("header", { className: "nav-header", key: "header" }, [
            h("div", { className: "nav-brand", key: "brand" }, [
              h("span", { className: "nav-mark", key: "mark" }, "AI"),
              h("span", { key: "name" }, "主页导航"),
            ]),
            h("p", { key: "copy" }, "请选择要进入的页面"),
          ]),
          h("div", { className: "nav-list", key: "list" }, [
            h(
              "a",
              {
                className: "nav-row",
                href: "https://www.google.com",
                target: "_blank",
                rel: "noreferrer",
                key: "google",
              },
              [
                h("span", { className: "nav-index", key: "index" }, "01"),
                h("strong", { key: "title" }, "谷歌"),
                h("span", { className: "nav-action", key: "action" }, "打开"),
              ]
            ),
            h(
              "a",
              {
                className: "nav-row",
                href: "https://www.baidu.com",
                target: "_blank",
                rel: "noreferrer",
                key: "baidu",
              },
              [
                h("span", { className: "nav-index", key: "index" }, "02"),
                h("strong", { key: "title" }, "百度"),
                h("span", { className: "nav-action", key: "action" }, "打开"),
              ]
            ),
            h(
              "button",
              {
                className: "nav-row nav-row-button",
                type: "button",
                onClick: handleOpenAgent,
                disabled: isOpeningAgent,
                key: "agent",
              },
              [
                h("span", { className: "nav-index", key: "index" }, "03"),
                h("strong", { key: "title" }, "AGENT"),
                h("span", { className: "nav-action", key: "action" }, isOpeningAgent ? "正在进入" : "进入"),
              ]
            ),
          ]),
        ]
      )
    );
  }

  /** 主应用组件，负责会话管理、消息渲染和发送流程。 */
  function App() {
    const [isAuthenticated, setIsAuthenticated] = useState(
      () => localStorage.getItem("langchain-starter-authenticated") === "1"
    );
    const [showAgent, setShowAgent] = useState(false);
    const [config, setConfig] = useState({
      model: "loading",
      webSearchEnabled: true,
      webSearchProvider: "auto",
      agentModeEnabled: true,
    });
    const [messages, setMessages] = useState(initialMessages);
    const [input, setInput] = useState("");
    const [isComposing, setIsComposing] = useState(false);
    const [webSearch, setWebSearch] = useState(true);
    const [agentMode, setAgentMode] = useState(true);
    const [status, setStatus] = useState("就绪");
    const [isThinking, setIsThinking] = useState(false);
    const [sessionId, setSessionId] = useState(getOrCreateSessionId);
    const [sessions, setSessions] = useState([]);
    const [deletedSessions, setDeletedSessions] = useState([]);
    const [sessionQuery, setSessionQuery] = useState("");
    const [confirmation, setConfirmation] = useState(null);
    const [isSessionTransitioning, setIsSessionTransitioning] = useState(false);
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

    /** 读取指定会话消息并恢复到当前聊天窗口，隐藏历史工具调用过程记录。 */
    async function loadSession(nextSessionId) {
      localStorage.setItem(sessionStorageKey, nextSessionId);
      setSessionId(nextSessionId);
      setIsSessionTransitioning(true);
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
          data.messages.filter((message) => message.role !== "tool").map((message) => ({
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
      } finally {
        window.setTimeout(() => setIsSessionTransitioning(false), 180);
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

    function handleLogin() {
      setIsAuthenticated(true);
      setShowAgent(false);
    }

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
      setIsSessionTransitioning(true);
      setStatus("新对话");
      window.setTimeout(refreshSessions, 300);
      window.setTimeout(() => setIsSessionTransitioning(false), 180);
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
      setConfirmation({
        action: "delete",
        session: targetSession,
        title: "删除会话",
        message: `确定删除「${title}」吗？删除后可在回收站恢复。`,
      });
    }

    /** 确认后将会话移动到回收站。 */
    async function confirmDeleteSession(targetSession) {
      if (!targetSession?.id) return;
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
      setConfirmation({
        action: "purge",
        session: targetSession,
        title: "永久删除会话",
        message: `确定永久删除「${title}」吗？此操作无法恢复。`,
      });
    }

    /** 确认后永久删除回收站中的会话。 */
    async function confirmPurgeSession(targetSession) {
      if (!targetSession?.id) return;
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

    /** 执行确认弹窗对应的删除操作。 */
    async function handleConfirmation() {
      if (!confirmation || isThinking) return;
      const { action, session } = confirmation;
      setConfirmation(null);
      if (action === "delete") {
        await confirmDeleteSession(session);
      } else if (action === "purge") {
        await confirmPurgeSession(session);
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
      const toolMessageId = crypto.randomUUID();
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
              const phaseLabel =
                event.phase === "start" ? "调用中" : event.phase === "end" ? "已完成" : "调用失败";
              const detail = event.error
                ? `输入：${event.input || ""}\n错误：${event.error}`
                : event.phase === "end"
                  ? `输入：${event.input || ""}\n结果：${event.preview || "已获取结果"}`
                  : `输入：${event.input || ""}`;
              setMessages((current) => {
                const nextMessage = {
                  role: "tool",
                  content: detail,
                  tool: event.tool,
                  phase: event.phase,
                  time: nowLabel(),
                  id: toolMessageId,
                };
                const existingIndex = current.findIndex((message) => message.id === toolMessageId);
                if (existingIndex === -1) return [...current, nextMessage];
                return current.map((message) => (message.id === toolMessageId ? nextMessage : message));
              });
              setStatus(`${toolName}${phaseLabel}`);
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

    /** 处理输入框回车发送和 Shift+Enter 换行，并跳过输入法候选词确认回车。 */
    function handleKeyDown(event) {
      if (isComposing || event.nativeEvent?.isComposing || event.keyCode === 229) {
        return;
      }
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    }

    if (!isAuthenticated) {
      return h(LoginScreen, { onLogin: handleLogin });
    }

    if (!showAgent) {
      return h(NavigationScreen, { onOpenAgent: () => setShowAgent(true) });
    }

    return h(
      "main",
      { className: "app-shell" },
      [
        h(
        "section",
        { className: "window", key: "window" },
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
          h("div", { className: "session-scroll-area", key: "sessions" }, [
          h("div", { className: "session-heading", key: "history-heading" }, "历史会话"),
          h(
            "nav",
            { className: "session-list", "aria-label": "历史会话", key: "history-list" },
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
          h("div", { className: "session-heading", key: "deleted-heading" }, "回收站"),
          h(
            "nav",
            { className: "session-list deleted", "aria-label": "回收站", key: "deleted-list" },
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
          )
          ]),
          h("div", { className: "sidebar-footer" }, [
            h("span", { key: "provider" }, `搜索源 ${config.webSearchProvider}`),
            h("span", { key: "status" }, status),
          ])
        ),
        h(
          "div",
          { className: classNames("chat-workspace", isSessionTransitioning && "is-transitioning") },
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
              onCompositionStart: () => setIsComposing(true),
              onCompositionEnd: () => setIsComposing(false),
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
        ),
        confirmation
          ? h(ConfirmationDialog, {
              key: "confirmation",
              title: confirmation.title,
              message: confirmation.message,
              onCancel: () => setConfirmation(null),
              onConfirm: handleConfirmation,
            })
          : null,
      ]
    );
  }

  /** 会话删除前的自定义确认弹窗，固定使用“取消”和“确定”按钮。 */
  function ConfirmationDialog({ title, message, onCancel, onConfirm }) {
    return h("div", { className: "confirmation-backdrop", role: "presentation" },
      h(
        "section",
        {
          className: "confirmation-dialog",
          role: "dialog",
          "aria-modal": "true",
          "aria-labelledby": "confirmation-title",
        },
        [
          h("h2", { id: "confirmation-title", key: "title" }, title),
          h("p", { key: "message" }, message),
          h("div", { className: "confirmation-actions", key: "actions" }, [
            h("button", { type: "button", className: "confirmation-cancel", onClick: onCancel, key: "cancel" }, "取消"),
            h("button", { type: "button", className: "confirmation-submit", onClick: onConfirm, key: "confirm" }, "确定"),
          ]),
        ]
      )
    );
  }

  /** 将表格行拆分为单元格文本。 */
  function splitTableCells(line) {
    return line
      .trim()
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim());
  }

  /** 判断一行是否为 Markdown 表格的分隔线。 */
  function isTableDivider(line) {
    return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
  }

  /** 渲染粗体、行内代码和链接等常用 Markdown 行内格式。 */
  function renderInlineMarkdown(text, keyPrefix) {
    const tokenPattern = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^\s)]+\)|https?:\/\/[^\s]+)/g;
    const parts = String(text).split(tokenPattern);
    return parts.filter(Boolean).map((part, index) => {
      const key = `${keyPrefix}-${index}`;
      if (part.startsWith("**") && part.endsWith("**")) {
        return h("strong", { key }, part.slice(2, -2));
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return h("code", { key }, part.slice(1, -1));
      }
      const link = part.match(/^\[([^\]]+)\]\(([^\s)]+)\)$/);
      if (link) {
        return h("a", { key, href: link[2], target: "_blank", rel: "noreferrer" }, link[1]);
      }
      if (/^https?:\/\//.test(part)) {
        return h("a", { key, href: part, target: "_blank", rel: "noreferrer" }, part);
      }
      return part;
    });
  }

  /** 将模型输出转换为可读的标题、段落、列表和表格元素。 */
  function renderMarkdown(content) {
    const lines = String(content || "").replace(/\r\n/g, "\n").split("\n");
    const blocks = [];
    let lineIndex = 0;

    while (lineIndex < lines.length) {
      const line = lines[lineIndex];
      if (!line.trim()) {
        lineIndex += 1;
        continue;
      }

      const heading = line.match(/^(#{1,3})\s+(.+)$/);
      if (heading) {
        const level = heading[1].length;
        blocks.push(h(`h${level}`, { key: `heading-${lineIndex}` }, renderInlineMarkdown(heading[2], `heading-${lineIndex}`)));
        lineIndex += 1;
        continue;
      }

      if (lineIndex + 1 < lines.length && line.includes("|") && isTableDivider(lines[lineIndex + 1])) {
        const headers = splitTableCells(line);
        const rows = [];
        lineIndex += 2;
        while (lineIndex < lines.length && lines[lineIndex].trim() && lines[lineIndex].includes("|")) {
          rows.push(splitTableCells(lines[lineIndex]));
          lineIndex += 1;
        }
        const tableHeader = h(
          "thead",
          { key: "head" },
          h(
            "tr",
            null,
            headers.map((cell, index) =>
              h("th", { key: index }, renderInlineMarkdown(cell, `table-head-${index}`))
            )
          )
        );
        const tableBody = h(
          "tbody",
          { key: "body" },
          rows.map((row, rowIndex) =>
            h(
              "tr",
              { key: rowIndex },
              headers.map((_, cellIndex) =>
                h(
                  "td",
                  { key: cellIndex },
                  renderInlineMarkdown(row[cellIndex] || "", `table-${rowIndex}-${cellIndex}`)
                )
              )
            )
          )
        );
        blocks.push(
          h(
            "div",
            { className: "markdown-table-wrap", key: `table-${lineIndex}` },
            h("table", null, [tableHeader, tableBody])
          )
        );
        continue;
      }

      const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
      const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
      if (unordered || ordered) {
        const isOrdered = Boolean(ordered);
        const items = [];
        while (lineIndex < lines.length) {
          const item = lines[lineIndex].match(isOrdered ? /^\s*\d+[.)]\s+(.+)$/ : /^\s*[-*+]\s+(.+)$/);
          if (!item) break;
          items.push(item[1]);
          lineIndex += 1;
        }
        blocks.push(h(isOrdered ? "ol" : "ul", { key: `list-${lineIndex}` }, items.map((item, index) => h("li", { key: index }, renderInlineMarkdown(item, `list-${lineIndex}-${index}`)))));
        continue;
      }

      const quote = line.match(/^>\s?(.+)$/);
      if (quote) {
        blocks.push(h("blockquote", { key: `quote-${lineIndex}` }, renderInlineMarkdown(quote[1], `quote-${lineIndex}`)));
        lineIndex += 1;
        continue;
      }

      const paragraph = [];
      while (lineIndex < lines.length && lines[lineIndex].trim()) {
        if (paragraph.length && (/^(#{1,3})\s+/.test(lines[lineIndex]) || lines[lineIndex].includes("|") || /^\s*[-*+]\s+/.test(lines[lineIndex]))) break;
        paragraph.push(lines[lineIndex]);
        lineIndex += 1;
      }
      blocks.push(h("p", { key: `paragraph-${lineIndex}` }, paragraph.flatMap((paragraphLine, index) => index ? [h("br", { key: `break-${index}` }), ...renderInlineMarkdown(paragraphLine, `paragraph-${lineIndex}-${index}`)] : renderInlineMarkdown(paragraphLine, `paragraph-${lineIndex}-${index}`))));
    }

    return blocks;
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
        ? "调用中"
        : message.phase === "end"
          ? "已完成"
          : message.phase === "error"
            ? "失败"
            : "";

    if (isTool) {
      return h(
        "article",
        { className: "message-row tool" },
        h("details", { className: "tool-details" }, [
          h("summary", { key: "summary" }, [
            h("span", { className: "tool-badge", key: "badge" }, toolTitle),
            phaseLabel ? h("span", { className: "tool-phase", key: "phase" }, phaseLabel) : null,
          ]),
          h("div", { className: "tool-content", key: "content" }, message.content || " "),
        ])
      );
    }

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
        h(
          "div",
          {
            className: classNames("bubble-content", message.role === "assistant" && "markdown-content", message.pending && "pending"),
          },
          message.role === "assistant" && !message.pending ? renderMarkdown(message.content) : message.content || " "
        )
      )
    );
  }

  createRoot(document.getElementById("root")).render(h(App));
})();
