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


class ChatWindow:
    """A polished desktop chat UI for continuous conversations."""

    def __init__(self, root: tk.Tk, settings: Settings) -> None:
        self.root = root
        self.settings = settings
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
        self._bring_to_front()
        self.root.bind_all("<Command-c>", self.copy_selected_text)
        self.root.bind_all("<Control-c>", self.copy_selected_text)

    def _bring_to_front(self) -> None:
        """Bring the window to the front on launch without keeping it pinned."""

        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self.root.after(1200, lambda: self.root.attributes("-topmost", False))

    def _configure_style(self) -> None:
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
            text="清空对话",
            style="Ghost.TButton",
            command=self.clear_messages,
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

        self._append_message(
            "系统",
            "输入问题开始对话。我会记住当前窗口里的上下文。"
            "支持触摸板/鼠标滚轮浏览历史，选中文本后按 Command+C 复制。",
        )
        self.input_text.focus_set()

    def _update_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_messages_frame(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.messages_window, width=event.width)

    def _bind_history_scroll(self, widget: tk.Widget) -> None:
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        widget.bind("<Button-4>", self._on_scroll_up, add="+")
        widget.bind("<Button-5>", self._on_scroll_down, add="+")

    def _scroll_history_pixels(self, pixels: float) -> str:
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
        return self._scroll_history_pixels(-72)

    def _on_scroll_down(self, _event: tk.Event) -> str:
        return self._scroll_history_pixels(72)

    def _scroll_to_bottom(self) -> None:
        self.root.after(10, lambda: self.canvas.yview_moveto(1.0))

    def _copy_to_clipboard(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_label.configure(text="已复制")

    def _copy_text_widget(self, widget: tk.Text) -> None:
        self._copy_to_clipboard(widget.get("1.0", "end-1c"))

    def copy_selected_text(self, _event: tk.Event | None = None) -> str | None:
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
        if not self.transcript:
            return

        text = "\n\n".join(
            f"{speaker}：\n{content}" for speaker, content in self.transcript
        )
        self._copy_to_clipboard(text)

    def _send_on_return(self, _event: tk.Event) -> str:
        self.send_message()
        return "break"

    def _insert_newline(self, _event: tk.Event) -> None:
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
        widget.configure(state=tk.NORMAL)
        widget.insert(tk.END, chunk)
        content = widget.get("1.0", "end-1c")
        estimated_lines = sum(
            max(1, (len(line) // 58) + 1) for line in (content.splitlines() or [content])
        )
        widget.configure(height=max(2, estimated_lines))
        widget.configure(state=tk.DISABLED)
        self._scroll_to_bottom()

    def _set_waiting(self, waiting: bool) -> None:
        self.is_waiting = waiting
        self.send_button.configure(text="思考中..." if waiting else "发送")
        self.send_button.configure(state=tk.DISABLED if waiting else tk.NORMAL)
        status = "模型正在回复..." if waiting else "就绪"
        self.status_label.configure(text=status)

    def clear_messages(self) -> None:
        if self.is_waiting:
            return

        self.history = []
        self.transcript = []
        self.message_count = 0
        for child in self.messages_frame.winfo_children():
            child.destroy()
        self._append_message("系统", "对话已清空，可以开始新的上下文。")

    def send_message(self) -> None:
        if self.is_waiting:
            return

        question = self.input_text.get("1.0", tk.END).strip()
        if not question:
            return

        self.input_text.delete("1.0", tk.END)
        self._append_message("你", question)
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
        answer_chunks: list[str] = []
        search_context = ""
        stream_ready = threading.Event()
        stream_widget_holder: dict[str, tk.Text] = {}

        def create_stream_message() -> None:
            stream_widget_holder["widget"] = self._append_message("AI", "", record=False)
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
        self.history = updated_history
        self.transcript.append(("AI", answer))
        self._set_waiting(False)

    def _show_error(self, exc: Exception) -> None:
        self._set_waiting(False)
        messagebox.showerror("调用失败", str(exc))
        self._append_message("系统", f"调用失败：{exc}")


def run_chat_window(settings: Settings) -> None:
    """Open the desktop chat window."""

    root = tk.Tk()
    ChatWindow(root, settings)
    root.mainloop()
