"""Filesystem tools with read-before-edit enforcement."""

import os
import uuid
from pathlib import Path
from typing import Optional, TYPE_CHECKING
import aiofiles
import aiofiles.os

from .base import BaseTool, ToolResult


async def _atomic_write(resolved: Path, content: str, encoding: str) -> None:
    """Write via temp file + os.replace so an interrupted write never leaves
    a truncated/corrupt target (atomic on the same filesystem). Unique temp
    name avoids collisions between concurrent writers."""
    tmp = resolved.with_name(f"{resolved.name}.tmp-{uuid.uuid4().hex[:8]}")
    try:
        async with aiofiles.open(tmp, "w", encoding=encoding) as f:
            await f.write(content)
        os.replace(tmp, resolved)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass

if TYPE_CHECKING:
    from .file_state import FileReadStateTracker


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
            "offset": {
                "type": "integer",
                "description": "1-based line number to start reading from",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read",
            },
        },
        "required": ["path"],
    }

    # Guard: never slurp an unbounded file fully into memory.
    MAX_READ_BYTES = 2_000_000

    def __init__(self, base_path: Optional[Path] = None, file_state: Optional["FileReadStateTracker"] = None):
        self.base_path = base_path
        self.file_state = file_state

    def _resolve_path(self, path: str) -> Path:
        """Resolve path, applying sandboxing if configured."""
        p = Path(path)
        if self.base_path:
            # Sandbox: ensure path is within base_path
            resolved = (self.base_path / p).resolve()
            if not resolved.is_relative_to(self.base_path.resolve()):
                raise PermissionError(f"Access denied: {path}")
            return resolved
        return p.resolve()

    async def execute(self, path: str, encoding: str = "utf-8",
                      offset: Optional[int] = None, limit: Optional[int] = None,
                      **kwargs) -> ToolResult:
        """Read file contents (optionally a line range; large files are capped)."""
        try:
            resolved = self._resolve_path(path)

            if not resolved.exists():
                return ToolResult.fail(f"File not found: {path}")

            if not resolved.is_file():
                return ToolResult.fail(f"Not a file: {path}")

            size = resolved.stat().st_size
            truncated = False

            if offset is not None or limit is not None:
                async with aiofiles.open(resolved, "r", encoding=encoding) as f:
                    all_lines = (await f.read()).splitlines(keepends=True)
                start = (offset - 1) if offset and offset > 0 else 0
                end = (start + limit) if limit else len(all_lines)
                content = "".join(all_lines[start:end])
            elif size > self.MAX_READ_BYTES:
                async with aiofiles.open(resolved, "r", encoding=encoding) as f:
                    content = await f.read(self.MAX_READ_BYTES)
                truncated = True
            else:
                async with aiofiles.open(resolved, "r", encoding=encoding) as f:
                    content = await f.read()

            # Track read for read-before-edit enforcement (note partial reads).
            if self.file_state:
                self.file_state.record_read(str(resolved), offset=offset, limit=limit)

            if truncated:
                content += (f"\n...[truncated at {self.MAX_READ_BYTES} bytes of {size}; "
                            f"use offset/limit to read more]")

            return ToolResult.ok(
                content,
                path=str(resolved),
                size=len(content),
                lines=content.count("\n") + 1,
                truncated=truncated,
            )

        except PermissionError as e:
            return ToolResult.fail(str(e))
        except UnicodeDecodeError:
            return ToolResult.fail(f"Cannot decode file with encoding {encoding}")
        except Exception as e:
            return ToolResult.fail(f"Error reading file: {e}")


class WriteFileTool(BaseTool):
    """Write contents to a file with read-before-write enforcement."""

    name = "write_file"
    description = "Write content to a file. If the file exists, you MUST read it first."
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

    def __init__(self, base_path: Optional[Path] = None, file_state: Optional["FileReadStateTracker"] = None, undo_manager=None):
        self.base_path = base_path
        self.file_state = file_state
        self.undo_manager = undo_manager

    def _resolve_path(self, path: str) -> Path:
        """Resolve path with sandboxing."""
        p = Path(path)
        if self.base_path:
            resolved = (self.base_path / p).resolve()
            if not resolved.is_relative_to(self.base_path.resolve()):
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
        """Write content to file with read-before-write enforcement."""
        try:
            resolved = self._resolve_path(path)

            # Enforce read-before-write for existing files
            if self.file_state and resolved.exists():
                if not self.file_state.has_been_read(str(resolved)):
                    return ToolResult.fail(
                        f"File exists but has not been read yet. "
                        f"Use read_file first before writing to: {path}"
                    )
                # Guard against clobbering external edits made since our read.
                if self.file_state.disk_changed_since_read(str(resolved)):
                    return ToolResult.fail(
                        f"File changed on disk since you read it. "
                        f"Re-read before writing to: {path}"
                    )

            if create_dirs:
                resolved.parent.mkdir(parents=True, exist_ok=True)

            # Capture prior content for undo (None if new file).
            before = None
            if resolved.exists():
                try:
                    async with aiofiles.open(resolved, "r", encoding=encoding) as f:
                        before = await f.read()
                except Exception:
                    before = None

            await _atomic_write(resolved, content, encoding)

            # Record for rollback.
            if self.undo_manager is not None:
                try:
                    await self.undo_manager.record_file_write(str(resolved), before, content)
                except Exception:
                    pass

            # Track write and refresh the read baseline (we now know current content).
            if self.file_state:
                self.file_state.record_write(str(resolved))
                self.file_state.record_read(str(resolved))

            return ToolResult.ok(
                f"Written {len(content)} bytes to {path}",
                path=str(resolved),
                size=len(content),
            )

        except PermissionError as e:
            return ToolResult.fail(str(e))
        except Exception as e:
            return ToolResult.fail(f"Error writing file: {e}")


class EditFileTool(BaseTool):
    """Make a targeted edit: replace an exact string with another."""

    name = "edit_file"
    description = (
        "Replace an exact substring in a file with new text. You MUST read the "
        "file first. old_string must match exactly and be unique unless replace_all=true."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to edit"},
            "old_string": {"type": "string", "description": "Exact text to replace"},
            "new_string": {"type": "string", "description": "Replacement text"},
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences (default: false)",
                "default": False,
            },
            "encoding": {"type": "string", "description": "File encoding", "default": "utf-8"},
        },
        "required": ["path", "old_string", "new_string"],
    }

    def __init__(self, base_path: Optional[Path] = None, file_state: Optional["FileReadStateTracker"] = None, undo_manager=None):
        self.base_path = base_path
        self.file_state = file_state
        self.undo_manager = undo_manager

    def _resolve_path(self, path: str) -> Path:
        p = Path(path)
        if self.base_path:
            resolved = (self.base_path / p).resolve()
            if not resolved.is_relative_to(self.base_path.resolve()):
                raise PermissionError(f"Access denied: {path}")
            return resolved
        return p.resolve()

    async def execute(
        self,
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        encoding: str = "utf-8",
        **kwargs,
    ) -> ToolResult:
        try:
            resolved = self._resolve_path(path)
            if not resolved.exists() or not resolved.is_file():
                return ToolResult.fail(f"File not found: {path}")

            if self.file_state:
                if not self.file_state.has_been_read(str(resolved)):
                    return ToolResult.fail(
                        f"File has not been read yet. Use read_file first before editing: {path}"
                    )
                if self.file_state.disk_changed_since_read(str(resolved)):
                    return ToolResult.fail(
                        f"File changed on disk since you read it. Re-read before editing: {path}"
                    )

            if old_string == new_string:
                return ToolResult.fail("old_string and new_string are identical — nothing to do.")

            async with aiofiles.open(resolved, "r", encoding=encoding) as f:
                content = await f.read()

            count = content.count(old_string)
            if count == 0:
                return ToolResult.fail("old_string not found in file.")
            if count > 1 and not replace_all:
                return ToolResult.fail(
                    f"old_string appears {count} times — add more context to make it unique, "
                    f"or pass replace_all=true."
                )

            if replace_all:
                new_content = content.replace(old_string, new_string)
            else:
                new_content = content.replace(old_string, new_string, 1)

            await _atomic_write(resolved, new_content, encoding)

            if self.undo_manager is not None:
                try:
                    await self.undo_manager.record_file_write(str(resolved), content, new_content)
                except Exception:
                    pass

            if self.file_state:
                self.file_state.record_write(str(resolved))
                self.file_state.record_read(str(resolved))

            n = count if replace_all else 1
            return ToolResult.ok(
                f"Edited {path} ({n} replacement{'s' if n != 1 else ''}).",
                path=str(resolved),
                replacements=n,
            )

        except PermissionError as e:
            return ToolResult.fail(str(e))
        except UnicodeDecodeError:
            return ToolResult.fail(f"Cannot decode file with encoding {encoding}")
        except Exception as e:
            return ToolResult.fail(f"Error editing file: {e}")


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
            if not resolved.is_relative_to(self.base_path.resolve()):
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
