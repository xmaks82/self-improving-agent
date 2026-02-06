"""Shell command execution tool."""

import asyncio
import logging
import shlex
from pathlib import Path
from typing import Optional

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


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

    def _is_command_allowed(self, command: str) -> tuple[bool, str]:
        """
        Check if command is allowed.

        Returns:
            (allowed, reason)
        """
        if not self.sandbox_mode:
            return True, ""

        # Parse command
        try:
            parts = shlex.split(command)
        except ValueError:
            return False, "Invalid command syntax"

        if not parts:
            return False, "Empty command"

        # Get base command (handle paths like /usr/bin/python)
        base_cmd = Path(parts[0]).name

        # Check dangerous commands
        if base_cmd in self.DANGEROUS_COMMANDS:
            return False, f"Command not allowed: {base_cmd}"

        # Check if command is in allowed list
        if base_cmd not in self.allowed_commands:
            return False, f"Command not in allowed list: {base_cmd}"

        # Check for dangerous patterns in arguments
        for part in parts[1:]:
            if part.startswith(">") or part in ["|", "&&", "||", ";"]:
                logger.warning("Shell operator detected in command: %s (operator: %s)", command, part)

        return True, ""

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

            if process.returncode == 0:
                return ToolResult.ok(
                    output.strip(),
                    command=command,
                    exit_code=process.returncode,
                )
            else:
                return ToolResult.fail(
                    f"Command failed with exit code {process.returncode}",
                    output=output.strip(),
                    command=command,
                    exit_code=process.returncode,
                )

        except Exception as e:
            return ToolResult.fail(
                f"Error executing command: {e}",
                command=command,
            )
