"""Tool registry for managing available tools."""

from pathlib import Path
from typing import Any, Optional

from .base import BaseTool, ToolResult
from .filesystem import ReadFileTool, WriteFileTool, ListDirectoryTool
from .shell import RunCommandTool
from .git import GitStatusTool, GitDiffTool, GitCommitTool
from .search import SearchFilesTool, GrepTool
from .web_search import WebSearchTool
from .web_fetch import WebFetchTool


class ToolRegistry:
    """
    Registry of available tools.

    Manages tool instances and provides unified access
    for tool discovery and execution.
    """

    def __init__(
        self,
        working_dir: Optional[Path] = None,
        sandbox_mode: bool = True,
    ):
        """
        Initialize tool registry.

        Args:
            working_dir: Base working directory for tools
            sandbox_mode: Enable safety restrictions
        """
        self.working_dir = working_dir or Path.cwd()
        self.sandbox_mode = sandbox_mode
        self._tools: dict[str, BaseTool] = {}

        # Register default tools
        self._register_default_tools()

    def _register_default_tools(self):
        """Register all default tools."""
        base = self.working_dir if self.sandbox_mode else None

        # Filesystem tools
        self.register(ReadFileTool(base_path=base))
        self.register(WriteFileTool(base_path=base))
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

        # Web tools
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

    async def execute(self, name: str, **kwargs) -> ToolResult:
        """
        Execute a tool by name.

        Args:
            name: Tool name
            **kwargs: Tool arguments

        Returns:
            ToolResult
        """
        tool = self.get(name)
        if not tool:
            return ToolResult.fail(f"Tool not found: {name}")

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
        return "\n".join(lines)

    @property
    def count(self) -> int:
        """Number of registered tools."""
        return len(self._tools)

    def __repr__(self) -> str:
        return f"ToolRegistry({self.count} tools)"

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __iter__(self):
        return iter(self._tools.values())
