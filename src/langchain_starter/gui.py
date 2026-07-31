"""Tkinter desktop chat window."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from langchain_starter.chat import (
    prepare_web_search_context,
    stream_conversation,
    stream_conversation_with_search_context,
)
from langchain_starter.config import Settings
from langchain_starter.storage import ConversationStore


class ChatWindow:
    """桌面聊天窗口，负责渲染消息、滚动、复制和发送。"""

    def __init__(self, root: tk.Tk, settings: Settings) -> None:
        """初始化桌面窗口、恢复会话并搭建主要 UI。"""
        self.root = root
        self.settings = settings
        self.store = ConversationStore()
        self.session_id = self.store.get_latest_session_id() or self.store.create_session()
        self.history: list[BaseMessage] = []
        self.transcript: list[tuple[str, str]] = []
        self.is_waiting = False
        self.message_count = 0
        self._scroll_remainder = 0.0
        self.web_search_enabled = tk.BooleanVar(value=True)

        self.root.title("LangChain Starter")
        self.root.geometry("960x720")
        self.root.minsize(700, 540)
        self.root.resizable(True, True)
        self.root.configure(bg="#f5f5f7")

        self._configure_style()
        self._build_widgets()
        self._load_persisted_messages()
        self._bring_to_front()
        self.root.bind_all("<Command-c>", self.copy_selected_text)
        self.root.bind_all("<Control-c>", self.copy_selected_text)

    def _bring_to_front(self) -> None:
        """启动时把窗口提到最前面，便于用户立即看到聊天界面。"""

        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self.root.after(1200, lambda: self.root.attributes("-topmost", False))

    def _configure_style(self) -> None:
        """配置整体视觉样式，统一字体、颜色和按钮外观。"""
        style = ttk.Style()
        if "aqua" in style.theme_names():
            style.theme_use("aqua")
        else:
            style.theme_use("clam")

        self.font_family = "SF Pro Text"
        self.title_font = (self.font_family, 19, "bold")
        self.body_font = (self.font_family, 13)
        self.small_font = (self.font_family, 11)
        self.small_bold_font = (self.font_family, 10, "bold")

        style.configure("Root.TFrame", background="#f5f5f7")
        style.configure("Header.TFrame", background="#f5f5f7")
        style.configure("Chat.TFrame", background="#f5f5f7")
        style.configure("Composer.TFrame", background="#f5f5f7")
        style.configure(
            "Title.TLabel",
            background="#f5f5f7",
            foreground="#1d1d1f",
            font=self.title_font,
        )
        style.configure(
            "Subtitle.TLabel",
            background="#f5f5f7",
            foreground="#6e6e73",
            font=self.small_font,
        )
        style.configure(
            "Status.TLabel",
            background="#f5f5f7",
            foreground="#6e6e73",
            font=self.small_font,
        )
        style.configure(
            "Send.TButton",
            font=(self.font_family, 12, "bold"),
            padding=(18, 10),
            background="#007aff",
            foreground="#ffffff",
            borderwidth=0,
        )
        style.map(
            "Send.TButton",
            background=[("disabled", "#a7c7f7"), ("active", "#006ee6")],
            foreground=[("disabled", "#ffffff"), ("active", "#ffffff")],
        )
        style.configure("Ghost.TButton", font=self.small_font, padding=(12, 7))

    def _build_widgets(self) -> None:
        """构建标题栏、消息区、输入区和操作按钮。"""
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=(22, 18), style="Root.TFrame")
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        header = ttk.Frame(main, padding=(4, 0, 4, 12), style="Header.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.columnconfigure(0, weight=1)

        title = ttk.Label(header, text="LangChain Starter", style="Title.TLabel")
        title.grid(row=0, column=0, sticky="w")

        subtitle = ttk.Label(
            header,
            text=f"当前模型：{self.settings.openai_model}",
            style="Subtitle.TLabel",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.status_label = ttk.Label(header, text="就绪", style="Status.TLabel")
        self.status_label.grid(row=0, column=1, sticky="e")

        copy_all_button = ttk.Button(
            header,
            text="复制全部",
            style="Ghost.TButton",
            command=self.copy_all_messages,
        )
        copy_all_button.grid(row=1, column=1, sticky="e", pady=(6, 0))

        paned = ttk.PanedWindow(main, orient=tk.VERTICAL)
        paned.grid(row=1, column=0, sticky="nsew")

        chat_shell = ttk.Frame(paned, style="Chat.TFrame")
        chat_shell.columnconfigure(0, weight=1)
        chat_shell.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            chat_shell,
            bg="#f5f5f7",
            bd=0,
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(chat_shell, orient=tk.VERTICAL, command=self.canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.messages_frame = ttk.Frame(self.canvas, padding=(6, 8), style="Chat.TFrame")
        self.messages_window = self.canvas.create_window(
            (0, 0),
            window=self.messages_frame,
            anchor="nw",
        )
        self.messages_frame.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_messages_frame)
        self._bind_history_scroll(self.canvas)
        self._bind_history_scroll(self.messages_frame)

        composer = ttk.Frame(paned, padding=(4, 14, 4, 4), style="Composer.TFrame")
        composer.columnconfigure(0, weight=1)

        self.input_text = tk.Text(
            composer,
            height=4,
            wrap=tk.WORD,
            font=self.body_font,
            bg="#ffffff",
            fg="#1d1d1f",
            insertbackground="#007aff",
            relief=tk.FLAT,
            padx=14,
            pady=12,
            undo=True,
            highlightthickness=1,
            highlightbackground="#d2d2d7",
            highlightcolor="#007aff",
        )
        self.input_text.grid(row=0, column=0, columnspan=4, sticky="ew")
        self.input_text.bind("<Return>", self._send_on_return)
        self.input_text.bind("<Shift-Return>", self._insert_newline)

        hint = ttk.Label(
            composer,
            text="Enter 发送，Shift + Enter 换行",
            style="Subtitle.TLabel",
        )
        hint.grid(row=1, column=0, sticky="w", pady=(10, 0))

        search_toggle = ttk.Checkbutton(
            composer,
            text="联网搜索",
            variable=self.web_search_enabled,
        )
        search_toggle.grid(row=1, column=1, sticky="e", padx=(10, 0), pady=(10, 0))

        clear_button = ttk.Button(
            composer,
            text="新对话",
            style="Ghost.TButton",
            command=self.start_new_session,
        )
        clear_button.grid(row=1, column=2, sticky="e", padx=(10, 0), pady=(10, 0))

        self.send_button = ttk.Button(
            composer,
            text="发送",
            style="Send.TButton",
            command=self.send_message,
        )
        self.send_button.grid(row=1, column=3, sticky="e", padx=(10, 0), pady=(10, 0))

        size_grip = ttk.Sizegrip(composer)
        size_grip.grid(row=2, column=3, sticky="se", pady=(4, 0))

        paned.add(chat_shell, weight=4)
        paned.add(composer, weight=1)

        self.input_text.focus_set()

    def _load_persisted_messages(self) -> None:
        """从 SQLite 恢复最近会话的聊天记录。"""
        messages = self.store.get_messages(self.session_id)
        if not messages:
            self._append_message(
                "系统",
                "输入问题开始对话。聊天记录会保存在本地 SQLite，重启后可恢复。"
                "支持触摸板/鼠标滚轮浏览历史，选中文本后按 Command+C 复制。",
            )
            return

        for message in messages:
            role = message["role"]
            content = message["content"]
            if role == "user":
                self.history.append(HumanMessage(content=content))
                self._append_message("你", content)
            elif role == "assistant":
                self.history.append(AIMessage(content=content))
                self._append_message("AI", content)
            elif role == "tool":
                self._append_message("工具", content)
            else:
                self._append_message("系统", content)
        self.status_label.configure(text="已恢复历史")

    def _update_scroll_region(self, _event: tk.Event) -> None:
        """在消息内容变化后刷新画布滚动范围。"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_messages_frame(self, event: tk.Event) -> None:
        """在窗口宽度变化时同步调整消息容器宽度。"""
        self.canvas.itemconfigure(self.messages_window, width=event.width)

    def _bind_history_scroll(self, widget: tk.Widget) -> None:
        """给消息区域绑定鼠标和触摸板滚动事件。"""
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        widget.bind("<Button-4>", self._on_scroll_up, add="+")
        widget.bind("<Button-5>", self._on_scroll_down, add="+")

    def _scroll_history_pixels(self, pixels: float) -> str:
        """按像素滚动消息历史，提升滚动手感。"""
        bbox = self.canvas.bbox("all")
        if not bbox:
            return "break"

        content_top = bbox[1]
        content_height = max(1, bbox[3] - bbox[1])
        viewport_height = self.canvas.winfo_height()
        max_offset = max(0, content_height - viewport_height)
        if max_offset == 0:
            return "break"

        current_offset = self.canvas.canvasy(0) - content_top
        next_offset = min(max(current_offset + pixels, 0), max_offset)
        self.canvas.yview_moveto(next_offset / content_height)
        return "break"

    def _on_mousewheel(self, event: tk.Event) -> None:
        """处理鼠标滚轮或触摸板滚动事件。"""
        if event.delta == 0:
            return "break"

        # macOS trackpads send small deltas; mouse wheels often send +/-120.
        # A pixel-based accumulator keeps trackpad movement smooth and less jumpy.
        scaled_pixels = -event.delta * 1.4175
        total_pixels = self._scroll_remainder + scaled_pixels
        whole_pixels = int(total_pixels)
        self._scroll_remainder = total_pixels - whole_pixels
        if whole_pixels == 0:
            whole_pixels = -1 if event.delta > 0 else 1
            self._scroll_remainder = 0.0
        return self._scroll_history_pixels(whole_pixels)

    def _on_scroll_up(self, _event: tk.Event) -> str:
        """兼容 Linux/部分环境的向上滚动事件。"""
        return self._scroll_history_pixels(-72)

    def _on_scroll_down(self, _event: tk.Event) -> str:
        """兼容 Linux/部分环向下滚动事件。"""
        return self._scroll_history_pixels(72)

    def _scroll_to_bottom(self) -> None:
        """将消息区域自动滚到底部，方便查看最新回复。"""
        self.root.after(10, lambda: self.canvas.yview_moveto(1.0))

    def _copy_to_clipboard(self, text: str) -> None:
        """把文本写入系统剪贴板，并提示复制成功。"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_label.configure(text="已复制")

    def _copy_text_widget(self, widget: tk.Text) -> None:
        """复制单个消息气泡里的文本内容。"""
        self._copy_to_clipboard(widget.get("1.0", "end-1c"))

    def copy_selected_text(self, _event: tk.Event | None = None) -> str | None:
        """复制当前选中的文本，便于快捷键操作。"""
        widget = self.root.focus_get()
        if not isinstance(widget, tk.Text):
            return None

        try:
            selected_text = widget.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            return None

        self._copy_to_clipboard(selected_text)
        return "break"

    def copy_all_messages(self) -> None:
        """复制当前会话的完整聊天记录。"""
        if not self.transcript:
            return

        text = "\n\n".join(
            f"{speaker}：\n{content}" for speaker, content in self.transcript
        )
        self._copy_to_clipboard(text)

    def _send_on_return(self, _event: tk.Event) -> str:
        """按回车键发送消息。"""
        self.send_message()
        return "break"

    def _insert_newline(self, _event: tk.Event) -> None:
        """按 Shift+Enter 在输入框中插入换行。"""
        self.input_text.insert(tk.INSERT, "\n")

    def _insert_message_bubble(
        self,
        speaker: str,
        content: str,
        *,
        align: str,
        bubble_bg: str,
        text_fg: str,
        label_fg: str,
    ) -> tk.Text:
        """创建一条消息气泡，用于用户、AI、系统或工具输出。"""
        row = ttk.Frame(self.messages_frame, style="Chat.TFrame")
        row.grid(row=self.message_count, column=0, sticky="ew", pady=6)
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=0)
        row.columnconfigure(2, weight=1)
        self._bind_history_scroll(row)

        bubble_column = 1 if align == "center" else 0 if align == "left" else 2
        sticky = "w" if align == "left" else "e" if align == "right" else ""
        max_width = 560 if align != "center" else 680

        bubble = tk.Frame(row, bg=bubble_bg, padx=15, pady=11, bd=0)
        bubble.grid(row=0, column=bubble_column, sticky=sticky)
        self._bind_history_scroll(bubble)

        speaker_label = tk.Label(
            bubble,
            text=speaker,
            bg=bubble_bg,
            fg=label_fg,
            font=self.small_bold_font,
            anchor="w",
            justify=tk.LEFT,
        )
        speaker_label.grid(row=0, column=0, sticky="w")
        self._bind_history_scroll(speaker_label)

        copy_button = tk.Button(
            bubble,
            text="复制",
            bg=bubble_bg,
            fg=label_fg,
            activebackground=bubble_bg,
            activeforeground=label_fg,
            borderwidth=0,
            highlightthickness=0,
            cursor="hand2",
            font=self.small_font,
        )
        copy_button.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self._bind_history_scroll(copy_button)

        content_lines = content.splitlines() or [content]
        estimated_lines = sum(max(1, (len(line) // 58) + 1) for line in content_lines)
        content_height = max(2, estimated_lines)
        content_width = 62 if align != "center" else 76

        content_text = tk.Text(
            bubble,
            bg=bubble_bg,
            fg=text_fg,
            font=self.body_font,
            wrap=tk.WORD,
            width=content_width,
            height=content_height,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            cursor="xterm",
            spacing1=1,
            spacing2=2,
            spacing3=3,
            selectbackground="#acd7ff",
            selectforeground="#1d1d1f",
        )
        content_text.insert("1.0", content)
        content_text.configure(state=tk.DISABLED)
        content_text.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))
        self._bind_history_scroll(content_text)
        copy_button.configure(command=lambda: self._copy_text_widget(content_text))

        self.message_count += 1
        return content_text

    def _append_message(
        self,
        speaker: str,
        content: str,
        *,
        record: bool = True,
    ) -> tk.Text:
        """把一条消息追加到聊天记录中，并滚动到最新位置。"""
        if record:
            self.transcript.append((speaker, content))
        if speaker == "你":
            text_widget = self._insert_message_bubble(
                speaker,
                content,
                align="right",
                bubble_bg="#007aff",
                text_fg="#ffffff",
                label_fg="#d7ebff",
            )
        elif speaker == "AI":
            text_widget = self._insert_message_bubble(
                speaker,
                content,
                align="left",
                bubble_bg="#e9e9eb",
                text_fg="#1d1d1f",
                label_fg="#6e6e73",
            )
        else:
            text_widget = self._insert_message_bubble(
                speaker,
                content,
                align="center",
                bubble_bg="#f2f2f7",
                text_fg="#3a3a3c",
                label_fg="#8e8e93",
            )
        self._scroll_to_bottom()
        return text_widget

    def _append_stream_chunk(self, widget: tk.Text, chunk: str) -> None:
        """把流式输出追加到正在生成的 AI 消息里。"""
        widget.configure(state=tk.NORMAL)
        if getattr(widget, "_is_pending_answer", False):
            widget.delete("1.0", tk.END)
            widget._is_pending_answer = False
        widget.insert(tk.END, chunk)
        content = widget.get("1.0", "end-1c")
        estimated_lines = sum(
            max(1, (len(line) // 58) + 1) for line in (content.splitlines() or [content])
        )
        widget.configure(height=max(2, estimated_lines))
        widget.configure(state=tk.DISABLED)
        self._scroll_to_bottom()

    def _set_waiting(self, waiting: bool) -> None:
        """切换发送中状态，并同步按钮和状态栏。"""
        self.is_waiting = waiting
        self.send_button.configure(text="思考中..." if waiting else "发送")
        self.send_button.configure(state=tk.DISABLED if waiting else tk.NORMAL)
        status = "模型正在回复..." if waiting else "就绪"
        self.status_label.configure(text=status)

    def start_new_session(self) -> None:
        """创建新的本地会话，开始一段全新的对话。"""
        if self.is_waiting:
            return

        self.session_id = self.store.create_session()
        self.history = []
        self.transcript = []
        self.message_count = 0
        for child in self.messages_frame.winfo_children():
            child.destroy()
        self._append_message("系统", "已创建新对话，可以开始新的上下文。")
        self.status_label.configure(text="新对话")

    def send_message(self) -> None:
        """读取输入框内容并异步请求模型回复。"""
        if self.is_waiting:
            return

        question = self.input_text.get("1.0", tk.END).strip()
        if not question:
            return

        self.input_text.delete("1.0", tk.END)
        self._append_message("你", question)
        self.store.ensure_session(self.session_id, title=question[:40] or "新会话")
        self.store.add_message(self.session_id, "user", question)
        use_web_search = self.web_search_enabled.get()
        self._set_waiting(True)
        if use_web_search:
            self.status_label.configure(text="正在联网搜索...")

        thread = threading.Thread(
            target=self._ask_model,
            args=(question, list(self.history), use_web_search),
            daemon=True,
        )
        thread.start()

    def _ask_model(
        self,
        question: str,
        history: list[BaseMessage],
        use_web_search: bool,
    ) -> None:
        """在线程中调用模型并把流式结果回传到 UI。"""
        answer_chunks: list[str] = []
        search_context = ""
        stream_ready = threading.Event()
        stream_widget_holder: dict[str, tk.Text] = {}

        def create_stream_message() -> None:
            widget = self._append_message("AI", "思考中...", record=False)
            widget._is_pending_answer = True
            stream_widget_holder["widget"] = widget
            stream_ready.set()

        try:
            if use_web_search:
                search_context = prepare_web_search_context(question, self.settings)
                self.root.after(
                    0,
                    self._append_message,
                    "系统",
                    "已联网搜索，正在流式生成回答。",
                )
                stream_iterator = stream_conversation_with_search_context(
                    question,
                    history,
                    search_context,
                    self.settings,
                )
            else:
                stream_iterator = stream_conversation(question, history, self.settings)

            self.root.after(0, create_stream_message)
            stream_ready.wait()
            stream_widget = stream_widget_holder["widget"]

            for chunk in stream_iterator:
                answer_chunks.append(chunk)
                self.root.after(0, self._append_stream_chunk, stream_widget, chunk)
        except Exception as exc:  # noqa: BLE001 - show API/config errors in the UI.
            self.root.after(0, self._show_error, exc)
            return

        answer = "".join(answer_chunks)
        updated_history = [*history, HumanMessage(content=question), AIMessage(content=answer)]
        self.root.after(0, self._finish_stream_answer, answer, updated_history)

    def _finish_stream_answer(
        self,
        answer: str,
        updated_history: list[BaseMessage],
    ) -> None:
        """在流式输出结束后，提交历史记录并恢复可交互状态。"""
        self.history = updated_history
        self.transcript.append(("AI", answer))
        self.store.add_message(
            self.session_id,
            "assistant",
            answer,
            metadata={"webSearch": self.web_search_enabled.get()},
        )
        self._set_waiting(False)

    def _show_error(self, exc: Exception) -> None:
        """把请求失败信息展示给用户。"""
        self._set_waiting(False)
        messagebox.showerror("调用失败", str(exc))
        self._append_message("系统", f"调用失败：{exc}")


def run_chat_window(settings: Settings) -> None:
    """打开桌面聊天窗口。"""

    root = tk.Tk()
    ChatWindow(root, settings)
    root.mainloop()
