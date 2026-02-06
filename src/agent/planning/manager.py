"""Task manager for persistent task storage."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import json
import aiofiles
import aiofiles.os

from .task import Task, TaskStatus
from ..config import config


class TaskManager:
    """
    Manages task storage and retrieval.

    Uses JSONL format for storage, similar to LogManager pattern.
    Storage path: data/tasks/tasks.jsonl
    """

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or config.paths.data / "tasks"
        self.tasks_file = self.base_path / "tasks.jsonl"
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure storage directories exist."""
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def _load_all(self) -> list[Task]:
        """Load all tasks from storage."""
        if not self.tasks_file.exists():
            return []

        tasks = []
        async with aiofiles.open(self.tasks_file, "r", encoding="utf-8") as f:
            async for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        tasks.append(Task.from_dict(data))
                    except (json.JSONDecodeError, KeyError):
                        continue
        return tasks

    async def _save_all(self, tasks: list[Task]):
        """Save all tasks to storage."""
        async with aiofiles.open(self.tasks_file, "w", encoding="utf-8") as f:
            for task in tasks:
                await f.write(json.dumps(task.to_dict()) + "\n")

    async def create(
        self,
        title: str,
        description: Optional[str] = None,
        priority: int = 0,
        parent_id: Optional[str] = None,
    ) -> Task:
        """
        Create a new task.

        Args:
            title: Task title
            description: Optional detailed description
            priority: 0=normal, 1=high, 2=urgent
            parent_id: ID of parent task for subtasks

        Returns:
            Created Task object
        """
        task = Task.create(
            title=title,
            description=description,
            priority=priority,
            parent_id=parent_id,
        )

        # Append to file
        async with aiofiles.open(self.tasks_file, "a", encoding="utf-8") as f:
            await f.write(json.dumps(task.to_dict()) + "\n")

        return task

    async def get(self, task_id: str) -> Optional[Task]:
        """
        Get task by ID.

        Args:
            task_id: Task ID (full or prefix)

        Returns:
            Task if found, None otherwise
        """
        tasks = await self._load_all()
        for task in tasks:
            if task.id == task_id or task.id.startswith(task_id):
                return task
        return None

    async def update(self, task_id: str, **updates) -> Optional[Task]:
        """
        Update task fields.

        Args:
            task_id: Task ID (full or prefix)
            **updates: Fields to update (title, description, priority, status)

        Returns:
            Updated Task if found, None otherwise
        """
        tasks = await self._load_all()
        updated_task = None

        for i, task in enumerate(tasks):
            if task.id == task_id or task.id.startswith(task_id):
                # Apply updates
                if "title" in updates:
                    task.title = updates["title"]
                if "description" in updates:
                    task.description = updates["description"]
                if "priority" in updates:
                    task.priority = updates["priority"]
                if "status" in updates:
                    if isinstance(updates["status"], TaskStatus):
                        task.status = updates["status"]
                    else:
                        task.status = TaskStatus(updates["status"])

                task.updated_at = datetime.now(timezone.utc)
                tasks[i] = task
                updated_task = task
                break

        if updated_task:
            await self._save_all(tasks)

        return updated_task

    async def complete(self, task_id: str) -> Optional[Task]:
        """
        Mark task as completed.

        Args:
            task_id: Task ID (full or prefix)

        Returns:
            Completed Task if found, None otherwise
        """
        tasks = await self._load_all()
        completed_task = None

        for i, task in enumerate(tasks):
            if task.id == task_id or task.id.startswith(task_id):
                task.complete()
                tasks[i] = task
                completed_task = task
                break

        if completed_task:
            await self._save_all(tasks)

        return completed_task

    async def start(self, task_id: str) -> Optional[Task]:
        """
        Mark task as in progress.

        Args:
            task_id: Task ID (full or prefix)

        Returns:
            Updated Task if found, None otherwise
        """
        tasks = await self._load_all()
        started_task = None

        for i, task in enumerate(tasks):
            if task.id == task_id or task.id.startswith(task_id):
                task.start()
                tasks[i] = task
                started_task = task
                break

        if started_task:
            await self._save_all(tasks)

        return started_task

    async def delete(self, task_id: str) -> bool:
        """
        Delete task.

        Args:
            task_id: Task ID (full or prefix)

        Returns:
            True if deleted, False if not found
        """
        tasks = await self._load_all()
        original_count = len(tasks)

        tasks = [t for t in tasks if not (t.id == task_id or t.id.startswith(task_id))]

        if len(tasks) < original_count:
            await self._save_all(tasks)
            return True

        return False

    async def list(
        self,
        status: Optional[TaskStatus] = None,
        include_completed: bool = True,
        limit: int = 50,
    ) -> list[Task]:
        """
        List tasks.

        Args:
            status: Filter by status (None for all)
            include_completed: Whether to include completed tasks
            limit: Maximum number of tasks to return

        Returns:
            List of tasks sorted by priority (desc) then created_at (asc)
        """
        tasks = await self._load_all()

        # Filter by status
        if status:
            tasks = [t for t in tasks if t.status == status]
        elif not include_completed:
            tasks = [t for t in tasks if t.status != TaskStatus.COMPLETED]

        # Sort: priority desc, then created_at asc
        tasks.sort(key=lambda t: (-t.priority, t.created_at))

        return tasks[:limit]

    async def clear_completed(self) -> int:
        """
        Remove all completed tasks.

        Returns:
            Number of tasks removed
        """
        tasks = await self._load_all()
        original_count = len(tasks)

        tasks = [t for t in tasks if t.status != TaskStatus.COMPLETED]

        await self._save_all(tasks)

        return original_count - len(tasks)

    async def count(self, status: Optional[TaskStatus] = None) -> int:
        """
        Count tasks.

        Args:
            status: Filter by status (None for all)

        Returns:
            Number of tasks
        """
        tasks = await self._load_all()

        if status:
            return sum(1 for t in tasks if t.status == status)

        return len(tasks)
