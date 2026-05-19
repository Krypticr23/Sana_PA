import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path("/Users/krishna/sana-server/data/sana.db")


class MemoryManager:
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_facts (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def get_history(self, user_id: str, conversation_id: str = None, limit: int = 20) -> list:
        if not conversation_id:
            return []
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("""
                SELECT role, content FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
            """, (conversation_id, limit)).fetchall()
        return [{"role": r[0], "content": r[1]} for r in rows]

    def save_message(self, user_id: str, conversation_id: str, user_message: str, assistant_message: str) -> str:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO conversations (id, user_id, created_at) VALUES (?, ?, ?)",
                    (conversation_id, user_id, now)
                )
            conn.execute(
                "INSERT INTO messages (id, conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), conversation_id, "user", user_message, now)
            )
            conn.execute(
                "INSERT INTO messages (id, conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), conversation_id, "assistant", assistant_message, now)
            )
            conn.commit()
        return conversation_id

    def get_conversations(self, user_id: str) -> list:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("""
                SELECT c.id, c.created_at, m.content
                FROM conversations c
                JOIN messages m ON m.conversation_id = c.id
                WHERE c.user_id = ? AND m.role = 'user'
                GROUP BY c.id
                ORDER BY c.created_at DESC
                LIMIT 20
            """, (user_id,)).fetchall()
        return [{"id": r[0], "created_at": r[1], "preview": r[2][:60]} for r in rows]
