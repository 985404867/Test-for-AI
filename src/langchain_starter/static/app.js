(function () {
  const { createElement: h, useEffect, useMemo, useRef, useState } = React;
  const { createRoot } = ReactDOM;

  const initialMessages = [
    {
      role: "system",
      content: "欢迎使用 LangChain Starter。默认开启联网搜索，回答会流式显示。",
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

  function App() {
    const [config, setConfig] = useState({
      model: "loading",
      webSearchEnabled: true,
      webSearchProvider: "baidu",
    });
    const [messages, setMessages] = useState(initialMessages);
    const [input, setInput] = useState("");
    const [webSearch, setWebSearch] = useState(true);
    const [status, setStatus] = useState("就绪");
    const [isThinking, setIsThinking] = useState(false);
    const listRef = useRef(null);
    const inputRef = useRef(null);

    useEffect(() => {
      fetch("/api/config")
        .then((response) => response.json())
        .then((data) => {
          setConfig(data);
          setWebSearch(Boolean(data.webSearchEnabled));
        })
        .catch(() => setStatus("配置读取失败"));
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
        .map((message) => `${message.role === "user" ? "你" : message.role === "assistant" ? "AI" : "系统"}：\n${message.content}`)
        .join("\n\n");
      await copyText(transcript);
    }

    async function sendMessage() {
      const question = input.trim();
      if (!question || isThinking) return;

      const assistantId = crypto.randomUUID();
      setInput("");
      setIsThinking(true);
      setStatus(webSearch ? "正在联网搜索..." : "正在生成回答...");
      setMessages((current) => [
        ...current,
        { role: "user", content: question, time: nowLabel() },
        { role: "assistant", content: "", time: nowLabel(), id: assistantId },
      ]);

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: question,
            webSearch,
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
            } else if (event.type === "chunk") {
              setMessages((current) =>
                current.map((message) =>
                  message.id === assistantId
                    ? { ...message, content: message.content + event.content }
                    : message
                )
              );
            } else if (event.type === "error") {
              throw new Error(event.content);
            }
          }
        }

        setStatus("就绪");
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
          "header",
          { className: "toolbar" },
          h("div", { className: "traffic-lights", "aria-hidden": "true" }, [
            h("span", { className: "light red", key: "red" }),
            h("span", { className: "light yellow", key: "yellow" }),
            h("span", { className: "light green", key: "green" }),
          ]),
          h("div", { className: "title-block" }, [
            h("h1", { key: "title" }, "LangChain Starter"),
            h(
              "p",
              { key: "subtitle" },
              `DeepSeek 对话 · ${config.model} · 搜索源 ${config.webSearchProvider}`
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
            "label",
            { className: "search-toggle" },
            h("input", {
              type: "checkbox",
              checked: webSearch,
              onChange: (event) => setWebSearch(event.target.checked),
            }),
            h("span", null, "联网搜索")
          ),
          h("textarea", {
            ref: inputRef,
            value: input,
            placeholder: "输入消息，Enter 发送，Shift + Enter 换行",
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
    );
  }

  function MessageBubble({ message, onCopy }) {
    const label =
      message.role === "user" ? "你" : message.role === "assistant" ? "AI" : "系统";
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
