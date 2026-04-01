"""Tracks which files have been read in the current session.

Enforces the read-before-edit/write pattern from Claude Code.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileReadRecord:
    """Record of a file read operation."""
    timestamp: float
    is_partial: bool = False
    offset: int | None = None
    limit: int | None = None


class FileReadStateTracker:
    """
    Tracks which files have been read in the current session.

    Used by WriteFileTool and (future) FileEditTool to enforce
    the read-before-edit pattern.
    """

    def __init__(self):
        self._reads: dict[str, FileReadRecord] = {}
        self._writes: dict[str, float] = {}  # path -> timestamp
        self.edit_count: int = 0  # Total file edits in this session

    def record_read(
        self,
        path: str,
        offset: int | None = None,
        limit: int | None = None,
    ):
        """Record that a file was read."""
        resolved = str(Path(path).resolve())
        self._reads[resolved] = FileReadRecord(
            timestamp=time.time(),
            is_partial=offset is not None or limit is not None,
            offset=offset,
            limit=limit,
        )

    def record_write(self, path: str):
        """Record that a file was written/edited."""
        resolved = str(Path(path).resolve())
        self._writes[resolved] = time.time()
        self.edit_count += 1

    def has_been_read(self, path: str) -> bool:
        """Check if a file has been read in this session."""
        resolved = str(Path(path).resolve())
        return resolved in self._reads

    def was_modified_since_read(self, path: str) -> bool:
        """Check if a file was modified (by us) after its last read."""
        resolved = str(Path(path).resolve())
        read_record = self._reads.get(resolved)
        write_time = self._writes.get(resolved)
        if read_record is None or write_time is None:
            return False
        return write_time > read_record.timestamp

    def clear(self):
        """Clear all tracking state."""
        self._reads.clear()
        self._writes.clear()
        self.edit_count = 0
