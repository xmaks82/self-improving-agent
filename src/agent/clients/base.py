"""Base LLM client abstraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Iterator, Optional


@dataclass
class LLMResponse:
    """Unified response from LLM."""
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    stop_reason: Optional[str] = None


@dataclass
class ToolDefinition:
    """Tool definition for function calling."""
    name: str
    description: str
    input_schema: dict


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    provider: str = "base"
    supports_streaming: bool = True
    supports_tools: bool = True

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """Synchronous chat completion."""
        pass

    @abstractmethod
    def stream(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        """Streaming chat completion, yields text chunks."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the current model name."""
        pass

    def set_model(self, model: str):
        """Set the model to use."""
        self.model = model
