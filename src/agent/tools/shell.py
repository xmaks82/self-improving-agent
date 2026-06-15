"""Shell command execution tool with git safety."""

import asyncio
import logging
import re
import shlex
from pathlib import Path
from typing import Optional

from .base import BaseTool, ToolResult
from .bash_security import BashSecurityValidator
from .command_semantics import interpret_exit_code

logger = logging.getLogger(__name__)

# Dangerous git operations that can cause data loss
DANGEROUS_GIT_PATTERNS = [
    (r"git\s+push\s+.*--force", "force push can overwrite remote history"),
    (r"git\s+push\s+-f\b", "force push can overwrite remote history"),
    (r"git\s+reset\s+--hard", "hard reset discards all uncommitted changes"),
    (r"git\s+checkout\s+--\s", "discards uncommitted changes to files"),
    (r"git\s+checkout\s+\.\s*$", "discards all uncommitted changes"),
    (r"git\s+branch\s+-D\b", "force deletes branch even if unmerged"),
    (r"git\s+clean\s+-f", "permanently removes untracked files"),
    (r"git\s+stash\s+drop", "permanently deletes a stash entry"),
    (r"git\s+push\s+\S+\s+:", "deletes remote branch"),
    (r"git\s+rebase\s+.*--force", "force rebase rewrites history"),
]


class RunCommandTool(BaseTool):
    """Execute shell commands."""

    name = "run_command"
    description = "Execute a shell command and return its output."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The command to execute",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 30)",
                "default": 30,
            },
        },
        "required": ["command"],
    }

    # Commands that are always allowed
    SAFE_COMMANDS = {
        "ls", "cat", "head", "tail", "grep", "find", "wc",
        "echo", "pwd", "date", "whoami", "env", "which",
        "python", "python3", "pip", "pip3",
        "node", "npm", "npx",
        "git",
        "make", "cargo", "go",
    }

    # Commands that are never allowed
    DANGEROUS_COMMANDS = {
        "rm", "rmdir", "mv", "dd", "mkfs", "fdisk",
        "shutdown", "reboot", "halt", "poweroff",
        "chmod", "chown", "chgrp",
        "sudo", "su",
        "kill", "killall", "pkill",
        ">", ">>",  # Redirects (when at start)
    }

    def __init__(
        self,
        working_dir: Optional[Path] = None,
        allowed_commands: Optional[set[str]] = None,
        timeout: int = 30,
        sandbox_mode: bool = True,
    ):
        """
        Initialize shell tool.

        Args:
            working_dir: Default working directory
            allowed_commands: Additional allowed commands
            timeout: Default timeout in seconds
            sandbox_mode: If True, restrict to safe commands
        """
        self.working_dir = working_dir or Path.cwd()
        self.allowed_commands = (
            self.SAFE_COMMANDS | (allowed_commands or set())
        )
        self.default_timeout = timeout
        self.sandbox_mode = sandbox_mode
        self.security_validator = BashSecurityValidator(strict_mode=sandbox_mode)

    # Chars that shlex(punctuation_chars=True) tokenizes as operators.
    _PUNCT = set("|&;<>()")

    def _split_segments(self, command: str) -> list[list[str]]:
        """Split a command into sub-command token lists at shell operators
        (;, &&, ||, |, &), honoring quotes. Rejects redirection and subshells
        in sandbox mode (raises ValueError). Each segment's head is validated
        separately so a chained `rm` can't ride in behind an allowed `git`.
        """
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)  # raises ValueError on unbalanced quotes
        segments: list[list[str]] = [[]]
        for t in tokens:
            if t and all(ch in self._PUNCT for ch in t):  # an operator token
                if any(ch in "<>" for ch in t):
                    raise ValueError(f"redirection not allowed in sandbox: '{t}'")
                if "(" in t or ")" in t:
                    raise ValueError("subshell '()' not allowed in sandbox")
                segments.append([])  # ; && || | &  → new sub-command
            else:
                segments[-1].append(t)
        return [s for s in segments if s]

    def _is_command_allowed(self, command: str) -> tuple[bool, str]:
        """
        Check if command is allowed.

        Returns:
            (allowed, reason)
        """
        if not self.sandbox_mode:
            return True, ""

        try:
            segments = self._split_segments(command)
        except ValueError as e:
            return False, f"Command rejected: {e}"

        if not segments:
            return False, "Empty command"

        # Validate EVERY sub-command head (chaining can't smuggle a denied cmd).
        for seg in segments:
            base_cmd = Path(seg[0]).name
            if base_cmd in self.DANGEROUS_COMMANDS:
                return False, f"Command not allowed: {base_cmd}"
            if base_cmd not in self.allowed_commands:
                return False, f"Command not in allowed list: {base_cmd}"

        return True, ""

    def _check_dangerous_git(self, command: str) -> Optional[str]:
        """Check for dangerous git operations. Returns warning or None."""
        for pattern, description in DANGEROUS_GIT_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return f"WARNING: {description}. Command: {command}"
        return None

    async def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> ToolResult:
        """Execute shell command."""
        # Validate command
        allowed, reason = self._is_command_allowed(command)
        if not allowed:
            return ToolResult.fail(reason)

        # Git safety check (basic patterns)
        git_warning = self._check_dangerous_git(command)
        if git_warning:
            return ToolResult.fail(git_warning)

        # Enhanced security validation
        sec_allowed, sec_reason = self.security_validator.validate(command)
        if not sec_allowed:
            return ToolResult.fail(sec_reason)

        # Resolve working directory
        work_dir = Path(cwd) if cwd else self.working_dir
        if not work_dir.exists():
            return ToolResult.fail(f"Working directory not found: {work_dir}")

        # Set timeout
        cmd_timeout = timeout or self.default_timeout

        try:
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(work_dir),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=cmd_timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult.fail(
                    f"Command timed out after {cmd_timeout}s",
                    output="",
                    command=command,
                )

            # Decode output
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            # Combine output
            output = stdout_text
            if stderr_text:
                output += f"\n[stderr]\n{stderr_text}"

            # Use command semantics for exit code interpretation
            interp = interpret_exit_code(command, process.returncode, stdout_text, stderr_text)
            if not interp.is_error:
                note = interp.message or ""
                result_output = output.strip()
                if note:
                    result_output = f"{result_output}\n[Note: {note}]" if result_output else note
                return ToolResult.ok(
                    result_output,
                    command=command,
                    exit_code=process.returncode,
                )
            else:
                return ToolResult.fail(
                    interp.message or f"Command failed with exit code {process.returncode}",
                    output=output.strip(),
                    command=command,
                    exit_code=process.returncode,
                )

        except Exception as e:
            return ToolResult.fail(
                f"Error executing command: {e}",
                command=command,
            )
