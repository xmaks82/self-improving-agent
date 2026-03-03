"""Tests for Memory dataclass and MemoryQuery."""

import pytest
from datetime import datetime
from src.agent.memory.types import Memory, MemoryType, MemoryQuery


@pytest.fixture
def sample_memory():
    return Memory.create(content="User prefers dark mode", memory_type=MemoryType.SEMANTIC)


class TestMemoryCreate:
    def test_create_basic_memory(self):
        memory = Memory.create(content="User prefers dark mode")
        assert memory.content == "User prefers dark mode"
        assert memory.type == MemoryType.EPISODIC
        assert memory.importance == 0.5
        assert len(memory.id) == 12

    def test_create_with_all_fields(self):
        memory = Memory.create(
            content="User prefers dark mode",
            memory_type=MemoryType.SEMANTIC,
            importance=0.8,
            metadata={"source": "chat"},
            tags=["preference", "ui"],
        )
        assert memory.type == MemoryType.SEMANTIC
        assert memory.importance == 0.8
        assert memory.metadata == {"source": "chat"}
        assert "preference" in memory.tags

    def test_create_has_timestamps(self):
        memory = Memory.create(content="test")
        assert isinstance(memory.created_at, datetime)
        assert memory.last_accessed is None


class TestMemoryAccess:
    def test_access_increments_count(self, sample_memory):
        sample_memory.access()
        assert sample_memory.access_count == 1
        assert sample_memory.last_accessed is not None

    def test_multiple_accesses(self, sample_memory):
        sample_memory.access()
        sample_memory.access()
        assert sample_memory.access_count == 2


class TestMemoryImportance:
    def test_update_importance(self, sample_memory):
        sample_memory.update_importance(0.2)
        assert sample_memory.importance == pytest.approx(0.7)

    def test_importance_clamps_to_one(self, sample_memory):
        sample_memory.update_importance(1.0)
        assert sample_memory.importance == 1.0

    def test_importance_clamps_to_zero(self, sample_memory):
        sample_memory.update_importance(-1.0)
        assert sample_memory.importance == 0.0


class TestMemorySerialization:
    def test_to_dict(self, sample_memory):
        d = sample_memory.to_dict()
        assert d["content"] == "User prefers dark mode"
        assert d["type"] == "semantic"
        assert "created_at" in d

    def test_from_dict_roundtrip(self, sample_memory):
        restored = Memory.from_dict(sample_memory.to_dict())
        assert restored.id == sample_memory.id
        assert restored.content == sample_memory.content
        assert restored.type == sample_memory.type
        assert restored.importance == sample_memory.importance

    def test_roundtrip_with_tags_and_metadata(self):
        memory = Memory.create(
            content="test",
            tags=["a", "b"],
            metadata={"key": "value"},
        )
        restored = Memory.from_dict(memory.to_dict())
        assert restored.tags == ["a", "b"]
        assert restored.metadata == {"key": "value"}


class TestMemoryScores:
    def test_recency_score_is_float(self, sample_memory):
        assert isinstance(sample_memory.recency_score, float)
        assert 0.0 <= sample_memory.recency_score <= 1.0

    def test_relevance_score_is_float(self, sample_memory):
        assert isinstance(sample_memory.relevance_score, float)
        assert 0.0 <= sample_memory.relevance_score <= 1.0


class TestMemoryQuery:
    def test_matches_type_filter(self, sample_memory):
        query = MemoryQuery(memory_type=MemoryType.SEMANTIC)
        assert query.matches(sample_memory) is True

    def test_rejects_wrong_type(self, sample_memory):
        query = MemoryQuery(memory_type=MemoryType.EPISODIC)
        assert query.matches(sample_memory) is False

    def test_matches_importance_filter(self, sample_memory):
        query = MemoryQuery(min_importance=0.3)
        assert query.matches(sample_memory) is True

    def test_rejects_low_importance(self, sample_memory):
        query = MemoryQuery(min_importance=0.9)
        assert query.matches(sample_memory) is False

    def test_matches_tags_filter(self):
        memory = Memory.create(content="test", tags=["python", "code"])
        query = MemoryQuery(tags=["python"])
        assert query.matches(memory) is True

    def test_rejects_missing_tags(self):
        memory = Memory.create(content="test", tags=["python"])
        query = MemoryQuery(tags=["javascript"])
        assert query.matches(memory) is False

    def test_excludes_working_memory_by_default(self):
        memory = Memory.create(content="test", memory_type=MemoryType.WORKING)
        query = MemoryQuery()
        assert query.matches(memory) is False

    def test_includes_working_memory_when_requested(self):
        memory = Memory.create(content="test", memory_type=MemoryType.WORKING)
        query = MemoryQuery(include_working=True)
        assert query.matches(memory) is True
