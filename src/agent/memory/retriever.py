"""Memory retriever: hybrid (vector + keyword) semantic search.

Combines embedding-based vector search with keyword matching, fused via
Reciprocal Rank Fusion (RRF). Vector search is optional and best-effort — if no
embeddings backend is configured/reachable, retrieval falls back to pure keyword
ranking, so the agent works out of the box without an embeddings server.
"""

import re
from typing import Optional
from collections import Counter

from .types import Memory, MemoryType, MemoryQuery
from .store import MemoryStore
from .embeddings import EmbeddingsClient, cosine_similarity

RRF_K = 60


class MemoryRetriever:
    """
    Retrieves relevant memories based on context.

    Hybrid: vector similarity (if an embeddings backend is available) + keyword
    matching, fused with RRF. Graceful fallback to keyword-only.
    """

    def __init__(self, store: MemoryStore, embeddings: Optional[EmbeddingsClient] = None):
        self.store = store
        self.embeddings = embeddings or EmbeddingsClient()

    async def retrieve(
        self,
        context: str,
        limit: int = 5,
        memory_types: Optional[list[MemoryType]] = None,
        min_importance: float = 0.0,
    ) -> list[Memory]:
        """
        Retrieve memories relevant to the given context.

        Runs keyword and (when available) vector ranking, fuses them via RRF.
        Falls back to keyword-only, then to recent memories.
        """
        kw_ranked = await self._keyword_candidates(
            context, limit, memory_types, min_importance
        )
        vec_ranked = await self._vector_candidates(
            context, limit, memory_types, min_importance
        )

        if not vec_ranked:
            # No embeddings backend (or empty) → keyword-only path.
            if kw_ranked:
                return kw_ranked[:limit]
            return await self.store.get_recent(limit=limit)

        fused = self._rrf([vec_ranked, kw_ranked])
        return fused[:limit]

    async def _keyword_candidates(
        self,
        context: str,
        limit: int,
        memory_types: Optional[list[MemoryType]],
        min_importance: float,
    ) -> list[Memory]:
        """Keyword-matched, relevance-scored candidates (original logic)."""
        keywords = self._extract_keywords(context)
        if not keywords:
            return []

        candidates: list[Memory] = []
        for keyword in keywords[:5]:
            candidates.extend(
                await self.store.search_by_content(keyword, limit=limit * 2)
            )

        seen, unique = set(), []
        for mem in candidates:
            if mem.id not in seen:
                seen.add(mem.id)
                unique.append(mem)
        candidates = unique

        if memory_types:
            candidates = [m for m in candidates if m.type in memory_types]
        if min_importance > 0:
            candidates = [m for m in candidates if m.importance >= min_importance]

        scored = [
            (self._calculate_relevance(m, context, keywords), m) for m in candidates
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored]

    async def _vector_candidates(
        self,
        context: str,
        limit: int,
        memory_types: Optional[list[MemoryType]],
        min_importance: float,
    ) -> list[Memory]:
        """Embedding cosine-ranked candidates. Empty if no embeddings backend."""
        if not self.embeddings.available:
            return []
        qvec = await self.embeddings.embed(context)
        if not qvec:
            return []
        pool = await self.store.get_embedded(memory_types=memory_types)
        if min_importance > 0:
            pool = [m for m in pool if m.importance >= min_importance]
        scored = [
            (cosine_similarity(qvec, m.embedding), m)
            for m in pool
            if m.embedding
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[: limit * 4]]

    @staticmethod
    def _rrf(ranked_lists: list[list[Memory]], k: int = RRF_K) -> list[Memory]:
        """Reciprocal Rank Fusion over several ranked Memory lists (by id)."""
        scores: dict[str, float] = {}
        objs: dict[str, Memory] = {}
        for lst in ranked_lists:
            for rank, mem in enumerate(lst, 1):
                scores[mem.id] = scores.get(mem.id, 0.0) + 1.0 / (k + rank)
                objs[mem.id] = mem
        return [objs[i] for i in sorted(scores, key=lambda x: scores[x], reverse=True)]

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

        # Tokenize and filter. [^\W\d_] = any-script letters (Latin + Cyrillic + …),
        # excluding digits/underscore — the old [a-zA-Z] regex dropped all Russian.
        words = re.findall(r'[^\W\d_]{3,}', text.lower(), re.UNICODE)
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
