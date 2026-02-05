"""Zhipu AI GLM client implementation."""

from typing import AsyncIterator, Iterator, Optional
import json
from zhipuai import ZhipuAI

from .base import BaseLLMClient, LLMResponse, LLMToolResponse, ToolCall, ToolResult
from .exceptions import RateLimitError


class ZhipuClient(BaseLLMClient):
    """Client for Zhipu AI GLM models."""

    provider = "zhipu"
    supports_streaming = True
    supports_tools = True

    # Available GLM models (February 2026)
    # Note: Free tier has strict rate limits
    MODELS = {
        # GLM 4.7 - newest
        "glm-4.7": "glm-4.7",

        # GLM 4.5 - balanced
        "glm-4.5-air": "glm-4.5-air",
        "glm-4.5-flash": "glm-4.5-flash",

        # GLM 4 Plus - powerful
        "glm-4-plus": "glm-4-plus",
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

    def _handle_rate_limit(self, e: Exception):
        """Check if exception is rate limit and raise unified error."""
        status_code = getattr(e, "status_code", None)
        if status_code == 429:
            raise RateLimitError(
                provider="zhipu",
                model=self.model,
                message=str(e),
            ) from e

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
            kwargs["tools"] = self._convert_tools_to_openai(tools)

        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            self._handle_rate_limit(e)
            raise

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

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                max_tokens=max_tokens,
                stream=True,
            )
        except Exception as e:
            self._handle_rate_limit(e)
            raise

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
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=formatted_messages,
                    max_tokens=max_tokens,
                    stream=True,
                )
            except Exception as e:
                self._handle_rate_limit(e)
                raise

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

                # Zhipu includes usage in last chunk
                if hasattr(chunk, 'usage') and chunk.usage:
                    usage["input_tokens"] = chunk.usage.prompt_tokens
                    usage["output_tokens"] = chunk.usage.completion_tokens

        return generate(), usage

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> LLMToolResponse:
        """Chat with tools using OpenAI/Zhipu format."""
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

        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            self._handle_rate_limit(e)
            raise

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
        """Format tool results for OpenAI/Zhipu conversation format."""
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
        return ["glm-4.7", "glm-4.5-air", "glm-4.5-flash", "glm-4-plus"]
