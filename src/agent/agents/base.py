"""Base agent class with common functionality."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
import uuid

from ..clients import BaseLLMClient
from ..storage.prompts import PromptManager
from ..storage.logs import LogManager


class BaseAgent(ABC):
    """Abstract base class for all agents."""

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
        """Get the current system prompt for this agent."""
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
