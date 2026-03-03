"""Tests for TaskManager."""

import pytest
import tempfile
from pathlib import Path
from src.agent.planning.task import TaskStatus
from src.agent.planning.manager import TaskManager


@pytest.fixture
def temp_manager():
    """Create a TaskManager with a temporary directory."""
    with tempfile.TemporaryDirectory() as tmp:
        yield TaskManager(base_path=Path(tmp))


class TestTaskManagerCRUD:
    @pytest.mark.asyncio
    async def test_create_task(self, temp_manager):
        """Test creating a task."""
        task = await temp_manager.create(title="Write docs")
        assert task.title == "Write docs"
        assert task.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_task(self, temp_manager):
        """Test getting a task by ID."""
        created = await temp_manager.create(title="Write docs")
        fetched = await temp_manager.get(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, temp_manager):
        """Test getting a nonexistent task returns None."""
        result = await temp_manager.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_task(self, temp_manager):
        """Test updating a task."""
        created = await temp_manager.create(title="Write docs")
        updated = await temp_manager.update(created.id, title="Write tests")
        assert updated.title == "Write tests"

    @pytest.mark.asyncio
    async def test_delete_task(self, temp_manager):
        """Test deleting a task."""
        created = await temp_manager.create(title="Write docs")
        result = await temp_manager.delete(created.id)
        assert result is True
        assert await temp_manager.get(created.id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_task(self, temp_manager):
        """Test deleting a nonexistent task returns False."""
        result = await temp_manager.delete("nonexistent")
        assert result is False


class TestTaskManagerList:
    @pytest.mark.asyncio
    async def test_list_empty(self, temp_manager):
        """Test listing tasks when empty."""
        tasks = await temp_manager.list()
        assert tasks == []

    @pytest.mark.asyncio
    async def test_list_all_tasks(self, temp_manager):
        """Test listing all tasks."""
        await temp_manager.create(title="Task 1")
        await temp_manager.create(title="Task 2")
        tasks = await temp_manager.list()
        assert len(tasks) == 2

    @pytest.mark.asyncio
    async def test_filter_by_status(self, temp_manager):
        """Test filtering tasks by status."""
        t1 = await temp_manager.create(title="Task 1")
        await temp_manager.create(title="Task 2")
        await temp_manager.complete(t1.id)
        completed = await temp_manager.list(status=TaskStatus.COMPLETED)
        assert len(completed) == 1

    @pytest.mark.asyncio
    async def test_exclude_completed(self, temp_manager):
        """Test excluding completed tasks."""
        t1 = await temp_manager.create(title="Task 1")
        await temp_manager.create(title="Task 2")
        await temp_manager.complete(t1.id)
        tasks = await temp_manager.list(include_completed=False)
        assert len(tasks) == 1


class TestTaskManagerOperations:
    @pytest.mark.asyncio
    async def test_complete_task(self, temp_manager):
        """Test completing a task."""
        created = await temp_manager.create(title="Write docs")
        completed = await temp_manager.complete(created.id)
        assert completed.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_start_task(self, temp_manager):
        """Test starting a task."""
        created = await temp_manager.create(title="Write docs")
        started = await temp_manager.start(created.id)
        assert started.status == TaskStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_clear_completed(self, temp_manager):
        """Test clearing completed tasks."""
        t1 = await temp_manager.create(title="Task 1")
        await temp_manager.create(title="Task 2")
        await temp_manager.complete(t1.id)
        removed = await temp_manager.clear_completed()
        assert removed == 1
        assert await temp_manager.count() == 1

    @pytest.mark.asyncio
    async def test_count_tasks(self, temp_manager):
        """Test counting tasks."""
        await temp_manager.create(title="Task 1")
        await temp_manager.create(title="Task 2")
        assert await temp_manager.count() == 2
