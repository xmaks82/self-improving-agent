"""Tests for MemoryConsolidator."""

import pytest
import tempfile
from pathlib import Path
from src.agent.memory.types import Memory, MemoryType
from src.agent.memory.store import MemoryStore
from src.agent.memory.consolidator import MemoryConsolidator


@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmp:
        yield MemoryStore(db_path=Path(tmp) / "test.db")


@pytest.fixture
def consolidator(temp_store):
    return MemoryConsolidator(store=temp_store)


class TestDecayAndPromotion:
    @pytest.mark.asyncio
    async def test_consolidate_returns_stats(self, consolidator):
        stats = await consolidator.consolidate()
        assert "decayed" in stats
        assert "promoted" in stats
        assert "removed" in stats
        assert "working_cleared" in stats

    @pytest.mark.asyncio
    async def test_promote_to_semantic(self, consolidator, temp_store):
        episodic = Memory.create(content="User said hello", memory_type=MemoryType.EPISODIC)
        await temp_store.store(episodic)
        semantic = await consolidator.promote_to_semantic(episodic, summary="User is friendly")
        assert semantic.type == MemoryType.SEMANTIC
        assert semantic.content == "User is friendly"
        assert "promoted" in semantic.tags

    @pytest.mark.asyncio
    async def test_promote_uses_original_content(self, consolidator, temp_store):
        episodic = Memory.create(content="User said hello", memory_type=MemoryType.EPISODIC)
        await temp_store.store(episodic)
        semantic = await consolidator.promote_to_semantic(episodic)
        assert semantic.content == episodic.content


class TestExtractSemantic:
    @pytest.mark.asyncio
    async def test_extract_semantic_from_pattern(self, consolidator):
        memories = [
            Memory.create(content=f"interaction {i}", tags=["python"]) for i in range(3)
        ]
        result = await consolidator.extract_semantic(memories, threshold=3)
        assert len(result) == 1
        assert result[0].type == MemoryType.SEMANTIC

    @pytest.mark.asyncio
    async def test_no_extraction_below_threshold(self, consolidator):
        memories = [
            Memory.create(content=f"interaction {i}", tags=["python"]) for i in range(2)
        ]
        result = await consolidator.extract_semantic(memories, threshold=3)
        assert len(result) == 0


class TestMergeSimilar:
    @pytest.mark.asyncio
    async def test_merge_memories(self, consolidator, temp_store):
        m1 = Memory.create(content="User likes Python", importance=0.6)
        m2 = Memory.create(content="User codes in Python", importance=0.7)
        await temp_store.store(m1)
        await temp_store.store(m2)
        merged = await consolidator.merge_similar([m1, m2], "User is a Python developer")
        assert merged.content == "User is a Python developer"
        assert "merged" in merged.tags
        assert await temp_store.get(m1.id) is None
        assert await temp_store.get(m2.id) is None

    @pytest.mark.asyncio
    async def test_merge_empty_list_raises(self, consolidator):
        with pytest.raises(ValueError, match="Cannot merge empty"):
            await consolidator.merge_similar([], "merged content")
