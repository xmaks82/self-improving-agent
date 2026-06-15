"""Session persistence with SQLite storage."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import aiosqlite

from ..config import config

logger = logging.getLogger(__name__)


@dataclass
class SessionRecord:
    """A saved session."""
    session_id: str
    model: str
    provider: str
    prompt_version: int
    conversation_history: list[dict]
    created_at: str
    updated_at: str
    turn_count: int
    summary: str  # First user message or auto label


class SessionStore:
    """SQLite-backed session persistence."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.paths.data / "sessions" / "sessions.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def initialize(self):
        """Create tables if needed."""
        if self._initialized:
            return
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    prompt_version INTEGER NOT NULL,
                    conversation_history TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    turn_count INTEGER NOT NULL,
                    summary TEXT NOT NULL
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC)"
            )
            await db.commit()
        self._initialized = True

    async def save(self, record: SessionRecord):
        """Save or update a session."""
        await self.initialize()
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """INSERT OR REPLACE INTO sessions
                   (session_id, model, provider, prompt_version,
                    conversation_history, created_at, updated_at,
                    turn_count, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.session_id,
                    record.model,
                    record.provider,
                    record.prompt_version,
                    json.dumps(record.conversation_history, ensure_ascii=False),
                    record.created_at,
                    record.updated_at,
                    record.turn_count,
                    record.summary,
                ),
            )
            await db.commit()

    async def load(self, session_id: str) -> Optional[SessionRecord]:
        """Load a session by ID (supports partial ID match)."""
        await self.initialize()
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            # Try exact match first, then prefix match
            cursor = await db.execute(
                "SELECT * FROM sessions WHERE session_id = ? OR session_id LIKE ?",
                (session_id, f"{session_id}%"),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return SessionRecord(
                session_id=row["session_id"],
                model=row["model"],
                provider=row["provider"],
                prompt_version=row["prompt_version"],
                conversation_history=json.loads(row["conversation_history"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                turn_count=row["turn_count"],
                summary=row["summary"],
            )

    async def list_sessions(self, limit: int = 20) -> list[SessionRecord]:
        """List recent sessions."""
        await self.initialize()
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [
                SessionRecord(
                    session_id=row["session_id"],
                    model=row["model"],
                    provider=row["provider"],
                    prompt_version=row["prompt_version"],
                    conversation_history=json.loads(row["conversation_history"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    turn_count=row["turn_count"],
                    summary=row["summary"],
                )
                for row in rows
            ]

    async def delete(self, session_id: str) -> bool:
        """Delete a session."""
        await self.initialize()
        async with aiosqlite.connect(str(self.db_path)) as db:
            cursor = await db.execute(
                "DELETE FROM sessions WHERE session_id = ? OR session_id LIKE ?",
                (session_id, f"{session_id}%"),
            )
            await db.commit()
            return cursor.rowcount > 0
