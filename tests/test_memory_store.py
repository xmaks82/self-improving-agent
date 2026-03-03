"""Tests for MemoryStore."""

import pytest
import tempfile
from pathlib import Path
from src.agent.memory.types import Memory, MemoryType, MemoryQuery
from src.agent.memory.store import MemoryStore


@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmp:
        yield MemoryStore(db_path=Path(tmp) / "test.db")


@pytest.fixture
def sample_memory():
    return Memory.create(content="User prefers dark mode", memory_type=MemoryType.SEMANTIC)


class TestMemoryStoreCRUD:
    @pytest.mark.asyncio
    async def test_store_and_get(self, temp_store, sample_memory):
        await temp_store.store(sample_memory)
        fetched = await temp_store.get(sample_memory.id)
        assert fetched is not None
        assert fetched.content == sample_memory.content

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, temp_store):
        result = await temp_store.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, temp_store, sample_memory):
        await temp_store.store(sample_memory)
        result = await temp_store.delete(sample_memory.id)
        assert result is True
        assert await temp_store.get(sample_memory.id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, temp_store):
        result = await temp_store.delete("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_update(self, temp_store, sample_memory):
        await temp_store.store(sample_memory)
        sample_memory.importance = 0.9
        await temp_store.update(sample_memory)
        fetched = await temp_store.get(sample_memory.id)
        assert fetched.importance == pytest.approx(0.9)


class TestMemoryStoreQuery:
    @pytest.mark.asyncio
    async def test_query_by_type(self, temp_store):
        await temp_store.store(Memory.create(content="semantic", memory_type=MemoryType.SEMANTIC))
        await temp_store.store(Memory.create(content="episodic", memory_type=MemoryType.EPISODIC))
        results = await temp_store.query(MemoryQuery(memory_type=MemoryType.SEMANTIC))
        assert len(results) == 1
        assert results[0].type == MemoryType.SEMANTIC

    @pytest.mark.asyncio
    async def test_query_by_importance(self, temp_store):
        await temp_store.store(Memory.create(content="high", importance=0.9))
        await temp_store.store(Memory.create(content="low", importance=0.1))
        results = await temp_store.query(MemoryQuery(min_importance=0.5))
        assert all(m.importance >= 0.5 for m in results)

    @pytest.mark.asyncio
    async def test_search_by_content(self, temp_store):
        await temp_store.store(Memory.create(content="User loves Python"))
        await temp_store.store(Memory.create(content="User hates Java"))
        results = await temp_store.search_by_content("Python")
        assert len(results) == 1
        assert "Python" in results[0].content

    @pytest.mark.asyncio
    async def test_get_recent(self, temp_store):
        await temp_store.store(Memory.create(content="first"))
        await temp_store.store(Memory.create(content="second"))
        results = await temp_store.get_recent(limit=2)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_by_type(self, temp_store):
        await temp_store.store(Memory.create(content="s1", memory_type=MemoryType.SEMANTIC))
        await temp_store.store(Memory.create(content="e1", memory_type=MemoryType.EPISODIC))
        results = await temp_store.get_by_type(MemoryType.SEMANTIC)
        assert all(m.type == MemoryType.SEMANTIC for m in results)


class TestMemoryStoreCleanup:
    @pytest.mark.asyncio
    async def test_count(self, temp_store):
        await temp_store.store(Memory.create(content="a"))
        await temp_store.store(Memory.create(content="b"))
        assert await temp_store.count() == 2

    @pytest.mark.asyncio
    async def test_count_by_type(self, temp_store):
        await temp_store.store(Memory.create(content="s", memory_type=MemoryType.SEMANTIC))
        await temp_store.store(Memory.create(content="e", memory_type=MemoryType.EPISODIC))
        assert await temp_store.count(MemoryType.SEMANTIC) == 1

    @pytest.mark.asyncio
    async def test_clear_all(self, temp_store):
        await temp_store.store(Memory.create(content="a"))
        await temp_store.store(Memory.create(content="b"))
        await temp_store.clear()
        assert await temp_store.count() == 0

    @pytest.mark.asyncio
    async def test_clear_by_type(self, temp_store):
        await temp_store.store(Memory.create(content="s", memory_type=MemoryType.SEMANTIC))
        await temp_store.store(Memory.create(content="e", memory_type=MemoryType.EPISODIC))
        await temp_store.clear(MemoryType.SEMANTIC)
        assert await temp_store.count() == 1
