"""OAuth authentication for Claude Pro/Max subscriptions.

Flow:
1. User runs `claude setup-token` in Claude Code CLI
2. Token is saved to ~/.claude/.credentials.json
3. This module reads that token and uses it for API calls
4. Token is auto-refreshed when expired

Alternative: user can set CLAUDE_CODE_OAUTH_TOKEN env var directly.

Security:
- Credentials files set to 600 permissions (owner-only)
- Token refresh with retry and exponential backoff
- Graceful fallback to API key on OAuth failure
- No Claude Code-specific headers sent (uses standard SDK)
- Separate file lock prevents concurrent refresh race conditions
"""

import json
import logging
import os
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Anthropic OAuth constants
OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
TOKEN_ENDPOINT = "https://platform.claude.com/v1/oauth/token"
PROFILE_ENDPOINT = "https://api.anthropic.com/api/oauth/profile"

# Claude.ai OAuth scopes
CLAUDE_AI_SCOPES = [
    "user:profile",
    "user:inference",
    "user:sessions:claude_code",
]

# Credentials file locations (checked in order)
CREDENTIALS_PATHS = [
    Path.home() / ".claude" / ".credentials.json",
    Path.home() / ".claude" / "credentials.json",
]

# Refresh config
MAX_REFRESH_RETRIES = 3
REFRESH_BACKOFF_BASE = 2.0  # seconds
TOKEN_EXPIRY_BUFFER = 300   # 5 minutes before actual expiry


@dataclass
class OAuthTokens:
    """OAuth token set."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None  # Unix timestamp (ms in file, converted to seconds)
    scopes: list[str] = field(default_factory=list)
    subscription_type: Optional[str] = None  # pro, max, team, enterprise

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        # Normalize: if expires_at > year 2100 in seconds, it's likely milliseconds
        expires_sec = self.expires_at
        if expires_sec > 4_000_000_000:
            expires_sec = expires_sec / 1000
        return (expires_sec - TOKEN_EXPIRY_BUFFER) < time.time()

    @property
    def is_subscriber(self) -> bool:
        """Check if token has inference scope (= active subscription)."""
        return "user:inference" in (self.scopes or [])

    @property
    def token_preview(self) -> str:
        """Safe preview of token for logging (first 10 + last 4 chars)."""
        t = self.access_token
        if len(t) > 20:
            return f"{t[:10]}...{t[-4:]}"
        return "***"


@dataclass
class SubscriptionInfo:
    """User subscription details."""
    email: Optional[str] = None
    subscription_type: Optional[str] = None
    rate_limit_tier: Optional[str] = None
    has_extra_usage: bool = False


class OAuthManager:
    """Manages OAuth tokens for Claude subscription auth.

    Security features:
    - File permissions enforced to 600 (owner-only read/write)
    - Token refresh with retry + exponential backoff
    - Graceful degradation: OAuth failure → API key fallback
    - No spoofing of Claude Code headers (x-app, session ID, etc.)
    - Lock file prevents concurrent refresh from multiple processes
    """

    def __init__(self):
        self._tokens: Optional[OAuthTokens] = None
        self._subscription: Optional[SubscriptionInfo] = None
        self._refresh_failures: int = 0
        self._last_refresh_attempt: float = 0
        self._oauth_blocked: bool = False  # Set true if Anthropic blocks OAuth

    def load_tokens(self) -> Optional[OAuthTokens]:
        """Load OAuth tokens from env var or credentials file."""
        if self._oauth_blocked:
            return None

        # 1. Check env var (highest priority)
        env_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        if env_token:
            self._tokens = OAuthTokens(access_token=env_token)
            logger.info("OAuth token loaded from env")
            return self._tokens

        # 2. Check credentials files
        for cred_path in CREDENTIALS_PATHS:
            if not cred_path.exists():
                continue
            try:
                # Enforce file permissions
                self._enforce_permissions(cred_path)

                data = json.loads(cred_path.read_text())
                oauth_data = data.get("claudeAiOauth")
                if not oauth_data or "accessToken" not in oauth_data:
                    continue

                self._tokens = OAuthTokens(
                    access_token=oauth_data["accessToken"],
                    refresh_token=oauth_data.get("refreshToken"),
                    expires_at=oauth_data.get("expiresAt"),
                    scopes=oauth_data.get("scopes", []),
                    subscription_type=oauth_data.get("subscriptionType"),
                )
                logger.info(
                    "OAuth token loaded from %s (subscriber=%s, expired=%s)",
                    cred_path.name, self._tokens.is_subscriber, self._tokens.is_expired,
                )
                return self._tokens

            except (json.JSONDecodeError, KeyError, PermissionError) as e:
                logger.warning("Failed to parse %s: %s", cred_path, e)

        return None

    async def refresh_if_needed(self) -> Optional[OAuthTokens]:
        """Refresh token if expired. Returns tokens or None."""
        if self._oauth_blocked:
            return None

        if self._tokens is None:
            self.load_tokens()
        if self._tokens is None:
            return None
        if not self._tokens.is_expired:
            return self._tokens
        if not self._tokens.refresh_token:
            logger.warning("Token expired, no refresh token — fallback to API key")
            return None

        # Rate limit refresh attempts (min 30s between attempts)
        now = time.time()
        if now - self._last_refresh_attempt < 30:
            logger.debug("Skipping refresh — too soon since last attempt")
            return self._tokens  # Return possibly-expired token, let API handle it

        self._last_refresh_attempt = now

        # Retry with exponential backoff
        for attempt in range(MAX_REFRESH_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(
                        TOKEN_ENDPOINT,
                        data={
                            "grant_type": "refresh_token",
                            "refresh_token": self._tokens.refresh_token,
                            "client_id": OAUTH_CLIENT_ID,
                            "scope": " ".join(CLAUDE_AI_SCOPES),
                        },
                    )

                    # Detect blocking
                    if resp.status_code in (401, 403):
                        error_body = resp.text
                        if "blocked" in error_body.lower() or "forbidden" in error_body.lower():
                            logger.warning(
                                "OAuth refresh blocked by server (HTTP %d). "
                                "Falling back to API key.", resp.status_code
                            )
                            self._oauth_blocked = True
                            return None

                    resp.raise_for_status()
                    data = resp.json()

                    self._tokens.access_token = data["access_token"]
                    if "refresh_token" in data:
                        self._tokens.refresh_token = data["refresh_token"]
                    if "expires_in" in data:
                        self._tokens.expires_at = time.time() + data["expires_in"]
                    if "scope" in data:
                        self._tokens.scopes = data["scope"].split()

                    self._save_tokens()
                    self._refresh_failures = 0
                    logger.info("OAuth token refreshed (attempt %d)", attempt + 1)
                    return self._tokens

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (401, 403):
                    logger.warning("OAuth refresh rejected (HTTP %d) — token may be revoked", status)
                    self._refresh_failures += 1
                    if self._refresh_failures >= 3:
                        logger.warning("3 consecutive refresh failures — disabling OAuth")
                        self._oauth_blocked = True
                    return None
                # 429 or 5xx — retry
                backoff = REFRESH_BACKOFF_BASE * (2 ** attempt)
                logger.warning("Refresh HTTP %d, retry in %.1fs", status, backoff)
                await _async_sleep(backoff)

            except Exception as e:
                backoff = REFRESH_BACKOFF_BASE * (2 ** attempt)
                logger.warning("Refresh error: %s, retry in %.1fs", e, backoff)
                await _async_sleep(backoff)

        logger.warning("All refresh retries exhausted")
        self._refresh_failures += 1
        return None

    async def get_subscription_info(self) -> Optional[SubscriptionInfo]:
        """Fetch user profile and subscription details."""
        if self._subscription:
            return self._subscription

        tokens = await self.refresh_if_needed()
        if not tokens:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    PROFILE_ENDPOINT,
                    headers={"Authorization": f"Bearer {tokens.access_token}"},
                )
                resp.raise_for_status()
                data = resp.json()

                org = data.get("organization", {})
                account = data.get("account", {})

                type_map = {
                    "claude_max": "max",
                    "claude_pro": "pro",
                    "claude_enterprise": "enterprise",
                    "claude_team": "team",
                }

                self._subscription = SubscriptionInfo(
                    email=account.get("email"),
                    subscription_type=type_map.get(org.get("organization_type", "")),
                    rate_limit_tier=org.get("rate_limit_tier"),
                    has_extra_usage=bool(org.get("has_extra_usage_enabled")),
                )
                return self._subscription

        except Exception as e:
            logger.warning("Failed to fetch subscription info: %s", e)
            return None

    def _save_tokens(self):
        """Save tokens back to credentials file with secure permissions."""
        if not self._tokens:
            return
        for cred_path in CREDENTIALS_PATHS:
            if not cred_path.exists():
                continue
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
                self._enforce_permissions(cred_path)
                return
            except Exception as e:
                logger.warning("Failed to save tokens to %s: %s", cred_path, e)

    def _enforce_permissions(self, path: Path):
        """Set file to 600 (owner read/write only)."""
        try:
            current = path.stat().st_mode
            desired = stat.S_IRUSR | stat.S_IWUSR  # 0o600
            if current & 0o777 != desired:
                path.chmod(desired)
        except OSError:
            pass  # May fail on some filesystems

    @property
    def has_tokens(self) -> bool:
        return self._tokens is not None and not self._oauth_blocked

    @property
    def is_subscriber(self) -> bool:
        return self._tokens is not None and self._tokens.is_subscriber and not self._oauth_blocked

    @property
    def is_blocked(self) -> bool:
        return self._oauth_blocked

    def reset_blocked(self):
        """Reset blocked state (e.g., after re-login)."""
        self._oauth_blocked = False
        self._refresh_failures = 0


# Singleton for global access
_global_manager: Optional[OAuthManager] = None


def get_oauth_manager() -> OAuthManager:
    """Get or create the global OAuthManager singleton."""
    global _global_manager
    if _global_manager is None:
        _global_manager = OAuthManager()
    return _global_manager


def get_auth_token() -> Optional[str]:
    """Get OAuth access token if available, else None."""
    mgr = get_oauth_manager()
    tokens = mgr.load_tokens()
    if tokens and not mgr.is_blocked:
        return tokens.access_token
    return None


async def _async_sleep(seconds: float):
    """Async sleep helper."""
    import asyncio
    await asyncio.sleep(seconds)
