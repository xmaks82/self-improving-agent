"""Tool registry for managing available tools."""

import logging
from pathlib import Path
from typing import Optional

from .base import BaseTool, ToolResult
from .filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirectoryTool
from .shell import RunCommandTool
from .git import GitStatusTool, GitDiffTool, GitCommitTool
from .search import SearchFilesTool, GrepTool
from .web_search import WebSearchTool
from .web_fetch import WebFetchTool
from .permissions import PermissionManager, PermissionLevel
from .file_state import FileReadStateTracker
from .worktree import EnterWorktreeTool, ExitWorktreeTool

logger = logging.getLogger(__name__)

# Tools that are always loaded
CORE_TOOL_NAMES = {
    "read_file", "write_file", "edit_file", "list_directory",
    "run_command", "git_status", "git_diff", "git_commit",
    "search_files", "grep",
}

# Tools that can be loaded on demand
OPTIONAL_TOOLS = {
    "web_search": ("web_search", "WebSearchTool"),
    "fetch_url": ("web_fetch", "WebFetchTool"),
    "notebook_edit": ("notebook", "NotebookEditTool"),
    "send_brief": ("brief", "BriefTool"),
}


class ToolRegistry:
    """
    Registry of available tools.

    Manages tool instances and provides unified access
    for tool discovery and execution. Supports deferred
    loading of optional tools.
    """

    def __init__(
        self,
        working_dir: Optional[Path] = None,
        sandbox_mode: bool = True,
        permission_manager: Optional[PermissionManager] = None,
        file_state: Optional[FileReadStateTracker] = None,
        load_all: bool = True,
        confirm_callback=None,
        undo_manager=None,
    ):
        self.working_dir = working_dir or Path.cwd()
        self.sandbox_mode = sandbox_mode
        self.permission_manager = permission_manager or PermissionManager()
        self.file_state = file_state or FileReadStateTracker()
        # confirm_callback: async (tool_name, kwargs) -> bool. When set, CONFIRM-level
        # tools require approval. None → pass-through (headless/auto).
        self.confirm_callback = confirm_callback
        # undo_manager: records before/after for every file mutation (enables rollback).
        self.undo_manager = undo_manager
        self._tools: dict[str, BaseTool] = {}
        self._deferred: dict[str, tuple[str, str]] = {}

        self._register_default_tools()
        if load_all:
            self._register_optional_tools()
        else:
            self._deferred.update(OPTIONAL_TOOLS)

    def _register_default_tools(self):
        """Register core tools (always available)."""
        base = self.working_dir if self.sandbox_mode else None

        # Filesystem tools (shared file state tracker + undo manager)
        self.register(ReadFileTool(base_path=base, file_state=self.file_state))
        self.register(WriteFileTool(base_path=base, file_state=self.file_state, undo_manager=self.undo_manager))
        self.register(EditFileTool(base_path=base, file_state=self.file_state, undo_manager=self.undo_manager))
        self.register(ListDirectoryTool(base_path=base))

        # Shell tool
        self.register(RunCommandTool(
            working_dir=self.working_dir,
            sandbox_mode=self.sandbox_mode,
        ))

        # Git tools
        self.register(GitStatusTool(default_path=self.working_dir))
        self.register(GitDiffTool(default_path=self.working_dir))
        self.register(GitCommitTool(default_path=self.working_dir))

        # Search tools
        self.register(SearchFilesTool(default_path=self.working_dir))
        self.register(GrepTool(default_path=self.working_dir))

        # Git worktree tools
        enter_wt = EnterWorktreeTool()
        self.register(enter_wt)
        self.register(ExitWorktreeTool(enter_wt))

    def _register_optional_tools(self):
        """Register optional tools (web, etc.)."""
        self.register(WebSearchTool())
        self.register(WebFetchTool())

    def register(self, tool: BaseTool):
        """Register a tool."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> Optional[BaseTool]:
        """Get tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_tool_names(self) -> list[str]:
        """Get list of tool names."""
        return list(self._tools.keys())

    def load_deferred(self, name: str) -> bool:
        """Load a deferred tool on demand. Returns True if loaded."""
        if name in self._tools:
            return True
        if name not in self._deferred:
            return False
        module_name, cls_name = self._deferred[name]
        try:
            import importlib
            mod = importlib.import_module(f".{module_name}", package="agent.tools")
            cls = getattr(mod, cls_name)
            self.register(cls())
            del self._deferred[name]
            logger.info("Loaded deferred tool: %s", name)
            return True
        except Exception as e:
            logger.warning("Failed to load deferred tool %s: %s", name, e)
            return False

    def search_tools(self, query: str) -> list[dict]:
        """Search loaded and deferred tools by name/description."""
        query_lower = query.lower()
        results = []
        for tool in self._tools.values():
            if query_lower in tool.name.lower() or query_lower in tool.description.lower():
                results.append({"name": tool.name, "description": tool.description, "loaded": True})
        for name in self._deferred:
            if query_lower in name.lower():
                results.append({"name": name, "description": "(not loaded)", "loaded": False})
        return results

    async def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name with permission checking."""
        # Auto-load deferred tool if needed
        if name not in self._tools and name in self._deferred:
            self.load_deferred(name)

        tool = self.get(name)
        if not tool:
            return ToolResult.fail(f"Tool not found: {name}")

        # Permission check
        allowed, reason = self.permission_manager.check_permission(name, **kwargs)
        if not allowed:
            return ToolResult.fail(f"Permission denied: {reason}")

        # Confirmation for CONFIRM-level tools (write/run/commit) when a UI wired
        # a callback. Without a callback we pass through (headless/auto mode).
        from .permissions import PermissionLevel
        if (self.confirm_callback is not None
                and self.permission_manager.get_permission(name) == PermissionLevel.CONFIRM):
            try:
                approved = await self.confirm_callback(name, kwargs)
            except Exception as e:
                return ToolResult.fail(f"Confirmation failed: {e}")
            if not approved:
                return ToolResult.fail(f"Rejected by user: {name}")

        # Validate arguments
        error = tool.validate_args(**kwargs)
        if error:
            return ToolResult.fail(error)

        return await tool.execute(**kwargs)

    def get_anthropic_tools(self) -> list[dict]:
        """Get all tools in Anthropic format."""
        return [tool.to_anthropic_format() for tool in self._tools.values()]

    def get_openai_tools(self) -> list[dict]:
        """Get all tools in OpenAI function format."""
        return [tool.to_openai_format() for tool in self._tools.values()]

    def get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions for prompts."""
        lines = ["Available tools:"]
        for tool in self._tools.values():
            lines.append(f"- {tool.name}: {tool.description}")
        if self._deferred:
            lines.append(f"\nAdditional tools available on demand: {', '.join(self._deferred.keys())}")
        return "\n".join(lines)

    @property
    def count(self) -> int:
        """Number of loaded tools."""
        return len(self._tools)

    @property
    def deferred_count(self) -> int:
        """Number of deferred (not yet loaded) tools."""
        return len(self._deferred)

    def __repr__(self) -> str:
        return f"ToolRegistry({self.count} tools)"

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __iter__(self):
        return iter(self._tools.values())
