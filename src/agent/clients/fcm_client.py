"""FCM backend client — free-model orchestration via an OpenAI-compatible endpoint.

Points the agent at the free-coding-models router / sanitize-proxy (the
battle-tested free-model stack with health-probe + auto-failover). It's just an
OpenAI-compatible endpoint, so we reuse OpenRouterClient's request/format logic
and only swap the base URL, the (optional) key, and the headers.

Config (no hardcoded secrets/paths):
  FCM_BASE_URL  — OpenAI-compatible endpoint (default http://localhost:9999/v1,
                  the sanitize-proxy in front of the FCM router)
  FCM_API_KEY   — optional; the local router usually needs none
  FCM_MODEL     — default model id (router may route by its own active set)
"""
import os
from typing import Optional

from .openrouter_client import OpenRouterClient


class FCMClient(OpenRouterClient):
    """OpenAI-compatible client for the local free-model router (FCM)."""

    provider = "fcm"
    BASE_URL = os.getenv("FCM_BASE_URL", "http://localhost:9999/v1")

    # Passthrough: the model id is sent as-is; the router resolves it against its
    # curated active set (smart model first for agentic work).
    MODELS = {
        "fcm": os.getenv("FCM_MODEL", "zai-glm-4.7"),
    }

    def __init__(self, api_key: Optional[str] = None, model: str = "fcm"):
        # Key is optional for the local router; default to a placeholder so the
        # OpenAI-compatible Authorization header is always well-formed.
        self.api_key = api_key or os.getenv("FCM_API_KEY", "fcm")
        self.model = self.MODELS.get(model, model)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @classmethod
    def list_models(cls) -> list[str]:
        return ["fcm"]
