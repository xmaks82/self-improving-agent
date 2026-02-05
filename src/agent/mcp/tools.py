"""MCP Tool Adapter for integrating MCP tools with the agent."""

from dataclasses import dataclass
from typing import Any, Optional

from mcp.types import Tool as MCPTool

from .client import MCPClient


@dataclass
class ToolDefinition:
    """Tool definition for LLM function calling."""

    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str  # Which MCP server provides this tool

    def to_anthropic_format(self) -> dict:
        """Convert to Anthropic tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def to_openai_format(self) -> dict:
        """Convert to OpenAI function format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class MCPToolAdapter:
    """
    Adapter for using MCP tools with LLM function calling.

    Collects tools from multiple MCP servers and provides
    unified interface for tool execution.
    """

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._tool_map: dict[str, str] = {}  # tool_name -> server_name

    def register_client(self, client: MCPClient):
        """Register an MCP client and its tools."""
        self._clients[client.name] = client

        # Map tools to server
        for tool in client.tools:
            self._tool_map[tool.name] = client.name

    def unregister_client(self, name: str):
        """Unregister a client."""
        if name in self._clients:
            # Remove tool mappings
            client = self._clients[name]
            for tool in client.tools:
                if tool.name in self._tool_map:
                    del self._tool_map[tool.name]
            del self._clients[name]

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """Get all available tool definitions."""
        definitions = []

        for client in self._clients.values():
            for tool in client.tools:
                definitions.append(
                    ToolDefinition(
                        name=tool.name,
                        description=tool.description or "",
                        input_schema=tool.inputSchema if tool.inputSchema else {},
                        server_name=client.name,
                    )
                )

        return definitions

    def get_anthropic_tools(self) -> list[dict]:
        """Get tools in Anthropic format."""
        return [t.to_anthropic_format() for t in self.get_tool_definitions()]

    def get_openai_tools(self) -> list[dict]:
        """Get tools in OpenAI format."""
        return [t.to_openai_format() for t in self.get_tool_definitions()]

    async def execute_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute a tool by name.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        server_name = self._tool_map.get(name)
        if not server_name:
            return {
                "success": False,
                "error": f"Tool '{name}' not found",
            }

        client = self._clients.get(server_name)
        if not client or not client.is_connected:
            return {
                "success": False,
                "error": f"Server '{server_name}' not connected",
            }

        try:
            result = await client.call_tool(name, arguments)

            # Extract content from result
            if hasattr(result, "content"):
                content = result.content
                if isinstance(content, list):
                    # Join text content
                    text_parts = []
                    for item in content:
                        if hasattr(item, "text"):
                            text_parts.append(item.text)
                        else:
                            text_parts.append(str(item))
                    output = "\n".join(text_parts)
                else:
                    output = str(content)
            else:
                output = str(result)

            return {
                "success": True,
                "output": output,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def get_tool_info(self, name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name."""
        server_name = self._tool_map.get(name)
        if not server_name:
            return None

        client = self._clients.get(server_name)
        if not client:
            return None

        mcp_tool = client.get_tool(name)
        if not mcp_tool:
            return None

        return ToolDefinition(
            name=mcp_tool.name,
            description=mcp_tool.description or "",
            input_schema=mcp_tool.inputSchema if mcp_tool.inputSchema else {},
            server_name=server_name,
        )

    def list_tools(self) -> list[str]:
        """List all available tool names."""
        return list(self._tool_map.keys())

    @property
    def tool_count(self) -> int:
        """Number of available tools."""
        return len(self._tool_map)

    @property
    def server_count(self) -> int:
        """Number of connected servers."""
        return len(self._clients)

    def __repr__(self) -> str:
        return f"MCPToolAdapter({self.server_count} servers, {self.tool_count} tools)"
