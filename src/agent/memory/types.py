"""Memory types for the agentic memory system."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import uuid
import json


class MemoryType(Enum):
    """Types of memory."""

    EPISODIC = "episodic"  # Specific interactions/events
    SEMANTIC = "semantic"  # General knowledge about user/project
    PROCEDURAL = "procedural"  # How to perform tasks
    WORKING = "working"  # Current context (short-term)


@dataclass
class Memory:
    """
    A memory unit in the agentic memory system.

    Attributes:
        id: Unique identifier
        type: Memory type (episodic, semantic, procedural, working)
        content: The actual memory content
        importance: Importance score (0.0-1.0)
        access_count: Number of times retrieved
        created_at: When memory was created
        last_accessed: When memory was last retrieved
        metadata: Additional structured data
        embedding: Vector embedding (optional)
        tags: Tags for categorization
    """

    id: str
    type: MemoryType
    content: str
    importance: float = 0.5
    access_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: Optional[list[float]] = None
    tags: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        importance: float = 0.5,
        metadata: Optional[dict] = None,
        tags: Optional[list[str]] = None,
    ) -> "Memory":
        """Create a new memory."""
        return cls(
            id=uuid.uuid4().hex[:12],
            type=memory_type,
            content=content,
            importance=importance,
            metadata=metadata or {},
            tags=tags or [],
        )

    def access(self) -> "Memory":
        """Record memory access."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)
        return self

    def update_importance(self, delta: float) -> "Memory":
        """Update importance score."""
        self.importance = max(0.0, min(1.0, self.importance + delta))
        return self

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "importance": self.importance,
            "access_count": self.access_count,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "metadata": json.dumps(self.metadata),
            "embedding": json.dumps(self.embedding) if self.embedding else None,
            "tags": json.dumps(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Memory":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            type=MemoryType(data["type"]),
            content=data["content"],
            importance=data["importance"],
            access_count=data["access_count"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None,
            metadata=json.loads(data["metadata"]) if data.get("metadata") else {},
            embedding=json.loads(data["embedding"]) if data.get("embedding") else None,
            tags=json.loads(data["tags"]) if data.get("tags") else [],
        )

    @property
    def age_hours(self) -> float:
        """Age of memory in hours."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds() / 3600

    @property
    def recency_score(self) -> float:
        """Calculate recency score (decays over time)."""
        # Half-life of 24 hours
        half_life = 24.0
        return 0.5 ** (self.age_hours / half_life)

    @property
    def relevance_score(self) -> float:
        """Combined relevance score."""
        # Combine importance, recency, and access frequency
        access_factor = min(1.0, self.access_count / 10)
        return (self.importance * 0.4 + self.recency_score * 0.4 + access_factor * 0.2)

    def __repr__(self) -> str:
        return f"Memory({self.id[:6]}, {self.type.value}, importance={self.importance:.2f})"


@dataclass
class MemoryQuery:
    """Query for memory retrieval."""

    text: Optional[str] = None
    memory_type: Optional[MemoryType] = None
    tags: Optional[list[str]] = None
    min_importance: float = 0.0
    limit: int = 10
    include_working: bool = False

    def matches(self, memory: Memory) -> bool:
        """Check if memory matches query criteria."""
        # Type filter
        if self.memory_type and memory.type != self.memory_type:
            return False

        # Working memory filter
        if not self.include_working and memory.type == MemoryType.WORKING:
            return False

        # Importance filter
        if memory.importance < self.min_importance:
            return False

        # Tags filter
        if self.tags and not any(tag in memory.tags for tag in self.tags):
            return False

        return True
