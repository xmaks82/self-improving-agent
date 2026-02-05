"""MCP Client for connecting to MCP servers."""

import asyncio
from contextlib import AsyncExitStack
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool as MCPTool

from .registry import MCPServerConfig


class MCPClient:
    """
    Client for connecting to MCP servers.

    Manages connection lifecycle and tool discovery.
    """

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.session: Optional[ClientSession] = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self._tools: list[MCPTool] = []
        self._connected = False

    @property
    def name(self) -> str:
        """Server name."""
        return self.config.name

    @property
    def is_connected(self) -> bool:
        """Check if connected to server."""
        return self._connected and self.session is not None

    @property
    def tools(self) -> list[MCPTool]:
        """List of available tools from this server."""
        return self._tools

    async def connect(self) -> bool:
        """
        Connect to the MCP server.

        Returns:
            True if connection successful, False otherwise.
        """
        if self._connected:
            return True

        try:
            self._exit_stack = AsyncExitStack()

            # Build server parameters
            server_params = StdioServerParameters(
                command=self.config.command,
                args=self.config.args or [],
                env=self.config.env,
            )

            # Connect via stdio
            stdio_transport = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            stdio, write = stdio_transport

            # Create session
            self.session = await self._exit_stack.enter_async_context(
                ClientSession(stdio, write)
            )

            # Initialize
            await self.session.initialize()

            # Discover tools
            response = await self.session.list_tools()
            self._tools = response.tools if response.tools else []

            self._connected = True
            return True

        except Exception as e:
            await self.disconnect()
            raise ConnectionError(f"Failed to connect to {self.config.name}: {e}")

    async def disconnect(self):
        """Disconnect from the server."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
        self.session = None
        self._tools = []
        self._connected = False

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """
        Call a tool on the server.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if not self.is_connected or not self.session:
            raise RuntimeError(f"Not connected to server {self.config.name}")

        result = await self.session.call_tool(name, arguments)
        return result

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get tool by name."""
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None

    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        return f"MCPClient({self.config.name}, {status}, {len(self._tools)} tools)"
