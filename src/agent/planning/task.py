"""Task dataclass for planning system."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum
import uuid


class TaskStatus(Enum):
    """Task status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class Task:
    """
    Represents a task in the planning system.

    Attributes:
        id: Unique task identifier
        title: Short task description
        status: Current status (pending, in_progress, completed, blocked)
        description: Optional detailed description
        priority: 0=normal, 1=high, 2=urgent
        parent_id: ID of parent task (for subtasks)
        created_at: When task was created
        updated_at: When task was last modified
        completed_at: When task was completed
    """
    id: str
    title: str
    status: TaskStatus = TaskStatus.PENDING
    description: Optional[str] = None
    priority: int = 0
    parent_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        title: str,
        description: Optional[str] = None,
        priority: int = 0,
        parent_id: Optional[str] = None,
    ) -> "Task":
        """Create a new task with generated ID."""
        return cls(
            id=uuid.uuid4().hex[:8],
            title=title,
            description=description,
            priority=priority,
            parent_id=parent_id,
        )

    def complete(self) -> "Task":
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        return self

    def start(self) -> "Task":
        """Mark task as in progress."""
        self.status = TaskStatus.IN_PROGRESS
        self.updated_at = datetime.now(timezone.utc)
        return self

    def block(self) -> "Task":
        """Mark task as blocked."""
        self.status = TaskStatus.BLOCKED
        self.updated_at = datetime.now(timezone.utc)
        return self

    def to_dict(self) -> dict:
        """Convert task to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "description": self.description,
            "priority": self.priority,
            "parent_id": self.parent_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Create task from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            status=TaskStatus(data["status"]),
            description=data.get("description"),
            priority=data.get("priority", 0),
            parent_id=data.get("parent_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )

    @property
    def is_completed(self) -> bool:
        """Check if task is completed."""
        return self.status == TaskStatus.COMPLETED

    @property
    def status_icon(self) -> str:
        """Get status icon for display."""
        icons = {
            TaskStatus.PENDING: "[ ]",
            TaskStatus.IN_PROGRESS: "[~]",
            TaskStatus.COMPLETED: "[x]",
            TaskStatus.BLOCKED: "[!]",
        }
        return icons[self.status]
