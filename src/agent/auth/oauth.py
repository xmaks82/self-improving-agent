"""OAuth authentication for Claude Pro/Max subscriptions.

Flow:
1. User runs `claude setup-token` in Claude Code CLI
2. Token is saved to ~/.claude/.credentials.json
3. This module reads that token and uses it for API calls
4. Token is auto-refreshed when expired

Alternative: user can set CLAUDE_CODE_OAUTH_TOKEN env var directly.
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Anthropic OAuth constants (from Claude Code source)
OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
TOKEN_ENDPOINT = "https://platform.claude.com/v1/oauth/token"
PROFILE_ENDPOINT = "https://api.anthropic.com/api/oauth/profile"

# Claude.ai OAuth scopes
CLAUDE_AI_SCOPES = [
    "user:profile",
    "user:inference",
    "user:sessions:claude_code",
]

# Credentials file locations
CREDENTIALS_PATHS = [
    Path.home() / ".claude" / ".credentials.json",
    Path.home() / ".claude" / "credentials.json",
]


@dataclass
class OAuthTokens:
    """OAuth token set."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None  # Unix timestamp
    scopes: list[str] | None = None
    subscription_type: Optional[str] = None  # pro, max, team, enterprise

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        # 5 minute buffer
        return (self.expires_at - 300) < time.time()

    @property
    def is_subscriber(self) -> bool:
        """Check if token has inference scope (= subscription user)."""
        return self.scopes is not None and "user:inference" in self.scopes


@dataclass
class SubscriptionInfo:
    """User subscription details."""
    email: Optional[str] = None
    subscription_type: Optional[str] = None  # pro, max, team, enterprise
    rate_limit_tier: Optional[str] = None
    has_extra_usage: bool = False


class OAuthManager:
    """Manages OAuth tokens for Claude subscription auth."""

    def __init__(self):
        self._tokens: Optional[OAuthTokens] = None
        self._subscription: Optional[SubscriptionInfo] = None

    def load_tokens(self) -> Optional[OAuthTokens]:
        """Load OAuth tokens from env var or credentials file."""
        # 1. Check env var (highest priority)
        env_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        if env_token:
            self._tokens = OAuthTokens(access_token=env_token)
            logger.info("OAuth token loaded from CLAUDE_CODE_OAUTH_TOKEN env")
            return self._tokens

        # 2. Check credentials file
        for cred_path in CREDENTIALS_PATHS:
            if cred_path.exists():
                try:
                    data = json.loads(cred_path.read_text())
                    oauth_data = data.get("claudeAiOauth", data)
                    self._tokens = OAuthTokens(
                        access_token=oauth_data["accessToken"],
                        refresh_token=oauth_data.get("refreshToken"),
                        expires_at=oauth_data.get("expiresAt"),
                        scopes=oauth_data.get("scopes", []),
                        subscription_type=oauth_data.get("subscriptionType"),
                    )
                    logger.info("OAuth token loaded from %s", cred_path)
                    return self._tokens
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Failed to parse %s: %s", cred_path, e)

        return None

    async def refresh_if_needed(self) -> Optional[OAuthTokens]:
        """Refresh token if expired."""
        if self._tokens is None:
            self.load_tokens()
        if self._tokens is None:
            return None

        if not self._tokens.is_expired:
            return self._tokens

        if not self._tokens.refresh_token:
            logger.warning("Token expired but no refresh token available")
            return None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    TOKEN_ENDPOINT,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self._tokens.refresh_token,
                        "client_id": OAUTH_CLIENT_ID,
                        "scope": " ".join(CLAUDE_AI_SCOPES),
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                self._tokens.access_token = data["access_token"]
                if "refresh_token" in data:
                    self._tokens.refresh_token = data["refresh_token"]
                if "expires_in" in data:
                    self._tokens.expires_at = time.time() + data["expires_in"]
                if "scope" in data:
                    self._tokens.scopes = data["scope"].split()

                # Save refreshed tokens back to file
                self._save_tokens()
                logger.info("OAuth token refreshed successfully")
                return self._tokens

        except Exception as e:
            logger.warning("Token refresh failed: %s", e)
            return None

    async def get_subscription_info(self) -> Optional[SubscriptionInfo]:
        """Fetch user profile and subscription details."""
        if self._subscription:
            return self._subscription

        tokens = await self.refresh_if_needed()
        if not tokens:
            return None

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    PROFILE_ENDPOINT,
                    headers={"Authorization": f"Bearer {tokens.access_token}"},
                )
                resp.raise_for_status()
                data = resp.json()

                org = data.get("organization", {})
                account = data.get("account", {})

                org_type = org.get("organization_type", "")
                type_map = {
                    "claude_max": "max",
                    "claude_pro": "pro",
                    "claude_enterprise": "enterprise",
                    "claude_team": "team",
                }

                self._subscription = SubscriptionInfo(
                    email=account.get("email"),
                    subscription_type=type_map.get(org_type),
                    rate_limit_tier=org.get("rate_limit_tier"),
                    has_extra_usage=bool(org.get("has_extra_usage_enabled")),
                )
                return self._subscription

        except Exception as e:
            logger.warning("Failed to fetch subscription info: %s", e)
            return None

    def _save_tokens(self):
        """Save tokens back to credentials file."""
        if not self._tokens:
            return
        for cred_path in CREDENTIALS_PATHS:
            if cred_path.exists():
                try:
                    data = json.loads(cred_path.read_text())
                    data["claudeAiOauth"] = {
                        "accessToken": self._tokens.access_token,
                        "refreshToken": self._tokens.refresh_token,
                        "expiresAt": self._tokens.expires_at,
                        "scopes": self._tokens.scopes,
                        "subscriptionType": self._tokens.subscription_type,
                    }
                    cred_path.write_text(json.dumps(data, indent=2))
                    return
                except Exception as e:
                    logger.warning("Failed to save tokens to %s: %s", cred_path, e)

    @property
    def has_tokens(self) -> bool:
        return self._tokens is not None

    @property
    def is_subscriber(self) -> bool:
        return self._tokens is not None and self._tokens.is_subscriber


def get_auth_token() -> Optional[str]:
    """Get OAuth access token if available, else None."""
    mgr = OAuthManager()
    tokens = mgr.load_tokens()
    return tokens.access_token if tokens else None
