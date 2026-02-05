"""Cerebras API client - free tier with 1M tokens/day."""

from typing import AsyncIterator, Optional
import json
import os
import httpx

from .base import BaseLLMClient, LLMResponse, LLMToolResponse, ToolCall, ToolResult
from .exceptions import RateLimitError


class CerebrasClient(BaseLLMClient):
    """
    Client for Cerebras API - OpenAI-compatible interface.

    Free tier: 1M tokens/day (resets daily).
    Speed: 450-1800 tokens/sec (20x faster than GPU).
    Get API key: https://cloud.cerebras.ai/
    """

    provider = "cerebras"
    supports_streaming = True
    supports_tools = True

    API_BASE = "https://api.cerebras.ai/v1"

    # Available models (February 2026)
    MODELS = {
        # Llama 3.1 models
        "llama-3.1-8b": "llama3.1-8b",
        "llama-3.1-70b": "llama3.1-70b",

        # Aliases
        "cerebras": "llama3.1-70b",
        "cerebras-70b": "llama3.1-70b",
        "cerebras-8b": "llama3.1-8b",
    }

    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.1-70b"):
        api_key = api_key or os.getenv("CEREBRAS_API_KEY")
        if not api_key:
            raise ValueError(
                "Cerebras API key required. Set CEREBRAS_API_KEY environment variable.\n"
                "Get free key at: https://cloud.cerebras.ai/"
            )

        self.api_key = api_key
        self.model = self.MODELS.get(model, model)
        self.client = httpx.Client(timeout=120.0)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """Synchronous chat completion."""
        formatted_messages = []

        if system:
            formatted_messages.append({
                "role": "system",
                "content": system,
            })

        formatted_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = self._convert_tools_to_openai(tools)

        try:
            response = self.client.post(
                f"{self.API_BASE}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after = e.response.headers.get("retry-after")
                raise RateLimitError(
                    provider="cerebras",
                    model=self.model,
                    message=str(e),
                    retry_after=float(retry_after) if retry_after else None,
                ) from e
            raise

        data = response.json()

        content = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=self.model,
            stop_reason=data["choices"][0].get("finish_reason"),
        )

    async def stream(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Streaming chat completion."""
        formatted_messages = []

        if system:
            formatted_messages.append({"role": "system", "content": system})

        formatted_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            with self.client.stream(
                "POST",
                f"{self.API_BASE}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            if chunk.get("choices") and chunk["choices"][0].get("delta", {}).get("content"):
                                yield chunk["choices"][0]["delta"]["content"]
                        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                            continue
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after = e.response.headers.get("retry-after")
                raise RateLimitError(
                    provider="cerebras",
                    model=self.model,
                    message=str(e),
                    retry_after=float(retry_after) if retry_after else None,
                ) from e
            raise

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> LLMToolResponse:
        """Chat with tools via Cerebras API."""
        formatted_messages = []

        if system:
            formatted_messages.append({
                "role": "system",
                "content": system,
            })

        formatted_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "max_tokens": max_tokens,
            "tools": self._convert_tools_to_openai(tools),
        }

        try:
            response = self.client.post(
                f"{self.API_BASE}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after = e.response.headers.get("retry-after")
                raise RateLimitError(
                    provider="cerebras",
                    model=self.model,
                    message=str(e),
                    retry_after=float(retry_after) if retry_after else None,
                ) from e
            raise

        data = response.json()

        message = data["choices"][0]["message"]
        content = message.get("content") or ""
        tool_calls = []

        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                try:
                    input_data = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    input_data = {}

                tool_calls.append(ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    input=input_data,
                ))

        usage = data.get("usage", {})

        result = LLMToolResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=self.model,
            stop_reason=data["choices"][0].get("finish_reason"),
        )
        result._raw_response = data
        return result

    def format_tool_results(
        self,
        tool_response: LLMToolResponse,
        tool_results: list[ToolResult],
    ) -> tuple[dict, list[dict]]:
        """Format tool results for OpenAI conversation format."""
        return self._format_openai_tool_results(
            tool_response._raw_response, tool_results, response_is_dict=True
        )

    def get_model_name(self) -> str:
        return self.model

    def set_model(self, model: str):
        self.model = self.MODELS.get(model, model)

    @classmethod
    def list_models(cls) -> list[str]:
        """List available model shortcuts."""
        return ["llama-3.1-8b", "llama-3.1-70b", "cerebras", "cerebras-70b", "cerebras-8b"]
