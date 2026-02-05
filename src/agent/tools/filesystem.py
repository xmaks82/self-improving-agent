"""Filesystem tools."""

import os
from pathlib import Path
from typing import Optional
import aiofiles
import aiofiles.os

from .base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """Read contents of a file."""

    name = "read_file"
    description = "Read the contents of a file at the specified path."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read",
            },
            "encoding": {
                "type": "string",
                "description": "File encoding (default: utf-8)",
                "default": "utf-8",
            },
        },
        "required": ["path"],
    }

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize with optional base path for sandboxing.

        Args:
            base_path: If set, all paths are relative to this directory
        """
        self.base_path = base_path

    def _resolve_path(self, path: str) -> Path:
        """Resolve path, applying sandboxing if configured."""
        p = Path(path)
        if self.base_path:
            # Sandbox: ensure path is within base_path
            resolved = (self.base_path / p).resolve()
            if not str(resolved).startswith(str(self.base_path.resolve())):
                raise PermissionError(f"Access denied: {path}")
            return resolved
        return p.resolve()

    async def execute(self, path: str, encoding: str = "utf-8", **kwargs) -> ToolResult:
        """Read file contents."""
        try:
            resolved = self._resolve_path(path)

            if not resolved.exists():
                return ToolResult.fail(f"File not found: {path}")

            if not resolved.is_file():
                return ToolResult.fail(f"Not a file: {path}")

            async with aiofiles.open(resolved, "r", encoding=encoding) as f:
                content = await f.read()

            return ToolResult.ok(
                content,
                path=str(resolved),
                size=len(content),
                lines=content.count("\n") + 1,
            )

        except PermissionError as e:
            return ToolResult.fail(str(e))
        except UnicodeDecodeError:
            return ToolResult.fail(f"Cannot decode file with encoding {encoding}")
        except Exception as e:
            return ToolResult.fail(f"Error reading file: {e}")


class WriteFileTool(BaseTool):
    """Write contents to a file."""

    name = "write_file"
    description = "Write content to a file at the specified path. Creates the file if it doesn't exist."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
            "encoding": {
                "type": "string",
                "description": "File encoding (default: utf-8)",
                "default": "utf-8",
            },
            "create_dirs": {
                "type": "boolean",
                "description": "Create parent directories if they don't exist",
                "default": True,
            },
        },
        "required": ["path", "content"],
    }

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path

    def _resolve_path(self, path: str) -> Path:
        """Resolve path with sandboxing."""
        p = Path(path)
        if self.base_path:
            resolved = (self.base_path / p).resolve()
            if not str(resolved).startswith(str(self.base_path.resolve())):
                raise PermissionError(f"Access denied: {path}")
            return resolved
        return p.resolve()

    async def execute(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = True,
        **kwargs,
    ) -> ToolResult:
        """Write content to file."""
        try:
            resolved = self._resolve_path(path)

            if create_dirs:
                resolved.parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(resolved, "w", encoding=encoding) as f:
                await f.write(content)

            return ToolResult.ok(
                f"Written {len(content)} bytes to {path}",
                path=str(resolved),
                size=len(content),
            )

        except PermissionError as e:
            return ToolResult.fail(str(e))
        except Exception as e:
            return ToolResult.fail(f"Error writing file: {e}")


class ListDirectoryTool(BaseTool):
    """List contents of a directory."""

    name = "list_directory"
    description = "List files and directories at the specified path."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the directory to list",
            },
            "recursive": {
                "type": "boolean",
                "description": "List recursively",
                "default": False,
            },
            "show_hidden": {
                "type": "boolean",
                "description": "Show hidden files (starting with .)",
                "default": False,
            },
        },
        "required": ["path"],
    }

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path

    def _resolve_path(self, path: str) -> Path:
        """Resolve path with sandboxing."""
        p = Path(path)
        if self.base_path:
            resolved = (self.base_path / p).resolve()
            if not str(resolved).startswith(str(self.base_path.resolve())):
                raise PermissionError(f"Access denied: {path}")
            return resolved
        return p.resolve()

    async def execute(
        self,
        path: str,
        recursive: bool = False,
        show_hidden: bool = False,
        **kwargs,
    ) -> ToolResult:
        """List directory contents."""
        try:
            resolved = self._resolve_path(path)

            if not resolved.exists():
                return ToolResult.fail(f"Directory not found: {path}")

            if not resolved.is_dir():
                return ToolResult.fail(f"Not a directory: {path}")

            entries = []

            if recursive:
                for item in resolved.rglob("*"):
                    if not show_hidden and any(
                        part.startswith(".") for part in item.parts
                    ):
                        continue
                    rel_path = item.relative_to(resolved)
                    entry_type = "dir" if item.is_dir() else "file"
                    entries.append(f"{entry_type}: {rel_path}")
            else:
                for item in sorted(resolved.iterdir()):
                    if not show_hidden and item.name.startswith("."):
                        continue
                    entry_type = "dir" if item.is_dir() else "file"
                    entries.append(f"{entry_type}: {item.name}")

            output = "\n".join(entries) if entries else "(empty directory)"

            return ToolResult.ok(
                output,
                path=str(resolved),
                count=len(entries),
            )

        except PermissionError as e:
            return ToolResult.fail(str(e))
        except Exception as e:
            return ToolResult.fail(f"Error listing directory: {e}")
