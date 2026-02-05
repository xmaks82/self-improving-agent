"""MCP Manager for coordinating MCP operations."""

from pathlib import Path
from typing import Optional

from .client import MCPClient
from .registry import MCPRegistry, MCPServerConfig
from .tools import MCPToolAdapter


class MCPManager:
    """
    Manages MCP server connections and tool access.

    Provides high-level API for:
    - Loading/saving server configurations
    - Connecting/disconnecting servers
    - Tool discovery and execution
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.registry = MCPRegistry(config_path)
        self.tool_adapter = MCPToolAdapter()
        self._initialized = False

    async def initialize(self):
        """Initialize manager and load configurations."""
        if self._initialized:
            return

        await self.registry.load()
        self._initialized = True

    async def shutdown(self):
        """Shutdown all connections."""
        for client in list(self.registry.list_connected_clients()):
            await self.disconnect(client.name)

    async def connect(self, server_name: str) -> bool:
        """
        Connect to a server.

        Args:
            server_name: Name of server to connect

        Returns:
            True if connection successful
        """
        config = self.registry.get_server(server_name)
        if not config:
            raise ValueError(f"Server '{server_name}' not found in registry")

        # Check if already connected
        existing = self.registry.get_client(server_name)
        if existing and existing.is_connected:
            return True

        # Create and connect client
        client = MCPClient(config)
        await client.connect()

        # Register
        self.registry.register_client(server_name, client)
        self.tool_adapter.register_client(client)

        return True

    async def disconnect(self, server_name: str) -> bool:
        """
        Disconnect from a server.

        Args:
            server_name: Name of server to disconnect

        Returns:
            True if disconnection successful
        """
        client = self.registry.get_client(server_name)
        if not client:
            return False

        await client.disconnect()
        self.registry.unregister_client(server_name)
        self.tool_adapter.unregister_client(server_name)

        return True

    async def connect_all(self) -> dict[str, bool]:
        """
        Connect to all enabled servers.

        Returns:
            Dict of server_name -> success status
        """
        results = {}
        for config in self.registry.list_enabled_servers():
            try:
                results[config.name] = await self.connect(config.name)
            except Exception as e:
                results[config.name] = False
        return results

    def add_server(
        self,
        name: str,
        command: str,
        args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
        description: str = "",
    ) -> MCPServerConfig:
        """Add a new server configuration."""
        config = MCPServerConfig(
            name=name,
            command=command,
            args=args or [],
            env=env or {},
            enabled=True,
            description=description,
        )
        self.registry.add_server(config)
        return config

    async def remove_server(self, name: str) -> bool:
        """Remove a server configuration and disconnect if connected."""
        if self.registry.get_client(name):
            await self.disconnect(name)
        return self.registry.remove_server(name)

    async def save_config(self):
        """Save current configuration to file."""
        await self.registry.save()

    def get_tools(self) -> list[dict]:
        """Get all available tools in Anthropic format."""
        return self.tool_adapter.get_anthropic_tools()

    async def execute_tool(self, name: str, arguments: dict) -> dict:
        """Execute a tool."""
        return await self.tool_adapter.execute_tool(name, arguments)

    def list_servers(self) -> list[dict]:
        """List all servers with status."""
        servers = []
        for config in self.registry.list_servers():
            client = self.registry.get_client(config.name)
            servers.append({
                "name": config.name,
                "command": config.command,
                "enabled": config.enabled,
                "connected": client.is_connected if client else False,
                "tools": len(client.tools) if client and client.is_connected else 0,
                "description": config.description,
            })
        return servers

    def list_tools(self) -> list[dict]:
        """List all available tools."""
        tools = []
        for definition in self.tool_adapter.get_tool_definitions():
            tools.append({
                "name": definition.name,
                "description": definition.description,
                "server": definition.server_name,
            })
        return tools

    @property
    def connected_count(self) -> int:
        """Number of connected servers."""
        return len(self.registry.list_connected_clients())

    @property
    def tool_count(self) -> int:
        """Number of available tools."""
        return self.tool_adapter.tool_count

    def __repr__(self) -> str:
        return f"MCPManager({self.connected_count} connected, {self.tool_count} tools)"
