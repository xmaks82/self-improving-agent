"""Optional embeddings client for hybrid (vector + keyword) memory retrieval.

OpenAI-compatible ``/v1/embeddings`` endpoint. Fully optional and graceful:
if ``EMBEDDINGS_URL`` is unset or the endpoint is unreachable, retrieval
transparently falls back to keyword search — so the agent works out of the box
for anyone who clones the repo without an embeddings server.

Point ``EMBEDDINGS_URL`` at your own endpoint (a local llama-server, OpenAI,
Ollama, etc.). Nothing about your infrastructure ships in the repo.
"""
from __future__ import annotations

import logging
import math
from typing import Optional

import httpx

from ..config import config

log = logging.getLogger(__name__)


class EmbeddingsClient:
    """Async OpenAI-compatible embeddings client. Best-effort: any failure
    returns ``None`` and callers fall back to keyword retrieval."""

    def __init__(
        self,
        url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        cfg = config.embeddings
        self.url = url if url is not None else cfg.url
        self.model = model or cfg.model
        self.timeout = timeout if timeout is not None else cfg.timeout
        self.enabled = cfg.enabled

    @property
    def available(self) -> bool:
        return bool(self.enabled and self.url)

    async def embed(self, text: str) -> Optional[list[float]]:
        """Embed a single string. None on any failure (→ keyword fallback)."""
        if not self.available or not text:
            return None
        out = await self.embed_batch([text])
        return out[0] if out else None

    async def embed_batch(self, texts: list[str]) -> Optional[list[list[float]]]:
        """Embed a batch. None on any failure."""
        if not self.available or not texts:
            return None
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self.url, json={"input": texts, "model": self.model}
                )
                resp.raise_for_status()
                data = resp.json().get("data", [])
                if len(data) != len(texts):
                    return None
                return [d["embedding"] for d in data]
        except Exception as e:  # noqa: BLE001 — best-effort, never break recall
            log.debug("embeddings unavailable, falling back to keyword: %s", e)
            return None


def cosine_similarity(a: Optional[list[float]], b: Optional[list[float]]) -> float:
    """Cosine similarity in [-1, 1]; 0.0 for missing/mismatched vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
