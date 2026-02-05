"""Git tools."""

import asyncio
from pathlib import Path
from typing import Optional

from .base import BaseTool, ToolResult


class GitStatusTool(BaseTool):
    """Get git repository status."""

    name = "git_status"
    description = "Get the status of a git repository, showing modified, staged, and untracked files."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the git repository (default: current directory)",
            },
        },
        "required": [],
    }

    def __init__(self, default_path: Optional[Path] = None):
        self.default_path = default_path or Path.cwd()

    async def execute(self, path: Optional[str] = None, **kwargs) -> ToolResult:
        """Get git status."""
        repo_path = Path(path) if path else self.default_path

        if not (repo_path / ".git").exists():
            return ToolResult.fail(f"Not a git repository: {repo_path}")

        try:
            process = await asyncio.create_subprocess_exec(
                "git", "status", "--porcelain", "-b",
                cwd=str(repo_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return ToolResult.fail(
                    f"Git error: {stderr.decode()}"
                )

            output = stdout.decode().strip()

            # Parse output for summary
            lines = output.split("\n") if output else []
            branch = ""
            modified = 0
            staged = 0
            untracked = 0

            for line in lines:
                if line.startswith("##"):
                    branch = line[3:].split("...")[0]
                elif line.startswith(" M") or line.startswith("MM"):
                    modified += 1
                elif line.startswith("M "):
                    staged += 1
                elif line.startswith("??"):
                    untracked += 1
                elif line.startswith("A "):
                    staged += 1

            return ToolResult.ok(
                output if output else "Nothing to commit, working tree clean",
                branch=branch,
                modified=modified,
                staged=staged,
                untracked=untracked,
            )

        except Exception as e:
            return ToolResult.fail(f"Error running git status: {e}")


class GitDiffTool(BaseTool):
    """Get git diff."""

    name = "git_diff"
    description = "Show changes in the working directory or between commits."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the git repository",
            },
            "file": {
                "type": "string",
                "description": "Specific file to diff (optional)",
            },
            "staged": {
                "type": "boolean",
                "description": "Show staged changes (--cached)",
                "default": False,
            },
            "commit": {
                "type": "string",
                "description": "Compare with specific commit",
            },
        },
        "required": [],
    }

    def __init__(self, default_path: Optional[Path] = None):
        self.default_path = default_path or Path.cwd()

    async def execute(
        self,
        path: Optional[str] = None,
        file: Optional[str] = None,
        staged: bool = False,
        commit: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """Get git diff."""
        repo_path = Path(path) if path else self.default_path

        if not (repo_path / ".git").exists():
            return ToolResult.fail(f"Not a git repository: {repo_path}")

        try:
            cmd = ["git", "diff"]

            if staged:
                cmd.append("--cached")

            if commit:
                cmd.append(commit)

            if file:
                cmd.extend(["--", file])

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(repo_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return ToolResult.fail(f"Git error: {stderr.decode()}")

            output = stdout.decode().strip()

            if not output:
                return ToolResult.ok("No changes")

            # Count changes
            additions = output.count("\n+") - output.count("\n+++")
            deletions = output.count("\n-") - output.count("\n---")

            return ToolResult.ok(
                output,
                additions=additions,
                deletions=deletions,
            )

        except Exception as e:
            return ToolResult.fail(f"Error running git diff: {e}")


class GitCommitTool(BaseTool):
    """Create a git commit."""

    name = "git_commit"
    description = "Stage files and create a git commit."
    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Commit message",
            },
            "path": {
                "type": "string",
                "description": "Path to the git repository",
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Files to stage (default: all changed files)",
            },
            "all": {
                "type": "boolean",
                "description": "Stage all changes (-a flag)",
                "default": False,
            },
        },
        "required": ["message"],
    }

    def __init__(self, default_path: Optional[Path] = None):
        self.default_path = default_path or Path.cwd()

    async def execute(
        self,
        message: str,
        path: Optional[str] = None,
        files: Optional[list[str]] = None,
        all: bool = False,
        **kwargs,
    ) -> ToolResult:
        """Create git commit."""
        repo_path = Path(path) if path else self.default_path

        if not (repo_path / ".git").exists():
            return ToolResult.fail(f"Not a git repository: {repo_path}")

        try:
            # Stage files
            if files:
                for file in files:
                    process = await asyncio.create_subprocess_exec(
                        "git", "add", file,
                        cwd=str(repo_path),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await process.communicate()
            elif all:
                process = await asyncio.create_subprocess_exec(
                    "git", "add", "-A",
                    cwd=str(repo_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await process.communicate()

            # Create commit
            cmd = ["git", "commit", "-m", message]
            if all and not files:
                cmd.insert(2, "-a")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(repo_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error = stderr.decode() or stdout.decode()
                if "nothing to commit" in error.lower():
                    return ToolResult.fail("Nothing to commit")
                return ToolResult.fail(f"Git commit failed: {error}")

            output = stdout.decode().strip()

            # Extract commit hash
            commit_hash = ""
            for line in output.split("\n"):
                if line.startswith("["):
                    parts = line.split()
                    if len(parts) >= 2:
                        commit_hash = parts[1].rstrip("]")
                    break

            return ToolResult.ok(
                output,
                commit=commit_hash,
                message=message,
            )

        except Exception as e:
            return ToolResult.fail(f"Error creating commit: {e}")
