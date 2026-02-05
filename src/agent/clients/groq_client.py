"""Groq API client - free tier with very fast inference."""

from typing import AsyncIterator, Optional
import json
import os

try:
    from groq import Groq
except ImportError:
    Groq = None

from .base import BaseLLMClient, LLMResponse, LLMToolResponse, ToolCall, ToolResult


class GroqClient(BaseLLMClient):
    """
    Client for Groq API - extremely fast inference on LPU hardware.

    Free tier: 14,400 requests/day, no credit card required.
    Get API key: https://console.groq.com/
    """

    provider = "groq"
    supports_streaming = True
    supports_tools = True

    # Available models (February 2026)
    MODELS = {
        # Llama 4 - newest (preview)
        "llama-4-maverick": "meta-llama/llama-4-maverick-17b-128e-instruct",
        "llama-4-scout": "meta-llama/llama-4-scout-17b-16e-instruct",

        # Llama 3.3 - production, proven quality
        "llama-3.3-70b": "llama-3.3-70b-versatile",

        # Qwen 3 - thinking mode (preview)
        "qwen3-32b": "qwen/qwen3-32b",

        # Kimi K2 - Moonshot AI (preview)
        "kimi-k2": "moonshotai/kimi-k2-instruct-0905",

        # GPT-OSS - OpenAI open source
        "gpt-oss-120b": "openai/gpt-oss-120b",
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
            kwargs["tools"] = self._convert_tools_to_openai(tools)

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

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> LLMToolResponse:
        """Chat with tools using OpenAI format."""
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
            "tools": self._convert_tools_to_openai(tools),
        }

        response = self.client.chat.completions.create(**kwargs)

        # Extract content and tool calls
        message = response.choices[0].message
        content = message.content or ""
        tool_calls = []

        if message.tool_calls:
            for tc in message.tool_calls:
                # Arguments are JSON string in OpenAI format
                try:
                    input_data = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    input_data = {}

                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    input=input_data,
                ))

        result = LLMToolResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            model=self.model,
            stop_reason=response.choices[0].finish_reason,
        )
        result._raw_response = response
        return result

    def format_tool_results(
        self,
        tool_response: LLMToolResponse,
        tool_results: list[ToolResult],
    ) -> tuple[dict, list[dict]]:
        """Format tool results for OpenAI conversation format."""
        return self._format_openai_tool_results(
            tool_response._raw_response, tool_results, response_is_dict=False
        )

    def get_model_name(self) -> str:
        return self.model

    def set_model(self, model: str):
        self.model = self.MODELS.get(model, model)

    @classmethod
    def list_models(cls) -> list[str]:
        """List available model shortcuts."""
        return [
            "llama-4-maverick",     # Newest Llama 4 (128 experts)
            "llama-4-scout",        # Llama 4 fast (16 experts)
            "llama-3.3-70b",        # Production, proven quality
            "qwen3-32b",            # Qwen 3 thinking mode
            "kimi-k2",              # Moonshot AI
            "gpt-oss-120b",         # OpenAI OSS
        ]
