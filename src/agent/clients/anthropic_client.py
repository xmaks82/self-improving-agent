"""Anthropic Claude client implementation."""

from typing import AsyncIterator, Optional
from anthropic import (
    Anthropic,
    AsyncAnthropic,
    RateLimitError as AnthropicRateLimitError,
)

from .base import BaseLLMClient, LLMResponse, LLMToolResponse, ToolCall, ToolResult
from .exceptions import RateLimitError


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic Claude models."""

    provider = "anthropic"
    supports_streaming = True
    supports_tools = True
    supports_stream_tools = True

    # Available Anthropic models
    MODELS = {
        # Current generation (flagship — Opus 4.8, 2026)
        "claude-opus-4.8": "claude-opus-4-8",
        "claude-opus-4.7": "claude-opus-4-7",
        "claude-opus-4.6": "claude-opus-4-6",
        "claude-sonnet-4.6": "claude-sonnet-4-6",
        "claude-haiku": "claude-haiku-4-5-20251001",
        # Legacy
        "claude-opus-4.5": "claude-opus-4-5-20251101",
        "claude-sonnet-4.5": "claude-sonnet-4-5-20250929",
        "claude-opus": "claude-opus-4-20250514",
        # Full model names
        "claude-opus-4-8": "claude-opus-4-8",
        "claude-opus-4-7": "claude-opus-4-7",
        "claude-opus-4-6": "claude-opus-4-6",
        "claude-sonnet-4-6": "claude-sonnet-4-6",
        "claude-opus-4-5-20251101": "claude-opus-4-5-20251101",
        "claude-sonnet-4-5-20250929": "claude-sonnet-4-5-20250929",
        "claude-opus-4-20250514": "claude-opus-4-20250514",
        "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
    }

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet",
                 auth_token: Optional[str] = None):
        """
        Initialize Anthropic client.

        Auth priority:
        1. Proxy mode (ANTHROPIC_BASE_URL set) — routes through CLIProxyAPI proxy
        2. auth_token (subscription OAuth) — direct to Anthropic
        3. api_key > ANTHROPIC_API_KEY env — standard API billing
        """
        import os

        # Fallback API key for graceful degradation if OAuth fails
        self._fallback_api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._auth_token = auth_token

        # Proxy mode: route through CLIProxyAPI (subscription via OAuth proxy)
        proxy_base_url = os.getenv("ANTHROPIC_BASE_URL")
        proxy_api_key = os.getenv("ANTHROPIC_PROXY_KEY")

        if proxy_base_url:
            client_kwargs = {"base_url": proxy_base_url}
            if proxy_api_key:
                client_kwargs["api_key"] = proxy_api_key
            elif api_key:
                client_kwargs["api_key"] = api_key
            else:
                client_kwargs["api_key"] = os.getenv("ANTHROPIC_API_KEY", "proxy-key")
            self.client = Anthropic(**client_kwargs)
            self.async_client = AsyncAnthropic(**client_kwargs)
            self._auth_mode = "proxy"
        elif auth_token:
            self.client = Anthropic(api_key=None, auth_token=auth_token)
            self.async_client = AsyncAnthropic(api_key=None, auth_token=auth_token)
            self._auth_mode = "subscription"
        elif api_key:
            self.client = Anthropic(api_key=api_key)
            self.async_client = AsyncAnthropic(api_key=api_key)
            self._auth_mode = "api_key"
        else:
            self.client = Anthropic()
            self.async_client = AsyncAnthropic()
            self._auth_mode = "env"
        self.model = self.MODELS.get(model, model)

    def _fallback_to_api_key(self) -> bool:
        """Switch from OAuth to API key if OAuth is blocked/failing."""
        if not self._fallback_api_key:
            return False
        self.client = Anthropic(api_key=self._fallback_api_key)
        self.async_client = AsyncAnthropic(api_key=self._fallback_api_key)
        self._auth_mode = "api_key_fallback"
        # Mark OAuth as blocked in the global manager
        try:
            from ..auth.oauth import get_oauth_manager
            get_oauth_manager()._oauth_blocked = True
        except Exception:
            pass
        import logging
        logging.getLogger(__name__).warning(
            "OAuth blocked — switched to API key billing"
        )
        return True

    def _should_fallback(self, error: Exception) -> bool:
        """Check if error warrants OAuth → API key fallback."""
        if self._auth_mode != "subscription":
            return False
        status = getattr(getattr(error, 'response', None), 'status_code', 0)
        if status in (401, 403):
            return self._fallback_to_api_key()
        # Check for auth-related error messages
        msg = str(error).lower()
        if any(w in msg for w in ("unauthorized", "forbidden", "token", "revoked", "blocked")):
            return self._fallback_to_api_key()
        return False

    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """Synchronous chat completion with OAuth fallback."""
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
        except Exception as e:
            if self._should_fallback(e):
                return self.chat(messages, system, max_tokens, tools)
            raise

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

    async def stream(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Streaming chat completion."""
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        if system:
            kwargs["system"] = system

        try:
            async with self.async_client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
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
        except Exception as e:
            # OAuth blocked/expired → transparently fall back to API key and retry.
            if self._should_fallback(e):
                return self.chat_with_tools(messages, tools, system, max_tokens)
            raise

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

    async def stream_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ):
        """Token-stream text deltas, then yield the final LLMToolResponse."""
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "tools": tools,
        }
        if system:
            kwargs["system"] = system

        async with self.async_client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()

        content = ""
        tool_calls = []
        for block in final.content:
            if hasattr(block, "text"):
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))

        resp = LLMToolResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
            model=self.model,
            stop_reason=final.stop_reason,
        )
        resp._raw_response = final
        yield resp

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
        return ["claude-opus-4.6", "claude-sonnet-4.6", "claude-haiku", "claude-opus-4.5", "claude-sonnet-4.5"]
