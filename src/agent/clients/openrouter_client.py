"""OpenRouter API client — access to 200+ models including free ones.

OpenRouter uses OpenAI-compatible API format.
Free models end with :free suffix.
Get API key: https://openrouter.ai/keys (no credit card required)
"""

from typing import AsyncIterator, Optional
import json
import os

import httpx

from .base import BaseLLMClient, LLMResponse, LLMToolResponse, ToolCall, ToolResult
from .exceptions import RateLimitError

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterClient(BaseLLMClient):
    """
    Client for OpenRouter API — router to 200+ LLM models.

    Free models (no cost, rate-limited):
    - qwen/qwen3.6-plus-preview:free  — 1M context, tool use, reasoning
    - openrouter/free                  — auto-selects best free model

    Get free key: https://openrouter.ai/keys
    """

    provider = "openrouter"
    supports_streaming = True
    supports_tools = True
    supports_stream_tools = True
    BASE_URL = OPENROUTER_BASE_URL  # overridable by subclasses (e.g. FCMClient)

    # Curated models (free and paid)
    MODELS = {
        # Free models (актуально на 2026-06, сверено с live /models OpenRouter).
        # qwen3.6-plus-preview снят — заменён на qwen3-next (general, длинный контекст).
        "qwen3-next": "qwen/qwen3-next-80b-a3b-instruct:free",
        "qwen3-coder": "qwen/qwen3-coder:free",
        "kimi-k2.6": "moonshotai/kimi-k2.6:free",
        "glm-4.5-air-free": "z-ai/glm-4.5-air:free",
        "openrouter-free": "openrouter/free",
        # alias на прежнее имя, чтобы старые конфиги не падали
        "qwen3.6-plus": "qwen/qwen3-next-80b-a3b-instruct:free",
    }

    def __init__(self, api_key: Optional[str] = None, model: str = "qwen3.6-plus"):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key required. Set OPENROUTER_API_KEY.\n"
                "Get free key at: https://openrouter.ai/keys"
            )
        self.model = self.MODELS.get(model, model)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/xmaks82/self-improving-agent",
            "X-Title": "Self-Improving Agent",
        }

    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """Synchronous chat completion."""
        formatted = []
        if system:
            formatted.append({"role": "system", "content": system})
        formatted.extend(messages)

        body: dict = {
            "model": self.model,
            "messages": formatted,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = self._convert_tools_to_openai(tools)

        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers=self._headers(),
                    json=body,
                )
                if resp.status_code == 429:
                    raise RateLimitError(
                        provider="openrouter", model=self.model,
                        message="Rate limit exceeded",
                    )
                resp.raise_for_status()
                data = resp.json()
        except RateLimitError:
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError(
                    provider="openrouter", model=self.model,
                    message="Rate limit exceeded",
                ) from e
            raise

        choice = data["choices"][0]
        content = choice["message"].get("content") or ""
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=self.model,
            stop_reason=choice.get("finish_reason"),
        )

    async def stream(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Streaming chat completion."""
        formatted = []
        if system:
            formatted.append({"role": "system", "content": system})
        formatted.extend(messages)

        body = {
            "model": self.model,
            "messages": formatted,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.BASE_URL}/chat/completions",
                headers=self._headers(),
                json=body,
            ) as resp:
                if resp.status_code == 429:
                    raise RateLimitError(
                        provider="openrouter", model=self.model,
                        message="Rate limit exceeded",
                    )
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0].get("delta", {})
                        text = delta.get("content")
                        if text:
                            yield text
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> LLMToolResponse:
        """Chat with tool support (OpenAI format)."""
        formatted = []
        if system:
            formatted.append({"role": "system", "content": system})
        formatted.extend(messages)

        body = {
            "model": self.model,
            "messages": formatted,
            "max_tokens": max_tokens,
            "tools": self._convert_tools_to_openai(tools),
        }

        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers=self._headers(),
                    json=body,
                )
                if resp.status_code == 429:
                    raise RateLimitError(
                        provider="openrouter", model=self.model,
                        message="Rate limit exceeded",
                    )
                resp.raise_for_status()
                data = resp.json()
        except RateLimitError:
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError(
                    provider="openrouter", model=self.model,
                    message="Rate limit exceeded",
                ) from e
            raise

        choice = data["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""
        usage = data.get("usage", {})

        tool_calls = []
        for tc in (message.get("tool_calls") or []):
            try:
                input_data = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, KeyError):
                input_data = {}
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=tc["function"]["name"],
                input=input_data,
            ))

        result = LLMToolResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=self.model,
            stop_reason=choice.get("finish_reason"),
        )
        result._raw_response = data
        return result

    async def stream_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ):
        """Token-stream text deltas (OpenAI SSE), accumulate tool_calls, then
        yield the final LLMToolResponse with a raw dict for format_tool_results."""
        formatted = []
        if system:
            formatted.append({"role": "system", "content": system})
        formatted.extend(messages)

        body = {
            "model": self.model,
            "messages": formatted,
            "max_tokens": max_tokens,
            "tools": self._convert_tools_to_openai(tools),
            "stream": True,
        }

        acc_content = ""
        acc_tools: dict[int, dict] = {}
        usage: dict = {}

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", f"{self.BASE_URL}/chat/completions",
                headers=self._headers(), json=body,
            ) as resp:
                if resp.status_code == 429:
                    raise RateLimitError(provider=self.provider, model=self.model,
                                         message="Rate limit exceeded")
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                    choices = chunk.get("choices") or [{}]
                    delta = choices[0].get("delta", {})
                    if delta.get("content"):
                        acc_content += delta["content"]
                        yield delta["content"]
                    for tc in (delta.get("tool_calls") or []):
                        idx = tc.get("index", 0)
                        e = acc_tools.setdefault(idx, {"id": "", "name": "", "args": ""})
                        if tc.get("id"):
                            e["id"] = tc["id"]
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            e["name"] = fn["name"]
                        if fn.get("arguments"):
                            e["args"] += fn["arguments"]

        tool_calls = []
        raw_tcs = []
        for idx in sorted(acc_tools):
            e = acc_tools[idx]
            try:
                inp = json.loads(e["args"]) if e["args"] else {}
            except json.JSONDecodeError:
                inp = {}
            tool_calls.append(ToolCall(id=e["id"], name=e["name"], input=inp))
            raw_tcs.append({"id": e["id"], "type": "function",
                            "function": {"name": e["name"], "arguments": e["args"]}})

        raw = {"choices": [{"message": {"content": acc_content or None, "tool_calls": raw_tcs}}]}
        resp_obj = LLMToolResponse(
            content=acc_content,
            tool_calls=tool_calls,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=self.model,
            stop_reason=None,
        )
        resp_obj._raw_response = raw
        yield resp_obj

    def format_tool_results(
        self,
        tool_response: LLMToolResponse,
        tool_results: list[ToolResult],
    ) -> tuple[dict, list[dict]]:
        """Format tool results (OpenAI format)."""
        return self._format_openai_tool_results(
            tool_response._raw_response, tool_results, response_is_dict=True
        )

    def get_model_name(self) -> str:
        return self.model

    def set_model(self, model: str):
        self.model = self.MODELS.get(model, model)

    @classmethod
    def list_models(cls) -> list[str]:
        return [
            "qwen3.6-plus",       # Qwen 3.6 Plus 1M context (FREE)
            "openrouter-free",    # Auto-select best free model
        ]
