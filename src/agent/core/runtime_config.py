"""Runtime-mutable configuration layer."""

import json
import logging
from pathlib import Path
from typing import Any, Optional

import aiofiles

from ..config import config

logger = logging.getLogger(__name__)


class RuntimeConfig:
    """Runtime config that can be changed without restart."""

    MUTABLE_KEYS: dict[str, type] = {
        "model": str,
        "log_level": str,
        "feedback_confidence": float,
        "improvement_confidence": float,
        "sandbox_allow": str,  # comma-separated commands to add to allowlist
        "sandbox_block": str,  # comma-separated commands to add to blocklist
        "output_style": str,   # default/concise/explanatory/teaching
    }

    def __init__(self, persist_path: Optional[Path] = None):
        self._overrides: dict[str, Any] = {}
        self._persist_path = persist_path or config.paths.data / "runtime_config.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)

    async def load(self):
        """Load persisted overrides."""
        if self._persist_path.exists():
            try:
                async with aiofiles.open(self._persist_path, "r") as f:
                    self._overrides = json.loads(await f.read())
                logger.info("Loaded %d runtime config overrides", len(self._overrides))
            except Exception as e:
                logger.warning("Failed to load runtime config: %s", e)

    async def save(self):
        """Persist overrides to disk."""
        try:
            async with aiofiles.open(self._persist_path, "w") as f:
                await f.write(json.dumps(self._overrides, indent=2))
        except Exception as e:
            logger.warning("Failed to save runtime config: %s", e)

    def get(self, key: str) -> Any:
        """Get a config value (override > static config)."""
        if key in self._overrides:
            return self._overrides[key]
        return self._get_static(key)

    def _get_static(self, key: str) -> Any:
        """Get value from static config."""
        mapping = {
            "model": lambda: config.models.default,
            "log_level": lambda: config.log_level,
            "feedback_confidence": lambda: config.thresholds.feedback_confidence,
            "improvement_confidence": lambda: config.thresholds.improvement_confidence,
            "sandbox_allow": lambda: "",
            "sandbox_block": lambda: "",
            "output_style": lambda: "default",
        }
        getter = mapping.get(key)
        return getter() if getter else None

    async def set(self, key: str, value: str) -> tuple[bool, str]:
        """Set a config value. Returns (success, message)."""
        if key not in self.MUTABLE_KEYS:
            return False, f"Unknown key: {key}. Available: {', '.join(self.MUTABLE_KEYS)}"

        expected_type = self.MUTABLE_KEYS[key]
        try:
            typed_value = expected_type(value)
        except (ValueError, TypeError):
            return False, f"Invalid value for {key}: expected {expected_type.__name__}"

        # Apply to global config
        self._apply(key, typed_value)
        self._overrides[key] = typed_value
        await self.save()
        return True, f"{key} = {typed_value}"

    async def reset(self, key: str) -> tuple[bool, str]:
        """Reset a key to its default value."""
        if key not in self.MUTABLE_KEYS:
            return False, f"Unknown key: {key}"
        if key in self._overrides:
            del self._overrides[key]
            await self.save()
            # Re-apply static value
            static_val = self._get_static(key)
            self._apply(key, static_val)
            return True, f"{key} reset to default ({static_val})"
        return True, f"{key} already at default"

    def _apply(self, key: str, value: Any):
        """Apply a config change to the global config object."""
        if key == "model":
            config.models.default = value
        elif key == "log_level":
            config.log_level = value
            logging.getLogger().setLevel(getattr(logging, str(value).upper(), logging.INFO))
        elif key == "feedback_confidence":
            config.thresholds.feedback_confidence = value
        elif key == "improvement_confidence":
            config.thresholds.improvement_confidence = value
        elif key == "output_style":
            from .output_styles import set_style
            set_style(value)

    def list_all(self) -> dict[str, dict[str, Any]]:
        """Return all config values with override status."""
        result = {}
        for key in self.MUTABLE_KEYS:
            static_val = self._get_static(key)
            override_val = self._overrides.get(key)
            result[key] = {
                "value": override_val if override_val is not None else static_val,
                "default": static_val,
                "overridden": key in self._overrides,
            }
        return result
