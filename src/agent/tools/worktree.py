"""Git worktree isolation tools."""

import asyncio
import os
import uuid
from pathlib import Path
from typing import Optional

from .base import BaseTool, ToolResult


class EnterWorktreeTool(BaseTool):
    """Create an isolated git worktree and switch into it."""

    name = "enter_worktree"
    description = "Creates an isolated git worktree on a new branch."
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Worktree name (alphanumeric/dashes). Auto-generated if empty.",
            },
        },
        "required": [],
    }

    def __init__(self):
        self._original_cwd: Optional[str] = None
        self._worktree_path: Optional[str] = None
        self._branch: Optional[str] = None

    async def execute(self, name: str = "", **kwargs) -> ToolResult:
        if self._worktree_path:
            return ToolResult.fail(f"Already in worktree: {self._worktree_path}")

        cwd = os.getcwd()

        # Verify git repo
        proc = await asyncio.create_subprocess_exec(
            "git", "rev-parse", "--git-dir",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            return ToolResult.fail("Not in a git repository.")

        slug = name.strip() or f"wt-{uuid.uuid4().hex[:8]}"
        branch_name = f"worktree/{slug}"
        wt_dir = Path(cwd) / ".agent" / "worktrees" / slug
        wt_dir.parent.mkdir(parents=True, exist_ok=True)

        proc = await asyncio.create_subprocess_exec(
            "git", "worktree", "add", "-b", branch_name, str(wt_dir),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            return ToolResult.fail(f"Failed: {stderr.decode().strip()}")

        self._original_cwd = cwd
        self._worktree_path = str(wt_dir)
        self._branch = branch_name
        os.chdir(self._worktree_path)

        return ToolResult.ok(
            f"Worktree created at {self._worktree_path} on branch {branch_name}",
            worktree_path=self._worktree_path, branch=branch_name,
        )


class ExitWorktreeTool(BaseTool):
    """Exit worktree and return to original directory."""

    name = "exit_worktree"
    description = "Exits a worktree session, optionally removing it."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string", "enum": ["keep", "remove"],
                "description": "'keep' preserves worktree; 'remove' deletes it.",
            },
            "discard_changes": {
                "type": "boolean",
                "description": "Force remove even with uncommitted changes.",
            },
        },
        "required": ["action"],
    }

    def __init__(self, enter_tool: EnterWorktreeTool):
        self._enter = enter_tool

    async def execute(self, action: str, discard_changes: bool = False, **kwargs) -> ToolResult:
        if not self._enter._worktree_path:
            return ToolResult.fail("Not in a worktree session.")

        original = self._enter._original_cwd
        wt_path = self._enter._worktree_path
        os.chdir(original)

        if action == "remove":
            args = ["git", "worktree", "remove", wt_path]
            if discard_changes:
                args.append("--force")
            proc = await asyncio.create_subprocess_exec(
                *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                cwd=original)
            await proc.communicate()

        self._enter._original_cwd = None
        self._enter._worktree_path = None
        self._enter._branch = None

        verb = "removed" if action == "remove" else "kept"
        return ToolResult.ok(f"Exited worktree ({verb}). Back in {original}.")
