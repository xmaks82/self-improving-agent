"""Context compaction - summarizes old conversation history to save tokens."""

import asyncio
import logging

from ..clients.base import BaseLLMClient

logger = logging.getLogger(__name__)

COMPACTION_PROMPT = """Summarize this conversation concisely, preserving:
- Key decisions and conclusions
- Code/file references mentioned
- User preferences and constraints
- Important facts and context
- Current task state

Be brief but complete. Output ONLY the summary, no preamble."""


class ContextCompactor:
    """Compacts conversation history by summarizing older messages."""

    DEFAULT_KEEP_RECENT: int = 6  # Keep last 3 turns (user+assistant pairs)
    MAX_HISTORY_MESSAGES: int = 20  # Trigger at this many messages
    MAX_TOKEN_ESTIMATE: int = 30_000  # Trigger at estimated token count

    def __init__(self, client: BaseLLMClient):
        self.client = client

    def should_compact(
        self,
        history: list[dict],
        keep_recent: int | None = None,
    ) -> bool:
        """Check if compaction is needed."""
        keep = keep_recent or self.DEFAULT_KEEP_RECENT
        if len(history) <= keep:
            return False
        if len(history) >= self.MAX_HISTORY_MESSAGES:
            return True
        if self._estimate_tokens(history) >= self.MAX_TOKEN_ESTIMATE:
            return True
        return False

    def _estimate_tokens(self, history: list[dict]) -> int:
        """Estimate token count (~4 chars per token)."""
        total_chars = sum(len(msg.get("content", "")) for msg in history)
        return total_chars // 4

    async def compact(
        self,
        history: list[dict],
        system_prompt: str,
        keep_recent: int | None = None,
    ) -> list[dict]:
        """
        Compact history: summarize old messages, keep recent ones.

        Returns new history list with summary + recent messages.
        """
        keep = keep_recent or self.DEFAULT_KEEP_RECENT

        if len(history) <= keep:
            return history

        old_messages = history[:-keep]
        recent_messages = history[-keep:]

        # Build conversation text for summarization
        conversation_text = self._format_for_summary(old_messages)

        # Ask LLM to summarize
        try:
            summary_messages = [
                {"role": "user", "content": f"{COMPACTION_PROMPT}\n\n---\n{conversation_text}"}
            ]
            response = await asyncio.to_thread(
                self.client.chat,
                messages=summary_messages,
                system="You are a precise conversation summarizer.",
                max_tokens=1024,
            )
            summary = response.content.strip()
        except Exception as e:
            logger.warning("Compaction failed, keeping history as-is: %s", e)
            return history

        # Build new history: summary context + recent messages
        compacted = [
            {"role": "user", "content": f"[Context Summary of {len(old_messages)} previous messages]:\n{summary}"},
            {"role": "assistant", "content": "Understood. I have the context from our previous conversation."},
        ]
        compacted.extend(recent_messages)

        old_tokens = self._estimate_tokens(history)
        new_tokens = self._estimate_tokens(compacted)
        logger.info(
            "Compacted %d messages -> %d (~%d tokens saved)",
            len(history), len(compacted), old_tokens - new_tokens,
        )

        return compacted

    def _format_for_summary(self, messages: list[dict]) -> str:
        """Format messages as readable conversation text."""
        lines = []
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Assistant"
            content = msg.get("content", "")
            # Truncate very long messages
            if len(content) > 2000:
                content = content[:2000] + "..."
            lines.append(f"{role}: {content}")
        return "\n\n".join(lines)
