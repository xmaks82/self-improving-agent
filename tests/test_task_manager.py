import sys
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from src.agent.planning.manager import TaskManager
from src.agent.planning.task import TaskStatus


@pytest.mark.asyncio
async def test_create_and_list(tmp_path):
    manager = TaskManager(base_path=tmp_path)

    task = await manager.create("Test task")

    tasks = await manager.list()
    assert len(tasks) == 1
    assert tasks[0].title == "Test task"
    assert tasks[0].id == task.id


@pytest.mark.asyncio
async def test_get_update_and_prefix_lookup(tmp_path):
    manager = TaskManager(base_path=tmp_path)

    task = await manager.create("Original")

    found = await manager.get(task.id)
    assert found is not None
    assert found.title == "Original"

    # Prefix lookup
    prefix = task.id[:4]
    found_prefix = await manager.get(prefix)
    assert found_prefix is not None

    updated = await manager.update(task.id, title="Updated")
    assert updated is not None
    assert updated.title == "Updated"


@pytest.mark.asyncio
async def test_start_complete_clear_and_delete(tmp_path):
    manager = TaskManager(base_path=tmp_path)

    t1 = await manager.create("Task1")
    t2 = await manager.create("Task2")

    await manager.start(t1.id)
    got = await manager.get(t1.id)
    assert got.status == TaskStatus.IN_PROGRESS

    await manager.complete(t1.id)
    got2 = await manager.get(t1.id)
    assert got2.status == TaskStatus.COMPLETED

    removed = await manager.clear_completed()
    assert removed >= 1

    remaining = await manager.list()
    assert all(t.status != TaskStatus.COMPLETED for t in remaining)

    # Delete existing
    deleted = await manager.delete(t2.id)
    assert deleted is True

    # Delete non-existent
    deleted2 = await manager.delete("nope")
    assert deleted2 is False


@pytest.mark.asyncio
async def test_list_filters(tmp_path):
    manager = TaskManager(base_path=tmp_path)

    a = await manager.create("A")
    b = await manager.create("B")

    await manager.complete(a.id)

    all_tasks = await manager.list()
    assert len(all_tasks) == 2

    non_completed = await manager.list(include_completed=False)
    assert all(t.status != TaskStatus.COMPLETED for t in non_completed)

    in_progress = await manager.list(status=TaskStatus.IN_PROGRESS)
    assert isinstance(in_progress, list)
