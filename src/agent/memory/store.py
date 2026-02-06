"""Memory storage backend using SQLite."""

import aiosqlite
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import json

from .types import Memory, MemoryType, MemoryQuery
from ..config import config


class MemoryStore:
    """
    SQLite-based memory storage.

    Stores memories persistently with support for:
    - CRUD operations
    - Filtering by type, tags, importance
    - Retrieval by recency and relevance
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.paths.data / "memory" / "memories.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def initialize(self):
        """Initialize database schema."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL DEFAULT 0.5,
                    access_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT,
                    metadata TEXT,
                    embedding TEXT,
                    tags TEXT
                )
            """)

            # Indexes for common queries
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_type ON memories(type)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_created ON memories(created_at)"
            )

            await db.commit()

        self._initialized = True

    async def store(self, memory: Memory) -> Memory:
        """Store a memory."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            data = memory.to_dict()
            await db.execute(
                """
                INSERT OR REPLACE INTO memories
                (id, type, content, importance, access_count, created_at,
                 last_accessed, metadata, embedding, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["id"],
                    data["type"],
                    data["content"],
                    data["importance"],
                    data["access_count"],
                    data["created_at"],
                    data["last_accessed"],
                    data["metadata"],
                    data["embedding"],
                    data["tags"],
                ),
            )
            await db.commit()

        return memory

    async def get(self, memory_id: str) -> Optional[Memory]:
        """Get memory by ID."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Memory.from_dict(dict(row))
        return None

    async def update(self, memory: Memory) -> Memory:
        """Update existing memory."""
        return await self.store(memory)

    async def delete(self, memory_id: str) -> bool:
        """Delete memory by ID."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM memories WHERE id = ?", (memory_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def query(self, query: MemoryQuery) -> list[Memory]:
        """Query memories based on criteria."""
        await self.initialize()

        sql = "SELECT * FROM memories WHERE 1=1"
        params = []

        # Type filter
        if query.memory_type:
            sql += " AND type = ?"
            params.append(query.memory_type.value)
        elif not query.include_working:
            sql += " AND type != ?"
            params.append(MemoryType.WORKING.value)

        # Importance filter
        if query.min_importance > 0:
            sql += " AND importance >= ?"
            params.append(query.min_importance)

        # Order by relevance (importance + recency)
        sql += " ORDER BY importance DESC, created_at DESC"

        # Limit
        sql += " LIMIT ?"
        params.append(query.limit * 2)  # Get more for post-filtering

        memories = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                async for row in cursor:
                    memory = Memory.from_dict(dict(row))

                    # Post-filter by tags
                    if query.tags:
                        if not any(tag in memory.tags for tag in query.tags):
                            continue

                    memories.append(memory)
                    if len(memories) >= query.limit:
                        break

        return memories

    async def search_by_content(
        self,
        text: str,
        limit: int = 10,
        memory_type: Optional[MemoryType] = None,
    ) -> list[Memory]:
        """
        Search memories by content (simple text search).

        For production, consider using FTS5 or vector search.
        """
        await self.initialize()

        sql = "SELECT * FROM memories WHERE content LIKE ?"
        params = [f"%{text}%"]

        if memory_type:
            sql += " AND type = ?"
            params.append(memory_type.value)

        sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)

        memories = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                async for row in cursor:
                    memories.append(Memory.from_dict(dict(row)))

        return memories

    async def get_recent(
        self,
        limit: int = 10,
        memory_type: Optional[MemoryType] = None,
    ) -> list[Memory]:
        """Get most recent memories."""
        await self.initialize()

        sql = "SELECT * FROM memories"
        params = []

        if memory_type:
            sql += " WHERE type = ?"
            params.append(memory_type.value)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        memories = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                async for row in cursor:
                    memories.append(Memory.from_dict(dict(row)))

        return memories

    async def get_by_type(
        self,
        memory_type: MemoryType,
        limit: int = 50,
    ) -> list[Memory]:
        """Get memories by type."""
        await self.initialize()

        memories = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM memories WHERE type = ? ORDER BY importance DESC LIMIT ?",
                (memory_type.value, limit),
            ) as cursor:
                async for row in cursor:
                    memories.append(Memory.from_dict(dict(row)))

        return memories

    async def count(self, memory_type: Optional[MemoryType] = None) -> int:
        """Count memories."""
        await self.initialize()

        sql = "SELECT COUNT(*) FROM memories"
        params = []

        if memory_type:
            sql += " WHERE type = ?"
            params.append(memory_type.value)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(sql, params) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def clear(self, memory_type: Optional[MemoryType] = None) -> int:
        """Clear memories (all or by type)."""
        await self.initialize()

        sql = "DELETE FROM memories"
        params = []

        if memory_type:
            sql += " WHERE type = ?"
            params.append(memory_type.value)

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(sql, params)
            await db.commit()
            return cursor.rowcount

    async def cleanup_old(self, days: int = 30) -> int:
        """Remove old low-importance memories."""
        await self.initialize()

        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                DELETE FROM memories
                WHERE created_at < ? AND importance < 0.3 AND access_count < 3
                """,
                (cutoff,),
            )
            await db.commit()
            return cursor.rowcount

