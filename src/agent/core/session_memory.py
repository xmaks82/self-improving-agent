"""Session memory auto-update — background markdown notes maintained by subagent."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from ..clients.base import BaseLLMClient
from ..config import config

logger = logging.getLogger(__name__)

UPDATE_PROMPT = """Update the session notes with key information from recent conversation.

Preserve: user goals, files discussed, decisions made, current task state, patterns found.
Keep it under 1500 words. Write the COMPLETE updated markdown content.

Current notes:
{current_memory}

Recent conversation:
{recent_messages}"""


class SessionMemoryManager:
    """Maintains background session notes in markdown."""

    MIN_TOKENS_TO_INIT = 8_000
    MIN_TOKENS_BETWEEN_UPDATES = 5_000
    MIN_TOOL_CALLS_BETWEEN_UPDATES = 3

    def __init__(self, client: BaseLLMClient, session_id: str):
        self.client = client
        self.session_id = session_id
        self._initialized = False
        self._tokens_at_last = 0
        self._tool_calls = 0
        self._lock = asyncio.Lock()

    @property
    def memory_path(self) -> Path:
        d = config.paths.data / "session_memory"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{self.session_id}.md"

    def record_tool_call(self):
        self._tool_calls += 1

    def should_extract(self, estimated_tokens: int) -> bool:
        if not self._initialized:
            if estimated_tokens < self.MIN_TOKENS_TO_INIT:
                return False
            self._initialized = True
        token_growth = estimated_tokens - self._tokens_at_last
        return (token_growth >= self.MIN_TOKENS_BETWEEN_UPDATES
                and self._tool_calls >= self.MIN_TOOL_CALLS_BETWEEN_UPDATES)

    async def extract(self, messages: list[dict]) -> Optional[str]:
        """Extract key notes from conversation (runs in background)."""
        async with self._lock:
            current = self.memory_path.read_text() if self.memory_path.exists() else ""
            recent = "\n\n".join(
                f"{m['role'].title()}: {m.get('content', '')[:800]}"
                for m in messages[-12:]
            )
            try:
                resp = self.client.chat(
                    messages=[{"role": "user", "content": UPDATE_PROMPT.format(
                        current_memory=current or "(empty)", recent_messages=recent)}],
                    system="You are a precise note-taker.",
                    max_tokens=2048,
                )
                updated = resp.content.strip()
                self.memory_path.write_text(updated)
                self._tokens_at_last = sum(len(m.get("content", "")) for m in messages) // 4
                self._tool_calls = 0
                return updated
            except Exception as e:
                logger.warning("Session memory extraction failed: %s", e)
                return None

    def get_content(self) -> str:
        return self.memory_path.read_text() if self.memory_path.exists() else ""
