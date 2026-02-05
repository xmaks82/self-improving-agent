"""Undo system for reverting changes."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import json
import aiofiles

from ..config import config


@dataclass
class Change:
    """A recorded change that can be undone."""

    id: str
    change_type: str  # file_write, file_delete, file_create
    target: str
    timestamp: datetime
    before: Optional[str] = None  # Content before change
    after: Optional[str] = None  # Content after change
    metadata: dict[str, Any] = field(default_factory=dict)
    undone: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "change_type": self.change_type,
            "target": self.target,
            "timestamp": self.timestamp.isoformat(),
            "before": self.before,
            "after": self.after,
            "metadata": self.metadata,
            "undone": self.undone,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Change":
        return cls(
            id=data["id"],
            change_type=data["change_type"],
            target=data["target"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            before=data.get("before"),
            after=data.get("after"),
            metadata=data.get("metadata", {}),
            undone=data.get("undone", False),
        )


class UndoManager:
    """
    Manages undo history for file changes.

    Features:
    - Records file changes with before/after state
    - Supports undo and redo
    - Persists history to disk
    - Automatic cleanup of old entries
    """

    def __init__(
        self,
        history_path: Optional[Path] = None,
        max_history: int = 100,
    ):
        self.history_path = history_path or config.paths.data / "undo" / "history.json"
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_history = max_history
        self._changes: list[Change] = []
        self._redo_stack: list[Change] = []
        self._counter = 0

    async def load(self):
        """Load history from disk."""
        if not self.history_path.exists():
            return

        try:
            async with aiofiles.open(self.history_path, "r") as f:
                data = json.loads(await f.read())
                self._changes = [Change.from_dict(c) for c in data.get("changes", [])]
                self._counter = data.get("counter", 0)
        except (json.JSONDecodeError, KeyError):
            self._changes = []

    async def save(self):
        """Save history to disk."""
        data = {
            "changes": [c.to_dict() for c in self._changes[-self.max_history:]],
            "counter": self._counter,
        }
        async with aiofiles.open(self.history_path, "w") as f:
            await f.write(json.dumps(data, indent=2))

    def _generate_id(self) -> str:
        """Generate unique change ID."""
        self._counter += 1
        return f"chg_{self._counter:06d}"

    async def record_file_write(
        self,
        path: str,
        before: Optional[str],
        after: str,
        metadata: Optional[dict] = None,
    ) -> Change:
        """
        Record a file write operation.

        Args:
            path: File path
            before: Content before (None if new file)
            after: Content after
            metadata: Additional metadata

        Returns:
            Recorded change
        """
        change_type = "file_create" if before is None else "file_write"

        change = Change(
            id=self._generate_id(),
            change_type=change_type,
            target=path,
            timestamp=datetime.utcnow(),
            before=before,
            after=after,
            metadata=metadata or {},
        )

        self._changes.append(change)
        self._redo_stack.clear()  # Clear redo on new change
        await self.save()

        return change

    async def record_file_delete(
        self,
        path: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Change:
        """Record a file delete operation."""
        change = Change(
            id=self._generate_id(),
            change_type="file_delete",
            target=path,
            timestamp=datetime.utcnow(),
            before=content,
            after=None,
            metadata=metadata or {},
        )

        self._changes.append(change)
        self._redo_stack.clear()
        await self.save()

        return change

    async def undo(self) -> Optional[Change]:
        """
        Undo the last change.

        Returns:
            The undone change, or None if nothing to undo
        """
        # Find last non-undone change
        for change in reversed(self._changes):
            if not change.undone:
                return await self._apply_undo(change)

        return None

    async def _apply_undo(self, change: Change) -> Change:
        """Apply undo for a specific change."""
        path = Path(change.target)

        if change.change_type == "file_create":
            # Undo create = delete
            if path.exists():
                path.unlink()

        elif change.change_type == "file_delete":
            # Undo delete = restore
            if change.before is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(path, "w") as f:
                    await f.write(change.before)

        elif change.change_type == "file_write":
            # Undo write = restore previous content
            if change.before is not None:
                async with aiofiles.open(path, "w") as f:
                    await f.write(change.before)

        change.undone = True
        self._redo_stack.append(change)
        await self.save()

        return change

    async def redo(self) -> Optional[Change]:
        """
        Redo the last undone change.

        Returns:
            The redone change, or None if nothing to redo
        """
        if not self._redo_stack:
            return None

        change = self._redo_stack.pop()
        return await self._apply_redo(change)

    async def _apply_redo(self, change: Change) -> Change:
        """Apply redo for a specific change."""
        path = Path(change.target)

        if change.change_type == "file_create":
            # Redo create = create again
            if change.after is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(path, "w") as f:
                    await f.write(change.after)

        elif change.change_type == "file_delete":
            # Redo delete = delete again
            if path.exists():
                path.unlink()

        elif change.change_type == "file_write":
            # Redo write = apply new content
            if change.after is not None:
                async with aiofiles.open(path, "w") as f:
                    await f.write(change.after)

        change.undone = False
        await self.save()

        return change

    def get_history(self, limit: int = 20) -> list[Change]:
        """Get recent change history."""
        return list(reversed(self._changes[-limit:]))

    def get_undoable(self) -> list[Change]:
        """Get changes that can be undone."""
        return [c for c in self._changes if not c.undone]

    def get_redoable(self) -> list[Change]:
        """Get changes that can be redone."""
        return self._redo_stack.copy()

    @property
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return any(not c.undone for c in self._changes)

    @property
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self._redo_stack) > 0

    async def clear(self):
        """Clear all history."""
        self._changes.clear()
        self._redo_stack.clear()
        await self.save()
