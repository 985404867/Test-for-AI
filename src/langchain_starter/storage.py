"""SQLite-backed conversation persistence."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any


class ConversationStore:
    """持久化聊天会话、消息和工具事件。"""

    def __init__(self, db_path: Path = Path("data/conversations.sqlite3")) -> None:
        """初始化 SQLite 存储，并在第一次运行时创建表结构。"""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        """创建一个带 Row 访问方式的 SQLite 连接。"""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        """初始化会话表和消息表，并处理旧数据库的迁移。"""
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '新会话',
                    deleted_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session_id
                    ON messages(session_id, id);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
            }
            if "deleted_at" not in columns:
                connection.execute("ALTER TABLE sessions ADD COLUMN deleted_at TEXT")

    def ensure_session(self, session_id: str, title: str = "新会话") -> None:
        """确保会话存在；常用于首次发消息前自动创建会话记录。"""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(id, title)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = CASE
                        WHEN sessions.title = '新会话' AND excluded.title != '新会话'
                        THEN excluded.title
                        ELSE sessions.title
                    END
                """,
                (session_id, title),
            )

    def create_session(self, title: str = "新会话") -> str:
        """创建一个新的会话 ID，并写入默认标题。"""
        session_id = str(uuid.uuid4())
        self.ensure_session(session_id, title)
        return session_id

    def get_latest_session_id(self) -> str | None:
        """获取最近活跃的未删除会话，用于启动时恢复上下文。"""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM sessions
                WHERE deleted_at IS NULL
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ).fetchone()
        return str(row["id"]) if row else None

    def rename_session(self, session_id: str, title: str) -> bool:
        """重命名会话，通常由历史会话列表中的编辑动作触发。"""
        title = title.strip()
        if not title:
            raise ValueError("标题不能为空。")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE sessions
                SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND deleted_at IS NULL
                """,
                (title, session_id),
            )
        return cursor.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        """软删除会话，移动到回收站，便于后续恢复。"""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE sessions
                SET deleted_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND deleted_at IS NULL
                """,
                (session_id,),
            )
        return cursor.rowcount > 0

    def restore_session(self, session_id: str) -> bool:
        """把回收站中的会话恢复回正常列表。"""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE sessions
                SET deleted_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND deleted_at IS NOT NULL
                """,
                (session_id,),
            )
        return cursor.rowcount > 0

    def purge_session(self, session_id: str) -> bool:
        """永久删除会话及其消息，通常只在回收站中使用。"""
        with self._connect() as connection:
            connection.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cursor = connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return cursor.rowcount > 0

    def touch_session(self, session_id: str) -> None:
        """更新会话的最近活跃时间，便于排序显示。"""
        with self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """写入一条消息记录，供聊天历史和回放使用。"""
        self.ensure_session(session_id)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO messages(session_id, role, content, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (
                    session_id,
                    role,
                    content,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            connection.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """读取指定会话的全部消息。"""
        self.ensure_session(session_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, role, content, metadata, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()

        messages = []
        for row in rows:
            item = dict(row)
            try:
                item["metadata"] = json.loads(item["metadata"])
            except json.JSONDecodeError:
                item["metadata"] = {}
            messages.append(item)
        return messages

    def search_sessions(self, keyword: str, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        """按标题或 ID 搜索会话，支持包含回收站结果。"""
        keyword = keyword.strip()
        if not keyword:
            return self.list_sessions() if not include_deleted else self.list_deleted_sessions()

        like = f"%{keyword}%"
        deleted_clause = "" if include_deleted else "AND deleted_at IS NULL"
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id, title, created_at, updated_at, deleted_at
                FROM sessions
                WHERE (title LIKE ? OR id LIKE ?)
                {deleted_clause}
                ORDER BY updated_at DESC
                """,
                (like, like),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_deleted_sessions(self) -> list[dict[str, Any]]:
        """列出回收站里的会话。"""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, created_at, updated_at, deleted_at
                FROM sessions
                WHERE deleted_at IS NOT NULL
                ORDER BY deleted_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def list_sessions(self) -> list[dict[str, Any]]:
        """列出所有未删除会话，并按最近活跃时间排序。"""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, created_at, updated_at, deleted_at
                FROM sessions
                WHERE deleted_at IS NULL
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]
