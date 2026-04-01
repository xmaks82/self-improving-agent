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


def test_check_api_keys_for_groq(monkeypatch):
    """The default Groq model must require GROQ_API_KEY."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert check_api_keys("llama-4-maverick") is False

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    assert check_api_keys("llama-4-maverick") is True


def test_anthropic_stream_is_async_generator():
    """Main agent expects async iteration over provider streams."""
    assert inspect.isasyncgenfunction(AnthropicClient.stream)
