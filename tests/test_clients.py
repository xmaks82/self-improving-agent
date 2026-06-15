"""Client-level contracts: OAuth → API-key fallback decision."""


def test_oauth_fallback_switches_on_401(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    from agent.clients.anthropic_client import AnthropicClient

    c = AnthropicClient(api_key="fb-key", model="claude-haiku", auth_token="oauth-tok")
    assert c._auth_mode == "subscription"

    err = Exception("unauthorized")
    err.response = type("R", (), {"status_code": 401})()
    assert c._should_fallback(err) is True
    assert c._auth_mode == "api_key_fallback"


def test_no_fallback_without_subscription(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    from agent.clients.anthropic_client import AnthropicClient

    c = AnthropicClient(api_key="k", model="claude-haiku")  # api_key mode, not subscription
    err = Exception("forbidden")
    err.response = type("R", (), {"status_code": 403})()
    assert c._should_fallback(err) is False
