"""Tests for Task dataclass."""

import pytest
from datetime import datetime
from src.agent.planning.task import Task, TaskStatus


class TestTaskCreate:
    def test_create_basic_task(self):
        """Test creating a task with just a title."""
        task = Task.create(title="Write docs")
        assert task.title == "Write docs"
        assert task.status == TaskStatus.PENDING
        assert task.priority == 0
        assert task.description is None
        assert task.parent_id is None
        assert len(task.id) == 8

    def test_create_task_with_all_fields(self):
        """Test creating a task with all fields."""
        task = Task.create(
            title="Write docs",
            description="Detailed description",
            priority=2,
            parent_id="abc12345",
        )
        assert task.title == "Write docs"
        assert task.description == "Detailed description"
        assert task.priority == 2
        assert task.parent_id == "abc12345"

    def test_create_task_has_timestamps(self):
        """Test that created task has timestamps."""
        task = Task.create(title="Write docs")
        assert isinstance(task.created_at, datetime)
        assert isinstance(task.updated_at, datetime)
        assert task.completed_at is None


class TestTaskStatus:
    def test_complete_task(self):
        """Test completing a task."""
        task = Task.create(title="Write docs")
        task.complete()
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        assert task.is_completed is True

    def test_start_task(self):
        """Test starting a task."""
        task = Task.create(title="Write docs")
        task.start()
        assert task.status == TaskStatus.IN_PROGRESS

    def test_block_task(self):
        """Test blocking a task."""
        task = Task.create(title="Write docs")
        task.block()
        assert task.status == TaskStatus.BLOCKED

    def test_status_icons(self):
        """Test status icons."""
        task = Task.create(title="Write docs")
        assert task.status_icon == "[ ]"
        task.start()
        assert task.status_icon == "[~]"
        task.complete()
        assert task.status_icon == "[x]"
        task.block()
        assert task.status_icon == "[!]"


class TestTaskSerialization:
    def test_to_dict(self):
        """Test converting task to dictionary."""
        task = Task.create(title="Write docs", priority=1)
        d = task.to_dict()
        assert d["title"] == "Write docs"
        assert d["priority"] == 1
        assert d["status"] == "pending"
        assert "created_at" in d
        assert "updated_at" in d
        assert d["completed_at"] is None

    def test_from_dict(self):
        """Test creating task from dictionary."""
        task = Task.create(title="Write docs")
        d = task.to_dict()
        restored = Task.from_dict(d)
        assert restored.id == task.id
        assert restored.title == task.title
        assert restored.status == task.status
        assert restored.priority == task.priority

    def test_roundtrip_serialization(self):
        """Test that task survives to_dict -> from_dict roundtrip."""
        task = Task.create(title="Write docs", description="Details", priority=2)
        task.complete()
        restored = Task.from_dict(task.to_dict())
        assert restored.id == task.id
        assert restored.status == TaskStatus.COMPLETED
        assert restored.completed_at is not None
