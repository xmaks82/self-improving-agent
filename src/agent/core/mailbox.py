"""In-memory mailbox for inter-agent messaging."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class AgentMessage:
    sender: str
    recipient: str
    content: str
    summary: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AgentMailbox:
    """Simple async-safe mailbox for agent-to-agent communication."""

    def __init__(self):
        self._boxes: dict[str, list[AgentMessage]] = {}
        self._lock = asyncio.Lock()

    async def send(self, msg: AgentMessage):
        async with self._lock:
            self._boxes.setdefault(msg.recipient, []).append(msg)

    async def receive(self, agent_name: str) -> list[AgentMessage]:
        async with self._lock:
            return self._boxes.pop(agent_name, [])

    async def peek_count(self, agent_name: str) -> int:
        return len(self._boxes.get(agent_name, []))
