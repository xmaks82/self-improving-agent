"""OpenRouter API client - aggregator with many free models."""

from typing import AsyncIterator, Optional
import json
import os
import httpx

from .base import BaseLLMClient, LLMResponse, LLMToolResponse, ToolCall, ToolResult


class OpenRouterClient(BaseLLMClient):
    """
    Client for OpenRouter - unified API for 400+ models.

    Many free models available, no credit card required.
    Get API key: https://openrouter.ai/keys
    """

    provider = "openrouter"
    supports_streaming = True
    supports_tools = True

    API_BASE = "https://openrouter.ai/api/v1"

    # Free models (January 2026) - suffix :free means completely free
    MODELS = {
        # === TOP FREE MODELS ===
        # DeepSeek R1 - very strong reasoning
        "deepseek-r1": "deepseek/deepseek-r1-0528:free",

        # Meta Llama - best open models
        "llama-3.3-70b": "meta-llama/llama-3.3-70b-instruct:free",
        "llama-3.1-405b": "meta-llama/llama-3.1-405b-instruct:free",
        "llama-3.2-3b": "meta-llama/llama-3.2-3b-instruct:free",

        # Qwen 3 - strong Chinese models
        "qwen3-coder": "qwen/qwen3-coder:free",
        "qwen3-80b": "qwen/qwen3-next-80b-a3b-instruct:free",
        "qwen3-4b": "qwen/qwen3-4b:free",

        # Google Gemma 3
        "gemma-3-27b": "google/gemma-3-27b-it:free",
        "gemma-3-12b": "google/gemma-3-12b-it:free",
        "gemma-3-4b": "google/gemma-3-4b-it:free",

        # Mistral - strong European model
        "mistral-small": "mistralai/mistral-small-3.1-24b-instruct:free",

        # NVIDIA Nemotron
        "nemotron-nano": "nvidia/nemotron-nano-9b-v2:free",
        "nemotron-30b": "nvidia/nemotron-3-nano-30b-a3b:free",

        # Others
        "kimi-k2": "moonshotai/kimi-k2:free",
        "glm-4.5-air": "z-ai/glm-4.5-air:free",
        "gpt-oss-120b": "openai/gpt-oss-120b:free",
        "hermes-405b": "nousresearch/hermes-3-llama-3.1-405b:free",

        # Aliases for convenience
        "deepseek": "deepseek/deepseek-r1-0528:free",
        "llama": "meta-llama/llama-3.3-70b-instruct:free",
        "qwen": "qwen/qwen3-coder:free",
        "gemma": "google/gemma-3-27b-it:free",
    }

    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-r1"):
        api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenRouter API key required. Set OPENROUTER_API_KEY environment variable.\n"
                "Get free key at: https://openrouter.ai/keys"
            )

        self.api_key = api_key
        self.model = self.MODELS.get(model, model)
        self.client = httpx.Client(timeout=120.0)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/self-improving-agent",
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

        response = self.client.post(
            f"{self.API_BASE}/chat/completions",
            headers=self._headers(),
            json=payload,
        )
        response.raise_for_status()
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

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> LLMToolResponse:
        """Chat with tools via OpenRouter API."""
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

        response = self.client.post(
            f"{self.API_BASE}/chat/completions",
            headers=self._headers(),
            json=payload,
        )
        response.raise_for_status()
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
        """List available free model shortcuts."""
        return [
            "deepseek-r1",        # Best reasoning
            "llama-3.3-70b",      # Best Llama (use llama-3.3-70b-or for OpenRouter)
            "llama-3.1-405b",     # Largest free model!
            "qwen3-coder",        # Best for coding
            "gemma-3-27b",        # Google's best free
            "mistral-small",      # European alternative
        ]

    @classmethod
    def list_all_free_models(cls) -> list[str]:
        """List all free model IDs (for reference)."""
        return list(cls.MODELS.keys())
