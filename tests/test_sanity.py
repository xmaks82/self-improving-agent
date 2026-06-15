"""Basic sanity checks for core runtime contracts."""

import inspect
import tomllib
from pathlib import Path

from agent import __version__
from agent.clients.anthropic_client import AnthropicClient
from agent.main import check_api_keys


def test_package_version_matches_pyproject():
    """Ensure runtime package version matches declared project version."""
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    assert __version__ == pyproject["project"]["version"]


def test_check_api_keys_requires_provider_key(monkeypatch):
    """A model must require its provider's API key (llama-4-maverick → sambanova)."""
    monkeypatch.delenv("SAMBANOVA_API_KEY", raising=False)
    assert check_api_keys("llama-4-maverick") is False

    monkeypatch.setenv("SAMBANOVA_API_KEY", "test-key")
    assert check_api_keys("llama-4-maverick") is True


def test_check_api_keys_covers_openrouter(monkeypatch):
    """OpenRouter models must require OPENROUTER_API_KEY (audit gap)."""
    # Find any openrouter-mapped model; skip if none in the current map.
    import agent.clients.factory as fac
    or_models = [m for m, p in getattr(fac, "MODEL_PROVIDERS", {}).items() if p == "openrouter"]
    if not or_models:
        return
    model = or_models[0]
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert check_api_keys(model) is False
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    assert check_api_keys(model) is True


def test_anthropic_stream_is_async_generator():
    """Main agent expects async iteration over provider streams."""
    assert inspect.isasyncgenfunction(AnthropicClient.stream)
