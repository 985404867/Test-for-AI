"""Local React web UI server."""

from __future__ import annotations

import json
import logging
import mimetypes
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from langchain_starter.agent import ask_agent
from langchain_starter.chat import (
    prepare_web_search_context,
    stream_conversation,
    stream_conversation_with_search_context,
)
from langchain_starter.config import Settings
from langchain_starter.storage import ConversationStore


STATIC_ROOT = Path(__file__).resolve().parent / "static"
logger = logging.getLogger(__name__)


def _messages_from_payload(items: list[dict]) -> list[BaseMessage]:
    """把前端发送的历史消息转换为 LangChain 消息对象。"""
    messages: list[BaseMessage] = []
    for item in items:
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        if role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "user":
            messages.append(HumanMessage(content=content))
    return messages


def _json_line(payload: dict) -> bytes:
    """把事件对象编码成 NDJSON 单行，供前端流式消费。"""
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def _is_port_free(host: str, port: int) -> bool:
    """检查指定端口是否可绑定。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _choose_port(host: str, preferred_port: int) -> int:
    """从首选端口开始向后探测可用端口。"""
    for port in range(preferred_port, preferred_port + 30):
        if _is_port_free(host, port):
            return port
    raise RuntimeError("没有找到可用端口。")


def create_handler(settings: Settings):
    """创建处理静态资源和聊天 API 的 HTTP handler 类。"""
    store = ConversationStore()

    class WebHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            """禁用默认访问日志，避免控制台输出过于嘈杂。"""
            return

        def _send_static(self, path: str) -> None:
            """按请求路径返回前端静态资源。"""
            if path == "/":
                path = "/index.html"

            file_path = (STATIC_ROOT / path.removeprefix("/")).resolve()
            if not str(file_path).startswith(str(STATIC_ROOT.resolve())):
                self.send_error(404)
                return

            if not file_path.exists() or not file_path.is_file():
                self.send_error(404)
                return

            content = file_path.read_bytes()
            content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            if file_path.suffix == ".js":
                content_type = "text/javascript; charset=utf-8"
            elif file_path.suffix in {".html", ".css"}:
                content_type = f"text/{file_path.suffix.removeprefix('.')}; charset=utf-8"

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _send_json(self, payload: dict, status: int = 200) -> None:
            """以 JSON 格式返回 API 响应。"""
            content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self) -> None:
            """处理配置、会话列表、会话消息和静态资源的 GET 请求。"""
            parsed = urlparse(self.path)
            if parsed.path == "/api/config":
                payload = {
                    "model": settings.openai_model,
                    "webSearchEnabled": settings.web_search_enabled,
                    "webSearchProvider": settings.web_search_provider,
                    "maxResults": settings.web_search_max_results,
                    "agentModeEnabled": True,
                }
                self._send_json(payload)
                return

            if parsed.path == "/api/sessions":
                query = parse_qs(parsed.query)
                include_deleted = (query.get("deleted") or ["0"])[0].strip() in {"1", "true", "yes"}
                keyword = (query.get("q") or [""])[0].strip()
                sessions = (
                    store.search_sessions(keyword, include_deleted=include_deleted)
                    if keyword
                    else (store.list_deleted_sessions() if include_deleted else store.list_sessions())
                )
                self._send_json({"sessions": sessions})
                return

            if parsed.path == "/api/session":
                query = parse_qs(parsed.query)
                session_id = (query.get("sessionId") or [""])[0].strip()
                if not session_id:
                    self._send_json({"error": "缺少 sessionId"}, status=400)
                    return
                self._send_json({"messages": store.get_messages(session_id)})
                return

            self._send_static(parsed.path)

        def do_DELETE(self) -> None:
            """处理会话删除请求，支持软删除和永久删除。"""
            parsed = urlparse(self.path)
            if parsed.path != "/api/session":
                self.send_error(404)
                return

            query = parse_qs(parsed.query)
            session_id = (query.get("sessionId") or [""])[0].strip()
            if not session_id:
                self._send_json({"error": "缺少 sessionId"}, status=400)
                return

            purge = (query.get("purge") or ["0"])[0].strip() in {"1", "true", "yes"}
            deleted = store.purge_session(session_id) if purge else store.delete_session(session_id)
            logger.info(
                "Deleted chat session session=%s deleted=%s purge=%s",
                session_id,
                deleted,
                purge,
            )
            self._send_json({"deleted": deleted, "purged": purge})

        def do_PATCH(self) -> None:
            """处理会话重命名和恢复请求。"""
            parsed = urlparse(self.path)
            if parsed.path != "/api/session":
                self.send_error(404)
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                self.send_error(400, f"请求格式错误：{exc}")
                return

            session_id = str(payload.get("sessionId", "")).strip()
            if not session_id:
                self._send_json({"error": "缺少 sessionId"}, status=400)
                return

            if payload.get("restore"):
                ok = store.restore_session(session_id)
                self._send_json({"restored": ok})
                return

            title = str(payload.get("title", "")).strip()
            if not title:
                self._send_json({"error": "缺少 title"}, status=400)
                return

            try:
                ok = store.rename_session(session_id, title)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json({"renamed": ok, "title": title})

        def do_POST(self) -> None:
            """处理聊天请求，并以 NDJSON 流式返回结果。"""
            parsed = urlparse(self.path)
            if parsed.path != "/api/chat":
                self.send_error(404)
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                question = str(payload.get("message", "")).strip()
                use_web_search = bool(payload.get("webSearch", False))
                use_agent = bool(payload.get("agentMode", False))
                session_id = str(payload.get("sessionId", "")).strip()
                history = _messages_from_payload(payload.get("history", []))
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
                self.send_error(400, f"请求格式错误：{exc}")
                return

            if not question:
                self.send_error(400, "消息不能为空。")
                return
            if not session_id:
                self.send_error(400, "缺少 sessionId。")
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()

            try:
                logger.info(
                    "Chat request session=%s agent=%s web_search=%s chars=%d",
                    session_id,
                    use_agent,
                    use_web_search,
                    len(question),
                )
                store.ensure_session(session_id, title=question[:40] or "新会话")
                store.add_message(session_id, "user", question)

                if use_agent:
                    self.wfile.write(
                        _json_line({"type": "status", "content": "Agent 正在规划工具调用..."})
                    )
                    self.wfile.flush()
                    latest_tool_event: dict | None = None

                    def emit_tool_event(event: dict) -> None:
                        nonlocal latest_tool_event
                        # 界面只保留本轮最后一条工具状态，历史会话也不重复保存多次检索。
                        if event.get("phase") != "start":
                            latest_tool_event = event
                        self.wfile.write(_json_line({"type": "tool", **event}))
                        self.wfile.flush()

                    answer, _updated_history = ask_agent(
                        question,
                        history,
                        settings,
                        on_tool_event=emit_tool_event,
                    )
                    if latest_tool_event is not None:
                        content = (
                            f"{latest_tool_event.get('phase', '')}: {latest_tool_event.get('tool', '')}\n"
                            f"输入：{latest_tool_event.get('input', '')}\n"
                            f"结果：{latest_tool_event.get('error') or latest_tool_event.get('preview') or ''}"
                        ).strip()
                        store.add_message(
                            session_id,
                            "tool",
                            content,
                            metadata=latest_tool_event,
                        )
                    self.wfile.write(_json_line({"type": "chunk", "content": answer}))
                    self.wfile.flush()
                    store.add_message(session_id, "assistant", answer, metadata={"agentMode": True})
                    self.wfile.write(_json_line({"type": "done"}))
                    self.wfile.flush()
                    return
                elif use_web_search:
                    self.wfile.write(_json_line({"type": "status", "content": "正在联网搜索..."}))
                    self.wfile.flush()
                    search_context = prepare_web_search_context(question, settings)
                    self.wfile.write(
                        _json_line({"type": "status", "content": "正在生成回答..."})
                    )
                    self.wfile.flush()
                    chunks = stream_conversation_with_search_context(
                        question,
                        history,
                        search_context,
                        settings,
                    )
                else:
                    chunks = stream_conversation(question, history, settings)

                answer_chunks: list[str] = []
                for chunk in chunks:
                    answer_chunks.append(chunk)
                    self.wfile.write(_json_line({"type": "chunk", "content": chunk}))
                    self.wfile.flush()
                answer = "".join(answer_chunks)
                store.add_message(
                    session_id,
                    "assistant",
                    answer,
                    metadata={"webSearch": use_web_search, "agentMode": False},
                )
                self.wfile.write(_json_line({"type": "done"}))
                self.wfile.flush()
            except Exception as exc:  # noqa: BLE001 - surface backend errors in the UI.
                logger.exception("Chat request failed session=%s", session_id)
                self.wfile.write(_json_line({"type": "error", "content": str(exc)}))
                self.wfile.flush()

    return WebHandler


def run_web_app(settings: Settings, host: str = "127.0.0.1", port: int = 8000) -> None:
    """启动本地 React Web 服务。"""

    selected_port = _choose_port(host, port)
    server = ThreadingHTTPServer((host, selected_port), create_handler(settings))
    url = f"http://{host}:{selected_port}"
    print(f"Web GUI 已启动：{url}")
    print("按 Ctrl+C 停止服务。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb GUI 已停止。")
    finally:
        server.server_close()
