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

    # === GROQ (free, fast) ===
    "llama-4-maverick": "groq",
    "llama-4-scout": "groq",
    "llama-3.3-70b": "groq",
    "qwen3-32b": "groq",
    "kimi-k2": "groq",
    "gpt-oss-120b": "groq",

    # === DEEPSEEK (free tier 5M tokens/month) ===
    "deepseek-chat": "deepseek",
    "deepseek-v3": "deepseek",
    "deepseek-reasoner": "deepseek",
    "deepseek-r1": "deepseek",
    "deepseek": "deepseek",

    # === ZHIPU (free tier with rate limits) ===
    "glm-4.7": "zhipu",
    "glm-4.5-air": "zhipu",
    "glm-4.5-flash": "zhipu",
    "glm-4-plus": "zhipu",
    "glm": "zhipu",
}


def get_provider(model: str) -> str:
    """Determine provider from model name."""
    # Check exact match
    if model in MODEL_PROVIDERS:
        return MODEL_PROVIDERS[model]

    # Check prefix
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("llama") or model.startswith("qwen") or model.startswith("kimi") or model.startswith("gpt-oss"):
        return "groq"
    if model.startswith("deepseek"):
        return "deepseek"
    if model.startswith("glm") or model.startswith("codegeex"):
        return "zhipu"

    # Default to groq (most reliable free)
    return "groq"


def create_client(
    model: str = "llama-4-maverick",
    anthropic_api_key: Optional[str] = None,
    groq_api_key: Optional[str] = None,
    deepseek_api_key: Optional[str] = None,
    zhipu_api_key: Optional[str] = None,
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

    elif provider == "groq":
        from .groq_client import GroqClient
        return GroqClient(
            api_key=groq_api_key or os.getenv("GROQ_API_KEY"),
            model=model,
        )

    elif provider == "deepseek":
        from .deepseek_client import DeepSeekClient
        return DeepSeekClient(
            api_key=deepseek_api_key or os.getenv("DEEPSEEK_API_KEY"),
            model=model,
        )

    elif provider == "zhipu":
        from .zhipu_client import ZhipuClient
        return ZhipuClient(
            api_key=zhipu_api_key or os.getenv("ZHIPU_API_KEY"),
            model=model,
        )

    else:
        raise ValueError(f"Unknown provider for model: {model}")


def get_available_models() -> dict[str, list[str]]:
    """Get available models grouped by provider."""
    from .anthropic_client import AnthropicClient
    from .groq_client import GroqClient
    from .deepseek_client import DeepSeekClient
    from .zhipu_client import ZhipuClient

    return {
        "anthropic": AnthropicClient.list_models(),
        "groq": GroqClient.list_models(),
        "deepseek": DeepSeekClient.list_models(),
        "zhipu": ZhipuClient.list_models(),
    }


def get_free_models() -> dict[str, list[str]]:
    """Get only free models grouped by provider."""
    from .groq_client import GroqClient
    from .deepseek_client import DeepSeekClient
    from .zhipu_client import ZhipuClient

    return {
        "groq (free, fast)": GroqClient.list_models(),
        "deepseek (free 5M/month)": DeepSeekClient.list_models(),
        "zhipu (free tier)": ZhipuClient.list_models(),
    }


def get_all_model_names() -> list[str]:
    """Get flat list of all available model names."""
    models = []
    for provider_models in get_available_models().values():
        models.extend(provider_models)
    return models
