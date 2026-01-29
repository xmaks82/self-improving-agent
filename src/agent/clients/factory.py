"""Factory for creating LLM clients."""

from typing import Optional
import os

from .base import BaseLLMClient


# Model to provider mapping
MODEL_PROVIDERS = {
    # === ANTHROPIC (paid) ===
    "claude-opus-4.5": "anthropic",
    "claude-sonnet": "anthropic",
    "claude-opus": "anthropic",
    "claude-haiku": "anthropic",
    "claude-opus-4-5-20251101": "anthropic",
    "claude-sonnet-4-20250514": "anthropic",
    "claude-opus-4-20250514": "anthropic",
    "claude-haiku-3-5-20241022": "anthropic",

    # === ZHIPU (free tier with rate limits) ===
    "glm-4.7": "zhipu",
    "glm-4.5-air": "zhipu",
    "glm-4.5-airx": "zhipu",
    "glm-4.5-flash": "zhipu",
    "glm-4.5": "zhipu",
    "glm-4-plus": "zhipu",
    "glm-4": "zhipu",
    "glm": "zhipu",

    # === GROQ (free) ===
    "llama-3.3-70b": "groq",
    "llama-3.3": "groq",
    "llama-4-maverick": "groq",
    "llama-4-scout": "groq",
    "llama-4": "groq",
    "llama-3.1-8b": "groq",
    "qwen3-32b": "groq",
    "qwen3": "groq",
    "kimi-k2": "groq",
    "gpt-oss-120b": "groq",
    "gpt-oss-20b": "groq",
    "gpt-oss": "groq",

    # === OPENROUTER (free models) ===
    "deepseek-r1": "openrouter",
    "deepseek": "openrouter",
    "llama-3.3-70b-or": "openrouter",  # OpenRouter version
    "llama-3.1-405b": "openrouter",
    "llama-3.2-3b": "openrouter",
    "llama": "openrouter",
    "qwen3-coder": "openrouter",
    "qwen3-80b": "openrouter",
    "qwen3-4b": "openrouter",
    "qwen": "openrouter",
    "gemma-3-27b": "openrouter",
    "gemma-3-12b": "openrouter",
    "gemma-3-4b": "openrouter",
    "gemma": "openrouter",
    "mistral-small": "openrouter",
    "nemotron-nano": "openrouter",
    "nemotron-30b": "openrouter",
    "kimi-k2": "openrouter",
    "glm-4.5-air": "openrouter",
    "gpt-oss-120b": "openrouter",
    "hermes-405b": "openrouter",
}


def get_provider(model: str) -> str:
    """Determine provider from model name."""
    # Check exact match
    if model in MODEL_PROVIDERS:
        return MODEL_PROVIDERS[model]

    # Check prefix
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("glm") or model.startswith("codegeex"):
        return "zhipu"
    if model.startswith("llama-3."):
        return "groq"
    if model.startswith("deepseek") or model.startswith("gemma") or model.startswith("qwen3"):
        return "openrouter"

    # Default to openrouter (most flexible)
    return "openrouter"


def create_client(
    model: str = "claude-opus-4.5",
    anthropic_api_key: Optional[str] = None,
    zhipu_api_key: Optional[str] = None,
    groq_api_key: Optional[str] = None,
    openrouter_api_key: Optional[str] = None,
) -> BaseLLMClient:
    """
    Create an LLM client for the specified model.

    Args:
        model: Model name or shortcut
        *_api_key: Provider API keys (uses env if not provided)

    Returns:
        Configured LLM client
    """
    provider = get_provider(model)

    if provider == "anthropic":
        from .anthropic_client import AnthropicClient
        return AnthropicClient(
            api_key=anthropic_api_key or os.getenv("ANTHROPIC_API_KEY"),
            model=model,
        )

    elif provider == "zhipu":
        from .zhipu_client import ZhipuClient
        return ZhipuClient(
            api_key=zhipu_api_key or os.getenv("ZHIPU_API_KEY"),
            model=model,
        )

    elif provider == "groq":
        from .groq_client import GroqClient
        return GroqClient(
            api_key=groq_api_key or os.getenv("GROQ_API_KEY"),
            model=model,
        )

    elif provider == "openrouter":
        from .openrouter_client import OpenRouterClient
        return OpenRouterClient(
            api_key=openrouter_api_key or os.getenv("OPENROUTER_API_KEY"),
            model=model,
        )

    else:
        raise ValueError(f"Unknown provider for model: {model}")


def get_available_models() -> dict[str, list[str]]:
    """Get available models grouped by provider."""
    from .anthropic_client import AnthropicClient
    from .zhipu_client import ZhipuClient
    from .groq_client import GroqClient
    from .openrouter_client import OpenRouterClient

    return {
        "anthropic": AnthropicClient.list_models(),
        "zhipu": ZhipuClient.list_models(),
        "groq": GroqClient.list_models(),
        "openrouter": OpenRouterClient.list_models(),
    }


def get_free_models() -> dict[str, list[str]]:
    """Get only free models grouped by provider."""
    from .groq_client import GroqClient
    from .openrouter_client import OpenRouterClient
    from .zhipu_client import ZhipuClient

    return {
        "groq (free)": GroqClient.list_models(),
        "openrouter (free)": OpenRouterClient.list_models(),
        "zhipu (free tier)": ZhipuClient.list_models(),
    }


def get_all_model_names() -> list[str]:
    """Get flat list of all available model names."""
    models = []
    for provider_models in get_available_models().values():
        models.extend(provider_models)
    return models
