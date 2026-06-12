import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

def _resolve_db_path() -> Path:
    """Pick a DB location that works on whatever machine we're running on.

    Priority:
      1. SANA_DB_PATH env var (explicit override).
      2. The Jetson's always-on SSD, when /mnt/ssd exists.
      3. ~/sana-server/data (the Mac location used so far — keeps existing data).
    """
    env = os.environ.get("SANA_DB_PATH")
    if env:
        return Path(env).expanduser()
    if Path("/mnt/ssd").exists():
        return Path("/mnt/ssd/sana/data/sana.db")
    return Path.home() / "sana-server" / "data" / "sana.db"


DB_PATH = _resolve_db_path()


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

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Delete one conversation (and its messages). Returns False if it
        doesn't exist or doesn't belong to this user."""
        with sqlite3.connect(DB_PATH) as conn:
            owns = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            ).fetchone()
            if not owns:
                return False
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()
        return True

    def delete_all_conversations(self, user_id: str) -> int:
        """Delete all of a user's conversations (and their messages).
        Returns how many conversations were removed."""
        with sqlite3.connect(DB_PATH) as conn:
            ids = [
                r[0]
                for r in conn.execute(
                    "SELECT id FROM conversations WHERE user_id = ?", (user_id,)
                ).fetchall()
            ]
            for cid in ids:
                conn.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
            conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
            conn.commit()
        return len(ids)
