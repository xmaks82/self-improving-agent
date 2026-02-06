"""Base LLM client abstraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterator, Optional


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


@dataclass
class ToolCall:
    """Unified tool call from LLM response."""
    id: str
    name: str
    input: dict


@dataclass
class ToolResult:
    """Unified tool result to send back to LLM."""
    tool_call_id: str
    content: str


@dataclass
class LLMToolResponse:
    """Response from chat_with_tools() method."""
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    stop_reason: Optional[str] = None
    _raw_response: Any = field(default=None, repr=False)

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0


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
    async def stream(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Streaming chat completion, yields text chunks."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the current model name."""
        pass

    def set_model(self, model: str):
        """Set the model to use."""
        self.model = model

    @abstractmethod
    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> LLMToolResponse:
        """
        Chat completion with tool support.

        Args:
            messages: Conversation history
            tools: Tool definitions in Anthropic format
            system: System prompt
            max_tokens: Maximum response tokens

        Returns:
            LLMToolResponse with unified tool calls
        """
        pass

    @abstractmethod
    def format_tool_results(
        self,
        tool_response: LLMToolResponse,
        tool_results: list[ToolResult],
    ) -> tuple[dict, list[dict]]:
        """
        Format tool results for the conversation.

        Args:
            tool_response: The response containing tool calls
            tool_results: List of tool results

        Returns:
            Tuple of (assistant_message_dict, tool_result_messages)
            For Anthropic: tool_result_messages is a single-element list with tool_result content
            For OpenAI: tool_result_messages is a list of tool role messages
        """
        pass

    # Helper methods for OpenAI-compatible clients

    @staticmethod
    def _convert_tools_to_openai(tools: list[dict]) -> list[dict]:
        """Convert Anthropic tool format to OpenAI format.

        Shared by Groq, OpenRouter, and Zhipu clients.
        """
        converted = []
        for tool in tools:
            converted.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                }
            })
        return converted

    @staticmethod
    def _format_openai_tool_results(
        raw_response: Any,
        tool_results: list[ToolResult],
        response_is_dict: bool = False,
    ) -> tuple[dict, list[dict]]:
        """Format tool results for OpenAI-compatible APIs.

        Shared by Groq, OpenRouter, and Zhipu clients.

        Args:
            raw_response: Raw API response (dict for httpx, object for SDK)
            tool_results: List of tool results
            response_is_dict: True if raw_response is dict (httpx), False if object (SDK)
        """
        if response_is_dict:
            message = raw_response["choices"][0]["message"]
            assistant_msg = {
                "role": "assistant",
                "content": message.get("content"),
                "tool_calls": message.get("tool_calls", []),
            }
        else:
            message = raw_response.choices[0].message
            assistant_msg = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in (message.tool_calls or [])
                ]
            }

        tool_messages = [
            {
                "role": "tool",
                "tool_call_id": r.tool_call_id,
                "content": r.content,
            }
            for r in tool_results
        ]

        return assistant_msg, tool_messages
