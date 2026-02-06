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

    # === CEREBRAS (free 1M tokens/day, ultra-fast) ===
    "llama3.1-8b": "cerebras",
    "cerebras": "cerebras",
    "cerebras-8b": "cerebras",

    # === ZHIPU (glm-4.5-flash free, rest paid) ===
    "glm-4.5-flash": "zhipu",
    "glm-4.7": "zhipu",
    "glm-4.5-air": "zhipu",
    "glm": "zhipu",

    # === SAMBANOVA (free, ultra-fast 580 t/s) ===
    "sambanova": "sambanova",
    "samba-llama-70b": "sambanova",
    "samba-llama-8b": "sambanova",
    "samba-deepseek": "sambanova",
    "deepseek-r1-70b": "sambanova",
    "deepseek-v3": "sambanova",
    "qwq-32b": "sambanova",
}


def get_provider(model: str) -> str:
    """Determine provider from model name."""
    # Check exact match
    if model in MODEL_PROVIDERS:
        return MODEL_PROVIDERS[model]

    # Check prefix
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("llama-4") or model.startswith("kimi") or model.startswith("gpt-oss"):
        return "groq"
    if model.startswith("llama3.1") or model.startswith("cerebras"):
        return "cerebras"
    if model.startswith("glm") or model.startswith("codegeex"):
        return "zhipu"
    if model.startswith("samba") or model.startswith("Meta-Llama") or model.startswith("DeepSeek") or model.startswith("Qwen"):
        return "sambanova"

    # Default to groq (most reliable free)
    return "groq"


def create_client(
    model: str = "llama-4-maverick",
    anthropic_api_key: Optional[str] = None,
    groq_api_key: Optional[str] = None,
    cerebras_api_key: Optional[str] = None,
    zhipu_api_key: Optional[str] = None,
    sambanova_api_key: Optional[str] = None,
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

    elif provider == "cerebras":
        from .cerebras_client import CerebrasClient
        return CerebrasClient(
            api_key=cerebras_api_key or os.getenv("CEREBRAS_API_KEY"),
            model=model,
        )

    elif provider == "zhipu":
        from .zhipu_client import ZhipuClient
        return ZhipuClient(
            api_key=zhipu_api_key or os.getenv("ZHIPU_API_KEY"),
            model=model,
        )

    elif provider == "sambanova":
        from .sambanova_client import SambanovaClient
        return SambanovaClient(
            api_key=sambanova_api_key or os.getenv("SAMBANOVA_API_KEY"),
            model=model,
        )

    else:
        raise ValueError(f"Unknown provider for model: {model}")


def get_available_models() -> dict[str, list[str]]:
    """Get available models grouped by provider."""
    from .anthropic_client import AnthropicClient
    from .groq_client import GroqClient
    from .cerebras_client import CerebrasClient
    from .zhipu_client import ZhipuClient
    from .sambanova_client import SambanovaClient

    return {
        "anthropic": AnthropicClient.list_models(),
        "groq": GroqClient.list_models(),
        "cerebras": CerebrasClient.list_models(),
        "zhipu": ZhipuClient.list_models(),
        "sambanova": SambanovaClient.list_models(),
    }


def get_free_models() -> dict[str, list[str]]:
    """Get only free models grouped by provider."""
    from .groq_client import GroqClient
    from .cerebras_client import CerebrasClient
    from .zhipu_client import ZhipuClient
    from .sambanova_client import SambanovaClient

    return {
        "groq (free, fast)": GroqClient.list_models(),
        "cerebras (free 1M/day, ultra-fast)": CerebrasClient.list_models(),
        "zhipu (free)": ["glm-4.5-flash"],
        "sambanova (free, 580 t/s)": SambanovaClient.list_models(),
    }


def get_fallback_models(current_model: str) -> list[str]:
    """
    Get ordered list of fallback models when rate limit is hit.

    Priority:
    1. Other free providers with valid API keys
    2. Paid providers as last resort (if keys available)

    Args:
        current_model: The model that hit rate limit

    Returns:
        List of model names to try, in priority order
    """
    current_provider = get_provider(current_model)
    fallbacks = []

    # Define fallback models by provider (most reliable first)
    provider_fallbacks = {
        "groq": ["llama-3.3-70b", "llama-4-maverick"],
        "cerebras": ["llama3.1-8b"],
        "zhipu": ["glm-4.5-flash"],
        "sambanova": ["samba-llama-70b", "samba-llama-8b"],
        "anthropic": ["claude-haiku", "claude-sonnet"],
    }

    # Check which providers have valid API keys
    available_providers = []
    if os.getenv("GROQ_API_KEY"):
        available_providers.append("groq")
    if os.getenv("CEREBRAS_API_KEY"):
        available_providers.append("cerebras")
    if os.getenv("ZHIPU_API_KEY"):
        available_providers.append("zhipu")
    if os.getenv("SAMBANOVA_API_KEY"):
        available_providers.append("sambanova")
    if os.getenv("ANTHROPIC_API_KEY"):
        available_providers.append("anthropic")

    # Priority order: sambanova (fastest) -> groq -> cerebras -> zhipu -> anthropic
    priority_order = ["sambanova", "groq", "cerebras", "zhipu", "anthropic"]

    for provider in priority_order:
        if provider not in available_providers:
            continue
        for model in provider_fallbacks[provider]:
            # Skip current model
            if model == current_model:
                continue
            # Skip models from same provider (they likely have same rate limit)
            if provider == current_provider:
                continue
            fallbacks.append(model)

    return fallbacks
