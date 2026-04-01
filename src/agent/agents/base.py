"""Base agent class with common functionality."""

from abc import ABC, abstractmethod
from typing import AsyncIterator
import uuid

from ..clients import BaseLLMClient
from ..storage.prompts import PromptManager
from ..storage.logs import LogManager


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    # If True, use the prompt composer for system prompt generation.
    # Subclasses like AnalyzerAgent/VersionerAgent set this to False
    # to use their own specialized prompts.
    use_composer: bool = True

    def __init__(
        self,
        client: BaseLLMClient,
        prompt_manager: PromptManager,
        log_manager: LogManager,
        agent_name: str,
    ):
        self.client = client
        self.prompt_manager = prompt_manager
        self.log_manager = log_manager
        self.agent_name = agent_name
        self.conversation_history: list[dict] = []
        self.session_id = self._generate_session_id()

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return f"sess_{uuid.uuid4().hex[:12]}"

    def get_system_prompt(self) -> str:
        """
        Get the current system prompt for this agent.

        For the main agent: composes from sections + versioned YAML content.
        For sub-agents (analyzer, versioner): returns the YAML prompt as-is.
        """
        if self.use_composer and self.agent_name == "main_agent":
            from ..prompts.composer import compose_system_prompt
            agent_content = self.prompt_manager.get_current(self.agent_name)
            tool_names = set()
            # Try to get tool names from registry if available
            if hasattr(self, '_get_tool_names'):
                tool_names = self._get_tool_names()
            model = self.client.get_model_name() if self.client else ""
            provider = getattr(self.client, 'provider', "") if self.client else ""
            return compose_system_prompt(
                agent_specific_content=agent_content,
                tool_names=tool_names,
                model=model,
                provider=provider,
            )
        return self.prompt_manager.get_current(self.agent_name)

    def get_prompt_version(self) -> int:
        """Get the current prompt version."""
        return self.prompt_manager.current_version(self.agent_name)

    def reset_conversation(self):
        """Reset conversation history."""
        self.conversation_history = []
        self.session_id = self._generate_session_id()

    @abstractmethod
    async def process(self, message: str) -> AsyncIterator[str]:
        """Process a message and yield response chunks."""
        pass
