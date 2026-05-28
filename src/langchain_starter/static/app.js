(function () {
  const { createElement: h, useEffect, useMemo, useRef, useState } = React;
  const { createRoot } = ReactDOM;

  const initialMessages = [
    {
      role: "system",
      content: "欢迎使用 LangChain Starter。可以开启 Agent 模式，让模型自动调用联网搜索和本地知识库。",
    },
  ];

  function nowLabel() {
    return new Date().toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function classNames(...values) {
    return values.filter(Boolean).join(" ");
  }

  function formatSessionTime(value) {
    if (!value) return "";
    const date = new Date(`${value.replace(" ", "T")}Z`);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleDateString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
    });
  }

  function getOrCreateSessionId() {
    const key = "langchain-starter-session-id";
    let sessionId = localStorage.getItem(key);
    if (!sessionId) {
      sessionId = crypto.randomUUID();
      localStorage.setItem(key, sessionId);
    }
    return sessionId;
  }

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

    useEffect(() => {
      fetch("/api/config")
        .then((response) => response.json())
        .then((data) => {
          setConfig(data);
          setWebSearch(Boolean(data.webSearchEnabled));
          setAgentMode(Boolean(data.agentModeEnabled));
        })
        .catch(() => setStatus("配置读取失败"));
    }, []);

    async function refreshSessions() {
      try {
        const response = await fetch("/api/sessions");
        const data = await response.json();
        setSessions(Array.isArray(data.sessions) ? data.sessions : []);
      } catch {
        setStatus("历史会话读取失败");
      }
    }

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

    async function copyText(text) {
      await navigator.clipboard.writeText(text);
      setStatus("已复制");
      window.setTimeout(() => setStatus("就绪"), 1200);
    }

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

    function startNewSession() {
      const nextSessionId = crypto.randomUUID();
      localStorage.setItem(sessionStorageKey, nextSessionId);
      setSessionId(nextSessionId);
      setMessages(initialMessages);
      setStatus("新对话");
      window.setTimeout(refreshSessions, 300);
      inputRef.current?.focus();
    }

    function switchSession(nextSessionId) {
      if (!nextSessionId || nextSessionId === sessionId || isThinking) return;
      loadSession(nextSessionId);
    }

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
            webSearch: agentMode ? false : webSearch,
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
            sessionsForList.map((session) =>
              h(
                "button",
                {
                  className: classNames("session-item", session.id === sessionId && "active"),
                  onClick: () => switchSession(session.id),
                  disabled: isThinking,
                  key: session.id,
                  title: session.title || "新会话",
                },
                [
                  h("span", { className: "session-title", key: "title" }, session.title || "新会话"),
                  h("span", { className: "session-time", key: "time" }, formatSessionTime(session.updated_at)),
                ]
              )
            )
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
              h(
                "strong",
                { key: "title" },
                sessionsForList.find((session) => session.id === sessionId)?.title || "新会话"
              ),
            ]),
            h("div", { className: "toolbar-actions" }, [
              h("button", { className: "ghost-button", onClick: copyAll, key: "copy" }, "复制全部"),
              h("span", { className: "status-pill", key: "status" }, status),
            ])
          ),
          h(
            "div",
            { className: "chat-panel", ref: listRef },
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
            h(
              "div",
              { className: "mode-bar" },
              h(
                "label",
                { className: "search-toggle" },
                h("input", {
                  type: "checkbox",
                  checked: agentMode,
                  onChange: (event) => setAgentMode(event.target.checked),
                }),
                h("span", null, "Agent")
              ),
              h(
                "label",
                { className: classNames("search-toggle", agentMode && "disabled") },
                h("input", {
                  type: "checkbox",
                  checked: webSearch,
                  onChange: (event) => setWebSearch(event.target.checked),
                  disabled: agentMode,
                }),
                h("span", null, "联网")
              )
            ),
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

  function MessageBubble({ message, onCopy }) {
    const label =
      message.role === "user"
        ? "你"
        : message.role === "assistant"
          ? "AI"
          : message.role === "tool"
            ? "工具"
            : "系统";
    return h(
      "article",
      { className: classNames("message-row", message.role) },
      h(
        "div",
        { className: "bubble" },
        h("div", { className: "bubble-meta" }, [
          h("span", { key: "label" }, label),
          h(
            "button",
            { key: "copy", onClick: () => onCopy(message.content), className: "copy-link" },
            "复制"
          ),
        ]),
        h("div", { className: "bubble-content" }, message.content || " ")
      )
    );
  }

  createRoot(document.getElementById("root")).render(h(App));
})();
