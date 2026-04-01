"""Token usage and cost tracking per model/session."""

from dataclasses import dataclass, field

# Prices in $ per 1M tokens (input/output)
MODEL_PRICES: dict[str, dict[str, float]] = {
    # Free models
    "groq": {"input": 0.0, "output": 0.0},
    "cerebras": {"input": 0.0, "output": 0.0},
    "sambanova": {"input": 0.0, "output": 0.0},
    "openrouter": {"input": 0.0, "output": 0.0},
    "zhipu/glm-4.5-flash": {"input": 0.0, "output": 0.0},
    "zhipu/glm-4.7-flash": {"input": 0.0, "output": 0.0},
    # Paid - Anthropic (current gen pricing)
    "anthropic/claude-opus-4-6": {"input": 5.0, "output": 25.0},
    "anthropic/claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "anthropic/claude-opus-4-5": {"input": 5.0, "output": 25.0},
    "anthropic/claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "anthropic/claude-haiku-4-5": {"input": 1.0, "output": 5.0},
    # Paid - Zhipu
    "zhipu/glm-5.1": {"input": 1.0, "output": 3.20},
    "zhipu/glm-5": {"input": 1.0, "output": 3.20},
    "zhipu/glm-5-code": {"input": 1.20, "output": 5.0},
    "zhipu/glm-4.7": {"input": 0.60, "output": 2.20},
}


@dataclass
class TokenUsage:
    """Token usage for a single model."""
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class CostTracker:
    """Tracks token usage and costs per model/session."""

    _usage: dict[str, TokenUsage] = field(default_factory=dict)  # "provider/model" -> usage

    def record(self, provider: str, model: str, input_tokens: int, output_tokens: int):
        """Record token usage for a request."""
        key = f"{provider}/{model}"
        if key not in self._usage:
            self._usage[key] = TokenUsage()
        usage = self._usage[key]
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens
        usage.requests += 1

    def get_cost(self, provider: str, model: str, usage: TokenUsage) -> float:
        """Calculate cost for given usage."""
        # Try exact match, then provider-level match
        key = f"{provider}/{model}"
        prices = MODEL_PRICES.get(key) or MODEL_PRICES.get(provider, {"input": 0.0, "output": 0.0})
        return (
            usage.input_tokens * prices["input"] / 1_000_000
            + usage.output_tokens * prices["output"] / 1_000_000
        )

    @property
    def total_cost(self) -> float:
        """Total cost across all models."""
        total = 0.0
        for key, usage in self._usage.items():
            provider = key.split("/")[0]
            model = "/".join(key.split("/")[1:])
            total += self.get_cost(provider, model, usage)
        return total

    @property
    def total_tokens(self) -> int:
        """Total tokens across all models."""
        return sum(u.total for u in self._usage.values())

    @property
    def total_requests(self) -> int:
        """Total requests across all models."""
        return sum(u.requests for u in self._usage.values())

    def get_breakdown(self) -> list[dict]:
        """Get per-model cost breakdown."""
        result = []
        for key, usage in sorted(self._usage.items()):
            provider = key.split("/")[0]
            model = "/".join(key.split("/")[1:])
            cost = self.get_cost(provider, model, usage)
            result.append({
                "model": key,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total,
                "requests": usage.requests,
                "cost": cost,
            })
        return result

    def reset(self):
        """Reset all usage counters."""
        self._usage.clear()
