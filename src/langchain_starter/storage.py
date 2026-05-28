"""SQLite-backed conversation persistence."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any


class ConversationStore:
    """Persist chat sessions, messages, and tool events."""

    def __init__(self, db_path: Path = Path("data/conversations.sqlite3")) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '新会话',
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

    def ensure_session(self, session_id: str, title: str = "新会话") -> None:
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
        session_id = str(uuid.uuid4())
        self.ensure_session(session_id, title)
        return session_id

    def get_latest_session_id(self) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ).fetchone()
        return str(row["id"]) if row else None

    def touch_session(self, session_id: str) -> None:
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

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
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
