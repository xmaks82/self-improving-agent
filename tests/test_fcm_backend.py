"""Phase 5: FCM as a first-class provider/backend in the factory."""

from agent.clients.factory import get_provider, create_client
from agent.main import check_api_keys


def test_fcm_provider_resolves():
    assert get_provider("fcm") == "fcm"


def test_fcm_client_created_no_key_needed():
    c = create_client("fcm")
    assert c.provider == "fcm"
    assert c.supports_tools is True
    assert c.BASE_URL.endswith("/v1")          # OpenAI-compatible endpoint
    assert c.get_model_name()                    # resolved model id
    # FCM router needs no cloud key
    assert check_api_keys("fcm") is True
