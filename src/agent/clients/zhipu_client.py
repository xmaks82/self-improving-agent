"""Zhipu AI GLM client implementation."""

from typing import AsyncIterator, Iterator, Optional
from zhipuai import ZhipuAI

from .base import BaseLLMClient, LLMResponse


class ZhipuClient(BaseLLMClient):
    """Client for Zhipu AI GLM models."""

    provider = "zhipu"
    supports_streaming = True
    supports_tools = True

    # Available GLM models (January 2026)
    # Note: Free tier has strict rate limits (1113 error)
    MODELS = {
        # GLM 4.7 - newest
        "glm-4.7": "glm-4.7",

        # GLM 4.5 series
        "glm-4.5-air": "glm-4.5-air",
        "glm-4.5-airx": "glm-4.5-airx",
        "glm-4.5-flash": "glm-4.5-flash",
        "glm-4.5": "glm-4.5-air",

        # GLM 4 Plus
        "glm-4-plus": "glm-4-plus",
        "glm-4": "glm-4-plus",

        # Aliases
        "glm": "glm-4.7",
    }

    def __init__(self, api_key: Optional[str] = None, model: str = "glm-4"):
        if not api_key:
            import os
            api_key = os.getenv("ZHIPU_API_KEY")

        if not api_key:
            raise ValueError(
                "Zhipu API key required. Set ZHIPU_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.client = ZhipuAI(api_key=api_key)
        self.model = self.MODELS.get(model, model)

    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """Synchronous chat completion."""
        # Zhipu uses system message in messages array
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
            # Convert Anthropic tool format to Zhipu/OpenAI format
            kwargs["tools"] = self._convert_tools(tools)

        response = self.client.chat.completions.create(**kwargs)

        # Extract content
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
        """Streaming chat completion."""
        formatted_messages = []

        if system:
            formatted_messages.append({
                "role": "system",
                "content": system,
            })

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

    def stream_with_usage(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> tuple[Iterator[str], dict]:
        """Streaming with usage tracking."""
        usage = {"input_tokens": 0, "output_tokens": 0}

        formatted_messages = []
        if system:
            formatted_messages.append({"role": "system", "content": system})
        formatted_messages.extend(messages)

        def generate():
            response = self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                max_tokens=max_tokens,
                stream=True,
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

                # Zhipu includes usage in last chunk
                if hasattr(chunk, 'usage') and chunk.usage:
                    usage["input_tokens"] = chunk.usage.prompt_tokens
                    usage["output_tokens"] = chunk.usage.completion_tokens

        return generate(), usage

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert Anthropic tool format to OpenAI/Zhipu format."""
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
        return ["glm-4.7", "glm-4.5-air", "glm-4.5-flash", "glm-4-plus"]
