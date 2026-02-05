"""Base class for specialized sub-agents."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from ..clients import BaseLLMClient


class SubAgent(ABC):
    """
    Base class for specialized sub-agents.

    Sub-agents are focused on specific tasks and use
    a tailored system prompt for their specialty.
    """

    name: str
    description: str
    system_prompt: str

    def __init__(self, client: BaseLLMClient):
        self.client = client

    @abstractmethod
    async def execute(self, task: str, context: dict[str, Any]) -> str:
        """
        Execute a task.

        Args:
            task: Task description
            context: Additional context

        Returns:
            Result string
        """
        pass

    async def _call_llm(
        self,
        user_message: str,
        context: Optional[dict] = None,
    ) -> str:
        """Call LLM with system prompt."""
        messages = [{"role": "user", "content": user_message}]

        # Build full response from stream
        full_response = ""
        async for chunk in self.client.chat(
            messages=messages,
            system_prompt=self.system_prompt,
        ):
            full_response += chunk

        return full_response

    def _format_context(self, context: dict[str, Any]) -> str:
        """Format context for inclusion in prompt."""
        if not context:
            return ""

        lines = ["Context:"]
        for key, value in context.items():
            if isinstance(value, str) and len(value) > 500:
                value = value[:500] + "..."
            lines.append(f"- {key}: {value}")

        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name})"
