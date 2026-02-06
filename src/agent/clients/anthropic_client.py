"""Anthropic Claude client implementation."""

from typing import Iterator, Optional
from anthropic import Anthropic, RateLimitError as AnthropicRateLimitError

from .base import BaseLLMClient, LLMResponse, LLMToolResponse, ToolCall, ToolResult
from .exceptions import RateLimitError


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic Claude models."""

    provider = "anthropic"
    supports_streaming = True
    supports_tools = True

    # Available Anthropic models
    MODELS = {
        # Shortcuts
        "claude-opus-4.6": "claude-opus-4-6",            # Flagship (Feb 2026)
        "claude-opus-4.5": "claude-opus-4-5-20251101",   # Legacy
        "claude-sonnet": "claude-sonnet-4-5-20250929",
        "claude-opus": "claude-opus-4-20250514",
        "claude-haiku": "claude-haiku-4-5-20251001",
        # Full model names
        "claude-opus-4-6": "claude-opus-4-6",
        "claude-opus-4-5-20251101": "claude-opus-4-5-20251101",
        "claude-sonnet-4-5-20250929": "claude-sonnet-4-5-20250929",
        "claude-opus-4-20250514": "claude-opus-4-20250514",
        "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
    }

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet"):
        self.client = Anthropic(api_key=api_key) if api_key else Anthropic()
        self.model = self.MODELS.get(model, model)

    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """Synchronous chat completion."""
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        if system:
            kwargs["system"] = system

        if tools:
            kwargs["tools"] = tools

        try:
            response = self.client.messages.create(**kwargs)
        except AnthropicRateLimitError as e:
            raise RateLimitError(
                provider="anthropic",
                model=self.model,
                message=str(e),
            ) from e

        # Extract text content
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        return LLMResponse(
            content=content,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self.model,
            stop_reason=response.stop_reason,
        )

    def stream(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        """Streaming chat completion."""
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        if system:
            kwargs["system"] = system

        try:
            with self.client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield text
        except AnthropicRateLimitError as e:
            raise RateLimitError(
                provider="anthropic",
                model=self.model,
                message=str(e),
            ) from e

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> LLMToolResponse:
        """Chat with tools using native Anthropic format."""
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "tools": tools,
        }

        if system:
            kwargs["system"] = system

        try:
            response = self.client.messages.create(**kwargs)
        except AnthropicRateLimitError as e:
            raise RateLimitError(
                provider="anthropic",
                model=self.model,
                message=str(e),
            ) from e

        # Extract text and tool calls
        content = ""
        tool_calls = []

        for block in response.content:
            if hasattr(block, "text"):
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    input=block.input,
                ))

        result = LLMToolResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self.model,
            stop_reason=response.stop_reason,
        )
        result._raw_response = response
        return result

    def format_tool_results(
        self,
        tool_response: LLMToolResponse,
        tool_results: list[ToolResult],
    ) -> tuple[dict, list[dict]]:
        """Format tool results for Anthropic conversation format."""
        # Anthropic wants the raw content blocks as assistant message
        assistant_msg = {
            "role": "assistant",
            "content": tool_response._raw_response.content,
        }

        # Tool results as user message with tool_result content blocks
        user_msg = {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": r.tool_call_id,
                    "content": r.content,
                }
                for r in tool_results
            ]
        }

        return assistant_msg, [user_msg]

    def get_model_name(self) -> str:
        return self.model

    def set_model(self, model: str):
        self.model = self.MODELS.get(model, model)

    @classmethod
    def list_models(cls) -> list[str]:
        """List available model shortcuts."""
        return ["claude-opus-4.6", "claude-opus-4.5", "claude-sonnet", "claude-haiku"]
