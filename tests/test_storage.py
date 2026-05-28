from pathlib import Path
from tempfile import mkdtemp

from langchain_starter.storage import ConversationStore


def test_conversation_store_soft_delete_restore_and_rename() -> None:
    store = ConversationStore(Path(mkdtemp()) / "conversations.sqlite3")
    session_id = store.create_session("初始标题")
    store.add_message(session_id, "user", "你好")

    assert store.rename_session(session_id, "新标题") is True
    assert store.list_sessions()[0]["title"] == "新标题"
    assert store.search_sessions("新标题")[0]["id"] == session_id

    assert store.delete_session(session_id) is True
    assert store.list_sessions() == []
    assert store.list_deleted_sessions()[0]["id"] == session_id
    assert store.search_sessions("新标题") == []
    assert store.search_sessions("新标题", include_deleted=True)[0]["id"] == session_id

    assert store.restore_session(session_id) is True
    assert store.list_sessions()[0]["id"] == session_id

    assert store.purge_session(session_id) is True
    assert store.list_sessions() == []
    assert store.list_deleted_sessions() == []
