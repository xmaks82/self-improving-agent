"""Memory retriever for semantic search."""

import re
from typing import Optional
from collections import Counter

from .types import Memory, MemoryType, MemoryQuery
from .store import MemoryStore


class MemoryRetriever:
    """
    Retrieves relevant memories based on context.

    Uses keyword matching and relevance scoring.
    Can be extended with embedding-based search.
    """

    def __init__(self, store: MemoryStore):
        self.store = store

    async def retrieve(
        self,
        context: str,
        limit: int = 5,
        memory_types: Optional[list[MemoryType]] = None,
        min_importance: float = 0.0,
    ) -> list[Memory]:
        """
        Retrieve memories relevant to the given context.

        Args:
            context: Current context (user message, task, etc.)
            limit: Maximum memories to return
            memory_types: Filter by memory types
            min_importance: Minimum importance threshold

        Returns:
            List of relevant memories, sorted by relevance
        """
        # Extract keywords from context
        keywords = self._extract_keywords(context)

        if not keywords:
            # Fallback to recent memories
            return await self.store.get_recent(limit=limit)

        # Get candidate memories
        candidates = []

        # Search by each keyword
        for keyword in keywords[:5]:  # Limit keywords to avoid too many queries
            results = await self.store.search_by_content(
                keyword,
                limit=limit * 2,
            )
            candidates.extend(results)

        # Remove duplicates (by ID)
        seen = set()
        unique = []
        for mem in candidates:
            if mem.id not in seen:
                seen.add(mem.id)
                unique.append(mem)
        candidates = unique

        # Filter by type
        if memory_types:
            candidates = [m for m in candidates if m.type in memory_types]

        # Filter by importance
        if min_importance > 0:
            candidates = [m for m in candidates if m.importance >= min_importance]

        # Score and rank
        scored = []
        for memory in candidates:
            score = self._calculate_relevance(memory, context, keywords)
            scored.append((score, memory))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return top results
        return [m for _, m in scored[:limit]]

    async def retrieve_for_conversation(
        self,
        messages: list[dict],
        limit: int = 5,
    ) -> list[Memory]:
        """
        Retrieve memories relevant to a conversation.

        Args:
            messages: Conversation history
            limit: Maximum memories to return

        Returns:
            Relevant memories
        """
        # Combine recent messages for context
        context_parts = []
        for msg in messages[-3:]:  # Last 3 messages
            if isinstance(msg.get("content"), str):
                context_parts.append(msg["content"])

        context = " ".join(context_parts)
        return await self.retrieve(context, limit=limit)

    async def retrieve_by_tags(
        self,
        tags: list[str],
        limit: int = 10,
    ) -> list[Memory]:
        """Retrieve memories by tags."""
        query = MemoryQuery(tags=tags, limit=limit)
        return await self.store.query(query)

    async def get_working_memory(self, limit: int = 10) -> list[Memory]:
        """Get current working memory."""
        return await self.store.get_by_type(MemoryType.WORKING, limit=limit)

    async def get_user_knowledge(self, limit: int = 20) -> list[Memory]:
        """Get semantic memories (knowledge about user/project)."""
        return await self.store.get_by_type(MemoryType.SEMANTIC, limit=limit)

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text."""
        # Simple keyword extraction
        # Remove common words and extract meaningful terms
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into", "through",
            "during", "before", "after", "above", "below", "between",
            "under", "again", "further", "then", "once", "here", "there",
            "when", "where", "why", "how", "all", "each", "few", "more",
            "most", "other", "some", "such", "no", "nor", "not", "only",
            "own", "same", "so", "than", "too", "very", "just", "and",
            "but", "if", "or", "because", "until", "while", "this", "that",
            "these", "those", "it", "its", "i", "me", "my", "you", "your",
            "he", "him", "his", "she", "her", "we", "us", "our", "they",
            "them", "their", "what", "which", "who", "whom",
        }

        # Tokenize and filter
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        keywords = [w for w in words if w not in stopwords]

        # Count frequency
        freq = Counter(keywords)

        # Return most common
        return [word for word, _ in freq.most_common(10)]

    def _calculate_relevance(
        self,
        memory: Memory,
        context: str,
        keywords: list[str],
    ) -> float:
        """Calculate relevance score for a memory."""
        score = 0.0

        # Keyword matching
        content_lower = memory.content.lower()
        keyword_matches = sum(1 for kw in keywords if kw in content_lower)
        keyword_score = keyword_matches / max(len(keywords), 1)
        score += keyword_score * 0.4

        # Importance
        score += memory.importance * 0.3

        # Recency
        score += memory.recency_score * 0.2

        # Access frequency
        access_score = min(1.0, memory.access_count / 10)
        score += access_score * 0.1

        return score
