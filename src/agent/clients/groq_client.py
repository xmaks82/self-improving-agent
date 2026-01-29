"""Groq API client - free tier with very fast inference."""

from typing import AsyncIterator, Optional
import os

try:
    from groq import Groq
except ImportError:
    Groq = None

from .base import BaseLLMClient, LLMResponse


class GroqClient(BaseLLMClient):
    """
    Client for Groq API - extremely fast inference on LPU hardware.

    Free tier: 14,400 requests/day, no credit card required.
    Get API key: https://console.groq.com/
    """

    provider = "groq"
    supports_streaming = True
    supports_tools = True

    # Available models (January 2026)
    MODELS = {
        # Llama 3.3 - best quality
        "llama-3.3-70b": "llama-3.3-70b-versatile",
        "llama-3.3": "llama-3.3-70b-versatile",

        # Llama 4 - newest!
        "llama-4-maverick": "meta-llama/llama-4-maverick-17b-128e-instruct",
        "llama-4-scout": "meta-llama/llama-4-scout-17b-16e-instruct",
        "llama-4": "meta-llama/llama-4-maverick-17b-128e-instruct",

        # Llama 3.1
        "llama-3.1-8b": "llama-3.1-8b-instant",

        # Qwen 3
        "qwen3-32b": "qwen/qwen3-32b",
        "qwen3": "qwen/qwen3-32b",

        # Kimi K2 - Moonshot AI
        "kimi-k2": "moonshotai/kimi-k2-instruct",

        # GPT-OSS - OpenAI open source
        "gpt-oss-120b": "openai/gpt-oss-120b",
        "gpt-oss-20b": "openai/gpt-oss-20b",
        "gpt-oss": "openai/gpt-oss-120b",

        # Full names
        "llama-3.3-70b-versatile": "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant": "llama-3.1-8b-instant",
    }

    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b"):
        if Groq is None:
            raise ImportError(
                "groq package not installed. Run: pip install groq"
            )

        api_key = api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "Groq API key required. Set GROQ_API_KEY environment variable.\n"
                "Get free key at: https://console.groq.com/"
            )

        self.client = Groq(api_key=api_key)
        self.model = self.MODELS.get(model, model)

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

        kwargs = {
            "model": self.model,
            "messages": formatted_messages,
            "max_tokens": max_tokens,
        }

        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        response = self.client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content or ""

        return LLMResponse(
            content=content,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            model=self.model,
            stop_reason=response.choices[0].finish_reason,
        )

    async def stream(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Streaming chat completion - extremely fast on Groq."""
        formatted_messages = []

        if system:
            formatted_messages.append({"role": "system", "content": system})

        formatted_messages.extend(messages)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=formatted_messages,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert Anthropic tool format to OpenAI format."""
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

    def get_model_name(self) -> str:
        return self.model

    def set_model(self, model: str):
        self.model = self.MODELS.get(model, model)

    @classmethod
    def list_models(cls) -> list[str]:
        """List available model shortcuts."""
        return [
            "llama-3.3-70b",      # Best overall
            "llama-4-maverick",   # Newest Llama 4
            "llama-4-scout",      # Llama 4 smaller
            "qwen3-32b",          # Qwen 3
            "kimi-k2",            # Moonshot AI
            "gpt-oss-120b",       # OpenAI OSS
        ]
