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

    def __init__(self, client: BaseLLMClient, tool_registry=None):
        self.client = client
        # When set (and the client supports tools), the sub-agent runs a real
        # tool-loop instead of a single-shot text call.
        self.tool_registry = tool_registry

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
        """Call the LLM. If a tool registry is wired and the client supports
        tools, run a real tool-loop; otherwise a single-shot streamed reply.

        Errors propagate (the orchestrator marks the result failed) — they are
        NOT swallowed into a string that looks like a successful answer."""
        messages = [{"role": "user", "content": user_message}]

        if self.tool_registry is not None and getattr(self.client, "supports_tools", False):
            from ._tool_loop import run_tool_loop
            return await run_tool_loop(
                self.client, self.tool_registry, messages, system=self.system_prompt
            )

        full_response = ""
        async for chunk in self.client.stream(
            messages=messages,
            system=self.system_prompt,
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
