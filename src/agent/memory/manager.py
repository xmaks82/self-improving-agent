"""Memory manager for orchestrating memory operations."""

from pathlib import Path
from typing import Any, Optional

from .types import Memory, MemoryType, MemoryQuery
from .store import MemoryStore
from .retriever import MemoryRetriever
from .consolidator import MemoryConsolidator


class MemoryManager:
    """
    High-level manager for the agentic memory system.

    Provides unified API for:
    - Storing new memories
    - Retrieving relevant memories
    - Managing working memory
    - Running consolidation
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.store = MemoryStore(db_path)
        self.retriever = MemoryRetriever(self.store)
        self.consolidator = MemoryConsolidator(self.store)
        self._initialized = False

    async def initialize(self):
        """Initialize the memory system."""
        if self._initialized:
            return
        await self.store.initialize()
        self._initialized = True

    # ==================== Store Operations ====================

    async def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        importance: float = 0.5,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
    ) -> Memory:
        """
        Store a new memory.

        Args:
            content: Memory content
            memory_type: Type of memory
            importance: Importance score (0-1)
            tags: Tags for categorization
            metadata: Additional data

        Returns:
            Created memory
        """
        await self.initialize()

        memory = Memory.create(
            content=content,
            memory_type=memory_type,
            importance=importance,
            tags=tags,
            metadata=metadata,
        )
        return await self.store.store(memory)

    async def remember_interaction(
        self,
        user_message: str,
        assistant_response: str,
        importance: float = 0.5,
        tags: Optional[list[str]] = None,
    ) -> Memory:
        """
        Store a conversation interaction as episodic memory.

        Args:
            user_message: User's message
            assistant_response: Assistant's response
            importance: Importance score
            tags: Tags for categorization

        Returns:
            Created memory
        """
        content = f"User: {user_message}\nAssistant: {assistant_response}"
        return await self.remember(
            content=content,
            memory_type=MemoryType.EPISODIC,
            importance=importance,
            tags=tags or ["interaction"],
            metadata={
                "user_message": user_message,
                "assistant_response": assistant_response[:500],
            },
        )

    async def learn(
        self,
        fact: str,
        importance: float = 0.6,
        tags: Optional[list[str]] = None,
    ) -> Memory:
        """
        Store a learned fact as semantic memory.

        Args:
            fact: The fact/knowledge to store
            importance: Importance score
            tags: Tags for categorization

        Returns:
            Created memory
        """
        return await self.remember(
            content=fact,
            memory_type=MemoryType.SEMANTIC,
            importance=importance,
            tags=tags or ["learned"],
        )

    async def learn_procedure(
        self,
        name: str,
        steps: list[str],
        importance: float = 0.7,
    ) -> Memory:
        """
        Store a procedure as procedural memory.

        Args:
            name: Procedure name
            steps: List of steps
            importance: Importance score

        Returns:
            Created memory
        """
        content = f"Procedure: {name}\n" + "\n".join(
            f"{i+1}. {step}" for i, step in enumerate(steps)
        )
        return await self.remember(
            content=content,
            memory_type=MemoryType.PROCEDURAL,
            importance=importance,
            tags=["procedure", name.lower().replace(" ", "_")],
            metadata={"name": name, "steps": steps},
        )

    async def set_working(
        self,
        key: str,
        value: Any,
    ) -> Memory:
        """
        Store in working memory (short-term context).

        Args:
            key: Key for the value
            value: Value to store

        Returns:
            Created memory
        """
        content = f"{key}: {value}"
        return await self.remember(
            content=content,
            memory_type=MemoryType.WORKING,
            importance=0.8,
            tags=["working", key],
            metadata={"key": key, "value": str(value)},
        )

    # ==================== Retrieve Operations ====================

    async def recall(
        self,
        context: str,
        limit: int = 5,
        memory_types: Optional[list[MemoryType]] = None,
    ) -> list[Memory]:
        """
        Recall relevant memories based on context.

        Args:
            context: Current context
            limit: Maximum memories to return
            memory_types: Filter by types

        Returns:
            Relevant memories
        """
        await self.initialize()

        memories = await self.retriever.retrieve(
            context=context,
            limit=limit,
            memory_types=memory_types,
        )

        # Record access
        for memory in memories:
            memory.access()
            await self.store.update(memory)

        return memories

    async def recall_for_conversation(
        self,
        messages: list[dict],
        limit: int = 5,
    ) -> list[Memory]:
        """
        Recall memories relevant to conversation.

        Args:
            messages: Conversation history
            limit: Maximum memories

        Returns:
            Relevant memories
        """
        await self.initialize()
        return await self.retriever.retrieve_for_conversation(messages, limit)

    async def get_context(self, limit: int = 10) -> str:
        """
        Get formatted memory context for injection into prompts.

        Args:
            limit: Maximum memories to include

        Returns:
            Formatted context string
        """
        await self.initialize()

        # Get working memory
        working = await self.retriever.get_working_memory(limit=3)

        # Get semantic knowledge
        semantic = await self.retriever.get_user_knowledge(limit=limit - len(working))

        memories = working + semantic

        if not memories:
            return ""

        lines = ["[Memory Context]"]
        for mem in memories:
            type_label = mem.type.value.upper()
            lines.append(f"- [{type_label}] {mem.content[:200]}")

        return "\n".join(lines)

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[Memory]:
        """
        Search memories by content.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            Matching memories
        """
        await self.initialize()
        return await self.store.search_by_content(query, limit)

    # ==================== Management Operations ====================

    async def forget(self, memory_id: str) -> bool:
        """
        Forget (delete) a memory.

        Args:
            memory_id: Memory ID to delete

        Returns:
            True if deleted
        """
        await self.initialize()
        return await self.store.delete(memory_id)

    async def consolidate(self) -> dict:
        """
        Run memory consolidation.

        Returns:
            Consolidation statistics
        """
        await self.initialize()
        return await self.consolidator.consolidate()

    async def clear_working(self) -> int:
        """
        Clear all working memory.

        Returns:
            Number of memories cleared
        """
        await self.initialize()
        return await self.store.clear(MemoryType.WORKING)

    async def get_stats(self) -> dict:
        """
        Get memory statistics.

        Returns:
            Statistics dictionary
        """
        await self.initialize()

        return {
            "total": await self.store.count(),
            "episodic": await self.store.count(MemoryType.EPISODIC),
            "semantic": await self.store.count(MemoryType.SEMANTIC),
            "procedural": await self.store.count(MemoryType.PROCEDURAL),
            "working": await self.store.count(MemoryType.WORKING),
        }

    async def list_memories(
        self,
        memory_type: Optional[MemoryType] = None,
        limit: int = 20,
    ) -> list[Memory]:
        """
        List memories.

        Args:
            memory_type: Filter by type
            limit: Maximum to return

        Returns:
            List of memories
        """
        await self.initialize()

        if memory_type:
            return await self.store.get_by_type(memory_type, limit)
        return await self.store.get_recent(limit)

    def __repr__(self) -> str:
        return f"MemoryManager(initialized={self._initialized})"
