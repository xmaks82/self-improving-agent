"""Search tools for finding files and content."""

import asyncio
import fnmatch
from pathlib import Path
from typing import Optional

from .base import BaseTool, ToolResult


class SearchFilesTool(BaseTool):
    """Search for files by name pattern."""

    name = "search_files"
    description = "Search for files matching a pattern in a directory."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "File pattern to search for (e.g., '*.py', 'test_*.py')",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in",
            },
            "recursive": {
                "type": "boolean",
                "description": "Search recursively in subdirectories",
                "default": True,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 100,
            },
        },
        "required": ["pattern"],
    }

    def __init__(self, default_path: Optional[Path] = None):
        self.default_path = default_path or Path.cwd()

    async def execute(
        self,
        pattern: str,
        path: Optional[str] = None,
        recursive: bool = True,
        max_results: int = 100,
        **kwargs,
    ) -> ToolResult:
        """Search for files."""
        search_path = Path(path) if path else self.default_path

        if not search_path.exists():
            return ToolResult.fail(f"Path not found: {search_path}")

        if not search_path.is_dir():
            return ToolResult.fail(f"Not a directory: {search_path}")

        try:
            matches = []

            if recursive:
                # Use rglob for recursive search
                for item in search_path.rglob(pattern):
                    if item.is_file():
                        matches.append(str(item.relative_to(search_path)))
                        if len(matches) >= max_results:
                            break
            else:
                # Use glob for non-recursive search
                for item in search_path.glob(pattern):
                    if item.is_file():
                        matches.append(item.name)
                        if len(matches) >= max_results:
                            break

            if not matches:
                return ToolResult.ok(
                    f"No files found matching '{pattern}'",
                    count=0,
                )

            output = "\n".join(sorted(matches))
            truncated = len(matches) >= max_results

            return ToolResult.ok(
                output,
                count=len(matches),
                truncated=truncated,
            )

        except Exception as e:
            return ToolResult.fail(f"Error searching files: {e}")


class GrepTool(BaseTool):
    """Search for content in files."""

    name = "grep"
    description = "Search for a pattern in file contents."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Text or regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "File or directory to search in",
            },
            "file_pattern": {
                "type": "string",
                "description": "Only search files matching this pattern (e.g., '*.py')",
            },
            "recursive": {
                "type": "boolean",
                "description": "Search recursively",
                "default": True,
            },
            "case_insensitive": {
                "type": "boolean",
                "description": "Case insensitive search",
                "default": False,
            },
            "context_lines": {
                "type": "integer",
                "description": "Number of context lines to show",
                "default": 0,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of matches to return",
                "default": 50,
            },
        },
        "required": ["pattern"],
    }

    def __init__(self, default_path: Optional[Path] = None):
        self.default_path = default_path or Path.cwd()

    async def execute(
        self,
        pattern: str,
        path: Optional[str] = None,
        file_pattern: Optional[str] = None,
        recursive: bool = True,
        case_insensitive: bool = False,
        context_lines: int = 0,
        max_results: int = 50,
        **kwargs,
    ) -> ToolResult:
        """Search content in files."""
        search_path = Path(path) if path else self.default_path

        if not search_path.exists():
            return ToolResult.fail(f"Path not found: {search_path}")

        try:
            # Build grep command
            cmd = ["grep", "-n"]  # -n for line numbers

            if recursive and search_path.is_dir():
                cmd.append("-r")

            if case_insensitive:
                cmd.append("-i")

            if context_lines > 0:
                cmd.extend(["-C", str(context_lines)])

            # Add file pattern if specified
            if file_pattern and search_path.is_dir():
                cmd.extend(["--include", file_pattern])

            cmd.append(pattern)
            cmd.append(str(search_path))

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            output = stdout.decode("utf-8", errors="replace")

            if process.returncode == 1:
                # No matches found
                return ToolResult.ok(
                    f"No matches found for '{pattern}'",
                    count=0,
                )

            if process.returncode > 1:
                # Error
                return ToolResult.fail(
                    f"Grep error: {stderr.decode()}"
                )

            # Process results
            lines = output.strip().split("\n")
            if len(lines) > max_results:
                lines = lines[:max_results]
                truncated = True
            else:
                truncated = False

            result = "\n".join(lines)

            return ToolResult.ok(
                result,
                count=len(lines),
                truncated=truncated,
            )

        except FileNotFoundError:
            # grep not available, fall back to Python implementation
            return await self._python_grep(
                pattern, search_path, file_pattern, recursive,
                case_insensitive, context_lines, max_results
            )
        except Exception as e:
            return ToolResult.fail(f"Error searching: {e}")

    async def _python_grep(
        self,
        pattern: str,
        search_path: Path,
        file_pattern: Optional[str],
        recursive: bool,
        case_insensitive: bool,
        context_lines: int,
        max_results: int,
    ) -> ToolResult:
        """Python fallback for grep."""
        import re

        flags = re.IGNORECASE if case_insensitive else 0

        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult.fail(f"Invalid regex: {e}")

        matches = []

        # Get files to search
        if search_path.is_file():
            files = [search_path]
        elif recursive:
            if file_pattern:
                files = list(search_path.rglob(file_pattern))
            else:
                files = [f for f in search_path.rglob("*") if f.is_file()]
        else:
            if file_pattern:
                files = list(search_path.glob(file_pattern))
            else:
                files = [f for f in search_path.iterdir() if f.is_file()]

        for file_path in files:
            if len(matches) >= max_results:
                break

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                lines = content.split("\n")

                for i, line in enumerate(lines, 1):
                    if regex.search(line):
                        rel_path = file_path.relative_to(search_path) if search_path.is_dir() else file_path.name
                        matches.append(f"{rel_path}:{i}:{line}")

                        if len(matches) >= max_results:
                            break

            except (PermissionError, IsADirectoryError):
                continue

        if not matches:
            return ToolResult.ok(
                f"No matches found for '{pattern}'",
                count=0,
            )

        return ToolResult.ok(
            "\n".join(matches),
            count=len(matches),
            truncated=len(matches) >= max_results,
        )
