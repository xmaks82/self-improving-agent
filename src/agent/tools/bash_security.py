"""Enhanced Bash security validator with multi-layer validation.

Checks: command substitution, redirects, dangerous variables,
control characters, Unicode whitespace, git safety.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Command substitution patterns that could execute arbitrary code
COMMAND_SUBSTITUTION_PATTERNS = [
    (re.compile(r'\$\([^)]*\)'), "command substitution $()"),
    (re.compile(r'`[^`]*`'), "backtick command substitution"),
    (re.compile(r'\$\{[^}]*\}'), "variable expansion ${}"),
    (re.compile(r'<\([^)]*\)'), "process substitution <()"),
    (re.compile(r'>\([^)]*\)'), "process substitution >()"),
]

# Dangerous variable assignments
DANGEROUS_VARIABLE_PATTERNS = [
    (re.compile(r'\bIFS\s*='), "IFS manipulation can alter command parsing"),
    (re.compile(r'\bPATH\s*='), "PATH manipulation can redirect command execution"),
    (re.compile(r'\bLD_PRELOAD\s*='), "LD_PRELOAD can inject shared libraries"),
    (re.compile(r'\bLD_LIBRARY_PATH\s*='), "LD_LIBRARY_PATH manipulation"),
    (re.compile(r'\bPYTHONPATH\s*='), "PYTHONPATH manipulation"),
    (re.compile(r'\bNODE_PATH\s*='), "NODE_PATH manipulation"),
]

# Dangerous redirect patterns
REDIRECT_PATTERNS = [
    (re.compile(r'>\s*/etc/'), "redirect to /etc/"),
    (re.compile(r'>\s*/dev/sd'), "redirect to block device"),
    (re.compile(r'>\s*/proc/'), "redirect to /proc/"),
    (re.compile(r'>\s*/sys/'), "redirect to /sys/"),
]

# Enhanced git safety patterns (extends shell.py DANGEROUS_GIT_PATTERNS)
GIT_SAFETY_PATTERNS = [
    (re.compile(r'git\s+push\s+.*--force.*\b(main|master)\b', re.I), "force push to main/master"),
    (re.compile(r'git\s+commit\s+.*--amend', re.I), "amend commit (creates NEW commits instead)"),
    (re.compile(r'git\s+add\s+(-A|\.)\s*$', re.I), "git add all (stage specific files instead)"),
    (re.compile(r'git\s+.*--no-verify', re.I), "skipping git hooks"),
]

# Control characters that could be used for injection
CONTROL_CHAR_PATTERN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

# Unicode whitespace that could hide malicious content
UNICODE_WHITESPACE = re.compile(r'[\u200b\u200c\u200d\u2060\ufeff\u00a0\u2000-\u200a]')


class BashSecurityValidator:
    """Multi-layer bash command security validator."""

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def validate(self, command: str) -> tuple[bool, Optional[str]]:
        """
        Run all security checks on a command.

        Returns:
            (allowed, reason). If not allowed, reason explains why.
        """
        checks = [
            self._check_control_characters,
            self._check_unicode_whitespace,
            self._check_dangerous_variables,
            self._check_dangerous_redirects,
            self._check_git_safety,
        ]

        # Command substitution check only in strict mode
        # (some legitimate use cases exist)
        if self.strict_mode:
            checks.insert(0, self._check_command_substitution)

        for check in checks:
            allowed, reason = check(command)
            if not allowed:
                return False, reason

        return True, None

    def _check_command_substitution(self, command: str) -> tuple[bool, Optional[str]]:
        """Detect command substitution patterns."""
        for pattern, description in COMMAND_SUBSTITUTION_PATTERNS:
            if pattern.search(command):
                return False, f"Security: {description} detected in command"
        return True, None

    def _check_dangerous_variables(self, command: str) -> tuple[bool, Optional[str]]:
        """Detect dangerous variable assignments."""
        for pattern, description in DANGEROUS_VARIABLE_PATTERNS:
            if pattern.search(command):
                return False, f"Security: {description}"
        return True, None

    def _check_dangerous_redirects(self, command: str) -> tuple[bool, Optional[str]]:
        """Detect dangerous output redirects."""
        for pattern, description in REDIRECT_PATTERNS:
            if pattern.search(command):
                return False, f"Security: {description}"
        return True, None

    def _check_git_safety(self, command: str) -> tuple[bool, Optional[str]]:
        """Detect dangerous git operations."""
        for pattern, description in GIT_SAFETY_PATTERNS:
            if pattern.search(command):
                return False, f"Git safety: {description}"
        return True, None

    def _check_control_characters(self, command: str) -> tuple[bool, Optional[str]]:
        """Detect control characters that could be used for injection."""
        if CONTROL_CHAR_PATTERN.search(command):
            return False, "Security: control characters detected in command"
        return True, None

    def _check_unicode_whitespace(self, command: str) -> tuple[bool, Optional[str]]:
        """Detect Unicode whitespace that could hide malicious content."""
        if UNICODE_WHITESPACE.search(command):
            return False, "Security: suspicious Unicode whitespace detected"
        return True, None
