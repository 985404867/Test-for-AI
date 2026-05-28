import io
import json
from pathlib import Path
from tempfile import mkdtemp

import pytest

import langchain_starter.web_server as web_server
from langchain_starter.config import Settings
from langchain_starter.storage import ConversationStore


def _settings() -> Settings:
    return Settings(
        openai_api_key="test-key",
        openai_model="gpt-4.1-mini",
        openai_base_url=None,
        openai_temperature=0.2,
        openai_max_tokens=8192,
        auto_continue_enabled=True,
        auto_continue_max_rounds=4,
        embedding_provider="local",
        embedding_model="text-embedding-3-small",
        retriever_k=4,
        knowledge_path=Path("data/knowledge.md"),
        web_search_enabled=False,
        web_search_provider="baidu",
        web_search_max_results=5,
        web_search_timeout=8,
        web_search_fetch_pages=True,
        web_search_page_chars=1600,
    )


class _DummyHeaders(dict):
    def get(self, key, default=None):  # noqa: A003 - match header API
        return super().get(key, default)


def _make_handler(handler_class, path: str, *, body: dict | None = None):
    handler = handler_class.__new__(handler_class)
    handler.path = path
    payload = json.dumps(body or {}, ensure_ascii=False).encode("utf-8")
    handler.rfile = io.BytesIO(payload)
    handler.wfile = io.BytesIO()
    handler.headers = _DummyHeaders({"Content-Length": str(len(payload))})
    handler.status_code = None
    handler.sent_headers = []
    handler.response_body = None

    def send_response(status):
        handler.status_code = status

    def send_header(name, value):
        handler.sent_headers.append((name, value))

    def end_headers():
        return None

    def send_error(status, message=None):
        handler.status_code = status
        handler.response_body = json.dumps({"error": message or ""}, ensure_ascii=False).encode("utf-8")

    handler.send_response = send_response
    handler.send_header = send_header
    handler.end_headers = end_headers
    handler.send_error = send_error
    return handler


@pytest.fixture()
def handler_factory(monkeypatch):
    store = ConversationStore(Path(mkdtemp()) / "conversations.sqlite3")
    monkeypatch.setattr(web_server, "ConversationStore", lambda: store)
    handler_class = web_server.create_handler(_settings())
    return handler_class, store


def _json_body(handler) -> dict:
    if handler.response_body is not None:
        return json.loads(handler.response_body.decode("utf-8"))
    body = handler.wfile.getvalue()
    return json.loads(body.decode("utf-8"))


def test_session_api_supports_rename_delete_restore(handler_factory) -> None:
    handler_class, store = handler_factory
    session_id = store.create_session("会话一")
    store.add_message(session_id, "user", "hello")

    handler = _make_handler(handler_class, "/api/sessions")
    handler_class.do_GET(handler)
    payload = _json_body(handler)
    assert payload["sessions"][0]["id"] == session_id

    handler = _make_handler(
        handler_class,
        "/api/session",
        body={"sessionId": session_id, "title": "重命名后的会话"},
    )
    handler_class.do_PATCH(handler)
    payload = _json_body(handler)
    assert payload["renamed"] is True

    handler = _make_handler(handler_class, "/api/sessions?q=%E9%87%8D%E5%91%BD%E5%90%8D")
    handler_class.do_GET(handler)
    payload = _json_body(handler)
    assert payload["sessions"][0]["title"] == "重命名后的会话"

    handler = _make_handler(handler_class, "/api/session?sessionId=%s" % session_id)
    handler_class.do_DELETE(handler)
    payload = _json_body(handler)
    assert payload["deleted"] is True

    handler = _make_handler(handler_class, "/api/sessions")
    handler_class.do_GET(handler)
    payload = _json_body(handler)
    assert payload["sessions"] == []

    handler = _make_handler(handler_class, "/api/sessions?deleted=1")
    handler_class.do_GET(handler)
    payload = _json_body(handler)
    assert payload["sessions"][0]["id"] == session_id

    handler = _make_handler(handler_class, "/api/session", body={"sessionId": session_id, "restore": True})
    handler_class.do_PATCH(handler)
    payload = _json_body(handler)
    assert payload["restored"] is True

    handler = _make_handler(handler_class, "/api/sessions")
    handler_class.do_GET(handler)
    payload = _json_body(handler)
    assert payload["sessions"][0]["id"] == session_id
