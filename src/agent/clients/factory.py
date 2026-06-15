"""Factory for creating LLM clients."""

from typing import Optional
import os

from .base import BaseLLMClient


# Model to provider mapping (updated 2026-06-01)
MODEL_PROVIDERS = {
    # === ANTHROPIC (paid) ===
    "claude-opus-4.8": "anthropic",
    "claude-opus-4.7": "anthropic",
    "claude-opus-4.6": "anthropic",
    "claude-sonnet-4.6": "anthropic",
    "claude-opus-4.5": "anthropic",
    "claude-sonnet-4.5": "anthropic",
    "claude-opus": "anthropic",
    "claude-haiku": "anthropic",

    # === GROQ (free, fast) ===
    "llama-4-scout": "groq",
    "llama-3.3-70b": "groq",
    "llama-3.1-8b": "groq",
    "qwen3-32b": "groq",
    "gpt-oss-120b": "groq",
    "gpt-oss-20b": "groq",

    # === CEREBRAS (free 1M tokens/day, ultra-fast) ===
    "llama3.1-8b": "cerebras",
    "cerebras": "cerebras",
    "qwen3-235b": "cerebras",
    "gpt-oss-120b-cerebras": "cerebras",
    "glm-4.7-cerebras": "cerebras",

    # === ZHIPU (flash models free, rest paid) ===
    "glm-4.5-flash": "zhipu",
    "glm-4.7-flash": "zhipu",
    "glm-5.1": "zhipu",
    "glm-5": "zhipu",
    "glm-5-code": "zhipu",
    "glm-4.7": "zhipu",
    "glm-4.5-air": "zhipu",
    "glm": "zhipu",

    # === OPENROUTER (free models, 200+ models) ===
    "qwen3-next": "openrouter",
    "qwen3-coder": "openrouter",
    "kimi-k2.6": "openrouter",
    "glm-4.5-air-free": "openrouter",
    "qwen3.6-plus": "openrouter",   # alias → qwen3-next (старое имя)
    "openrouter-free": "openrouter",

    # === FCM (local free-model router: health-probe + auto-failover) ===
    "fcm": "fcm",

    # === SAMBANOVA (free, ultra-fast 580 t/s) ===
    "sambanova": "sambanova",
    "llama-4-maverick": "sambanova",
    "samba-llama-70b": "sambanova",
    "deepseek-v3.1": "sambanova",
    "deepseek-v3.2": "sambanova",
    "gpt-oss-120b-samba": "sambanova",
    "minimax-m2.7": "sambanova",
    "gemma-4-31b": "sambanova",
    "gemma-3-12b": "sambanova",
}


def get_provider(model: str) -> str:
    """Determine provider from model name."""
    # Check exact match
    if model in MODEL_PROVIDERS:
        return MODEL_PROVIDERS[model]

    # Check prefix
    if model.startswith("fcm"):
        return "fcm"
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("kimi"):
        return "openrouter"  # Kimi снят с Groq 2026-03 → теперь через OpenRouter
    if model.startswith("gpt-oss"):
        return "groq"
    if model.startswith("llama3.1") or model.startswith("cerebras") or model.startswith("qwen-3-235b"):
        return "cerebras"
    if model.startswith("glm") or model.startswith("codegeex"):
        return "zhipu"
    if model.startswith("samba") or model.startswith("Meta-Llama") or model.startswith("DeepSeek") or model.startswith("Qwen") or model.startswith("Llama-4") or model.startswith("minimax") or model.startswith("gemma"):
        return "sambanova"
    if model.startswith("llama-"):
        return "groq"

    # Default to groq (most reliable free)
    return "groq"


def create_client(
    model: str = "llama-4-scout",
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
        api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")

        # Try OAuth subscription first, fallback to API key on failure
        auth_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
        if not auth_token:
            try:
                from ..auth.oauth import get_auth_token
                auth_token = get_auth_token()
            except Exception:
                auth_token = None

        if auth_token:
            # Pass both: auth_token for subscription, api_key as fallback
            return AnthropicClient(
                auth_token=auth_token,
                api_key=api_key,  # used if OAuth gets blocked
                model=model,
            )
        return AnthropicClient(api_key=api_key, model=model)

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

    elif provider == "openrouter":
        from .openrouter_client import OpenRouterClient
        return OpenRouterClient(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            model=model,
        )

    elif provider == "fcm":
        from .fcm_client import FCMClient
        return FCMClient(model=model)

    else:
        raise ValueError(f"Unknown provider for model: {model}")


def get_available_models() -> dict[str, list[str]]:
    """Get available models grouped by provider."""
    from .anthropic_client import AnthropicClient
    from .groq_client import GroqClient
    from .cerebras_client import CerebrasClient
    from .zhipu_client import ZhipuClient
    from .sambanova_client import SambanovaClient
    from .openrouter_client import OpenRouterClient

    return {
        "anthropic": AnthropicClient.list_models(),
        "groq": GroqClient.list_models(),
        "cerebras": CerebrasClient.list_models(),
        "zhipu": ZhipuClient.list_models(),
        "sambanova": SambanovaClient.list_models(),
        "openrouter": OpenRouterClient.list_models(),
    }


def get_free_models() -> dict[str, list[str]]:
    """Get only free models grouped by provider."""
    from .groq_client import GroqClient
    from .cerebras_client import CerebrasClient
    from .sambanova_client import SambanovaClient
    from .openrouter_client import OpenRouterClient

    return {
        "sambanova (free, 580 t/s)": SambanovaClient.list_models(),
        "groq (free, fast)": GroqClient.list_models(),
        "cerebras (free 1M/day, ultra-fast)": CerebrasClient.list_models(),
        "openrouter (free, 1M ctx)": OpenRouterClient.list_models(),
        "zhipu (free)": ["glm-4.5-flash", "glm-4.7-flash"],
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
        "groq": ["llama-3.3-70b", "llama-4-scout"],
        "cerebras": ["llama3.1-8b", "qwen3-235b"],
        "zhipu": ["glm-4.5-flash", "glm-4.7-flash"],
        "sambanova": ["samba-llama-70b", "deepseek-v3.2"],
        "anthropic": ["claude-haiku", "claude-sonnet-4.6"],
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
