"""Custom exceptions for LLM clients."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RateLimitError(Exception):
    """
    Unified rate limit exception across all providers.

    Raised when any provider returns a rate limit error (HTTP 429).
    Contains information needed for fallback handling.
    """
    provider: str
    model: str
    message: str
    retry_after: Optional[float] = None

    def __str__(self):
        return f"Rate limit exceeded for {self.provider}/{self.model}: {self.message}"
