import sys
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from src.agent.planning.task import Task, TaskStatus


def test_task_creation():
    task = Task.create(title="Test task")

    assert task.title == "Test task"
    assert task.status == TaskStatus.PENDING
    assert not task.is_completed


def test_task_start():
    task = Task.create(title="Test task")
    task.start()

    assert task.status == TaskStatus.IN_PROGRESS


def test_task_complete():
    task = Task.create(title="Test task")
    task.complete()

    assert task.is_completed is True
    assert task.status == TaskStatus.COMPLETED


def test_task_block():
    task = Task.create(title="Test task")
    task.block()

    assert task.status == TaskStatus.BLOCKED


def test_task_serialization():
    task = Task.create(title="Serialize me")
    data = task.to_dict()

    new_task = Task.from_dict(data)

    assert new_task.id == task.id
    assert new_task.title == task.title
    assert new_task.status == task.status
    assert new_task.created_at == task.created_at
