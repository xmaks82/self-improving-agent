"""Memory consolidation for maintaining memory quality."""

from datetime import datetime, timedelta
from typing import Optional

from .types import Memory, MemoryType
from .store import MemoryStore


class MemoryConsolidator:
    """
    Consolidates and maintains memory quality.

    Performs:
    - Importance decay over time
    - Removal of stale memories
    - Promotion of frequently accessed memories
    - Working memory cleanup
    """

    def __init__(self, store: MemoryStore):
        self.store = store

    async def consolidate(self) -> dict:
        """
        Run full consolidation process.

        Returns:
            Statistics about consolidation
        """
        stats = {
            "decayed": 0,
            "promoted": 0,
            "removed": 0,
            "working_cleared": 0,
        }

        # Decay importance of old, rarely accessed memories
        stats["decayed"] = await self._decay_importance()

        # Promote frequently accessed memories
        stats["promoted"] = await self._promote_frequent()

        # Remove very old, low-value memories
        stats["removed"] = await self._remove_stale()

        # Clear old working memory
        stats["working_cleared"] = await self._clear_old_working()

        return stats

    async def _decay_importance(self) -> int:
        """Decay importance of old memories."""
        count = 0
        cutoff = datetime.utcnow() - timedelta(days=7)

        # Get old memories
        memories = await self.store.get_recent(limit=100)

        for memory in memories:
            if memory.created_at < cutoff:
                # Decay based on age and access
                if memory.access_count < 2:
                    # Unused memories decay faster
                    decay = 0.1
                else:
                    decay = 0.02

                if memory.importance > 0.1:
                    memory.update_importance(-decay)
                    await self.store.update(memory)
                    count += 1

        return count

    async def _promote_frequent(self) -> int:
        """Promote frequently accessed memories."""
        count = 0

        # Get all memories
        memories = await self.store.get_recent(limit=200)

        for memory in memories:
            # Promote if accessed frequently
            if memory.access_count >= 5 and memory.importance < 0.8:
                boost = min(0.1, memory.access_count * 0.01)
                memory.update_importance(boost)
                await self.store.update(memory)
                count += 1

        return count

    async def _remove_stale(self) -> int:
        """Remove stale, low-value memories."""
        return await self.store.cleanup_old(days=30)

    async def _clear_old_working(self) -> int:
        """Clear old working memory entries."""
        # Working memory should be short-lived
        cutoff = datetime.utcnow() - timedelta(hours=24)

        working = await self.store.get_by_type(MemoryType.WORKING, limit=100)
        count = 0

        for memory in working:
            if memory.created_at < cutoff:
                await self.store.delete(memory.id)
                count += 1

        return count

    async def extract_semantic(
        self,
        episodic_memories: list[Memory],
        threshold: int = 3,
    ) -> list[Memory]:
        """
        Extract semantic memories from recurring episodic patterns.

        If similar episodic memories appear multiple times,
        create a semantic memory summarizing the pattern.

        Args:
            episodic_memories: Episodic memories to analyze
            threshold: Minimum occurrences for pattern extraction

        Returns:
            Newly created semantic memories
        """
        # Simple pattern detection based on tags
        tag_counts: dict[str, list[Memory]] = {}

        for mem in episodic_memories:
            for tag in mem.tags:
                if tag not in tag_counts:
                    tag_counts[tag] = []
                tag_counts[tag].append(mem)

        new_semantic = []

        for tag, memories in tag_counts.items():
            if len(memories) >= threshold:
                # Create semantic memory from pattern
                content = f"Pattern: {tag} - appears in {len(memories)} interactions"
                semantic = Memory.create(
                    content=content,
                    memory_type=MemoryType.SEMANTIC,
                    importance=0.6,
                    tags=[tag, "extracted"],
                    metadata={
                        "source_count": len(memories),
                        "source_ids": [m.id for m in memories[:5]],
                    },
                )
                await self.store.store(semantic)
                new_semantic.append(semantic)

        return new_semantic

    async def promote_to_semantic(
        self,
        memory: Memory,
        summary: Optional[str] = None,
    ) -> Memory:
        """
        Promote an episodic memory to semantic.

        Args:
            memory: Memory to promote
            summary: Optional summary for the semantic memory

        Returns:
            New semantic memory
        """
        semantic = Memory.create(
            content=summary or memory.content,
            memory_type=MemoryType.SEMANTIC,
            importance=max(memory.importance, 0.6),
            tags=memory.tags + ["promoted"],
            metadata={
                "source_id": memory.id,
                "source_type": memory.type.value,
            },
        )
        await self.store.store(semantic)
        return semantic

    async def merge_similar(
        self,
        memories: list[Memory],
        merged_content: str,
    ) -> Memory:
        """
        Merge similar memories into one.

        Args:
            memories: Memories to merge
            merged_content: Content for merged memory

        Returns:
            Merged memory
        """
        # Calculate merged importance
        max_importance = max(m.importance for m in memories)
        total_access = sum(m.access_count for m in memories)

        # Collect all tags
        all_tags = set()
        for m in memories:
            all_tags.update(m.tags)

        merged = Memory.create(
            content=merged_content,
            memory_type=memories[0].type,
            importance=min(1.0, max_importance + 0.1),
            tags=list(all_tags) + ["merged"],
            metadata={
                "merged_from": [m.id for m in memories],
                "merge_count": len(memories),
            },
        )
        merged.access_count = total_access

        # Store merged and delete originals
        await self.store.store(merged)
        for m in memories:
            await self.store.delete(m.id)

        return merged
