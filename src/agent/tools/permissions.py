"""Centralized tool permission system."""

import re
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    AUTO_APPROVE = "auto_approve"
    CONFIRM = "confirm"
    ALWAYS_DENY = "always_deny"


# Default tool permission mapping
DEFAULT_PERMISSIONS: dict[str, PermissionLevel] = {
    # Auto-approve: read-only operations
    "read_file": PermissionLevel.AUTO_APPROVE,
    "list_directory": PermissionLevel.AUTO_APPROVE,
    "search_files": PermissionLevel.AUTO_APPROVE,
    "grep": PermissionLevel.AUTO_APPROVE,
    "git_status": PermissionLevel.AUTO_APPROVE,
    "git_diff": PermissionLevel.AUTO_APPROVE,
    "web_search": PermissionLevel.AUTO_APPROVE,
    "quick_search": PermissionLevel.AUTO_APPROVE,
    "fetch_url": PermissionLevel.AUTO_APPROVE,
    "read_article": PermissionLevel.AUTO_APPROVE,
    # Confirm: write/execute operations
    "write_file": PermissionLevel.CONFIRM,
    "run_command": PermissionLevel.CONFIRM,
    "git_commit": PermissionLevel.CONFIRM,
}

# Dangerous git patterns that require high-risk confirmation
DANGEROUS_GIT_PATTERNS = [
    (r"git\s+push\s+.*--force", "force push"),
    (r"git\s+push\s+-f\b", "force push"),
    (r"git\s+reset\s+--hard", "hard reset"),
    (r"git\s+checkout\s+--\s", "discard changes"),
    (r"git\s+checkout\s+\.\s*$", "discard all changes"),
    (r"git\s+branch\s+-D\b", "force delete branch"),
    (r"git\s+clean\s+-f", "force clean"),
    (r"git\s+stash\s+drop", "drop stash"),
    (r"git\s+push\s+\S+\s+:", "delete remote branch"),
    (r"git\s+rebase\s+.*--force", "force rebase"),
]


@dataclass
class PermissionManager:
    """Centralized tool permission management."""

    _permissions: dict[str, PermissionLevel] = field(
        default_factory=lambda: dict(DEFAULT_PERMISSIONS)
    )
    _blocklist: set[str] = field(default_factory=set)
    _auto_approve_all: bool = False

    def get_permission(self, tool_name: str) -> PermissionLevel:
        """Get permission level for a tool."""
        if tool_name in self._blocklist:
            return PermissionLevel.ALWAYS_DENY
        return self._permissions.get(tool_name, PermissionLevel.CONFIRM)

    def set_permission(self, tool_name: str, level: PermissionLevel):
        """Set permission level for a tool."""
        self._permissions[tool_name] = level

    def block(self, tool_name: str):
        """Block a tool entirely."""
        self._blocklist.add(tool_name)

    def unblock(self, tool_name: str):
        """Remove a tool from the blocklist."""
        self._blocklist.discard(tool_name)

    def check_permission(
        self,
        tool_name: str,
        **kwargs,
    ) -> tuple[bool, str]:
        """
        Check if a tool call is allowed.

        Returns:
            (allowed, reason/warning). If not allowed, reason explains why.
            If allowed but risky, reason contains a warning message.
        """
        level = self.get_permission(tool_name)

        if level == PermissionLevel.ALWAYS_DENY:
            return False, f"Tool '{tool_name}' is blocked"

        if self._auto_approve_all:
            return True, ""

        if level == PermissionLevel.AUTO_APPROVE:
            return True, ""

        # CONFIRM level — check for dangerous patterns
        if tool_name == "run_command":
            command = kwargs.get("command", "")
            danger = self._detect_dangerous_git(command)
            if danger:
                return False, f"DANGEROUS: {danger}. Use with extreme caution."

        # CONFIRM level passes through (confirmation handled by caller/CLI)
        return True, ""

    def _detect_dangerous_git(self, command: str) -> Optional[str]:
        """Detect dangerous git operations. Returns description or None."""
        for pattern, description in DANGEROUS_GIT_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return f"{description} (matches: {pattern})"
        return None
