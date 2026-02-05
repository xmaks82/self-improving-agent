"""MCP Server Registry for managing multiple servers."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import yaml
import aiofiles

from ..config import config as app_config


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    description: str = ""

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "MCPServerConfig":
        """Create config from dictionary."""
        return cls(
            name=name,
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "enabled": self.enabled,
            "description": self.description,
        }


class MCPRegistry:
    """
    Registry for MCP servers.

    Manages server configurations and connected clients.
    Config file: ~/.agent/mcp.yaml or data/mcp.yaml
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self._default_config_path()
        self._servers: dict[str, MCPServerConfig] = {}
        self._clients: dict[str, Any] = {}  # MCPClient instances

    def _default_config_path(self) -> Path:
        """Get default config path."""
        # Check home directory first
        home_config = Path.home() / ".agent" / "mcp.yaml"
        if home_config.exists():
            return home_config
        # Fall back to data directory
        return app_config.paths.data / "mcp.yaml"

    async def load(self):
        """Load server configurations from file."""
        if not self.config_path.exists():
            self._servers = {}
            return

        async with aiofiles.open(self.config_path, "r") as f:
            content = await f.read()

        data = yaml.safe_load(content) or {}
        servers = data.get("servers", {})

        self._servers = {
            name: MCPServerConfig.from_dict(name, config)
            for name, config in servers.items()
        }

    async def save(self):
        """Save server configurations to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "servers": {
                name: config.to_dict()
                for name, config in self._servers.items()
            }
        }

        async with aiofiles.open(self.config_path, "w") as f:
            await f.write(yaml.dump(data, default_flow_style=False))

    def add_server(self, config: MCPServerConfig):
        """Add a server configuration."""
        self._servers[config.name] = config

    def remove_server(self, name: str) -> bool:
        """Remove a server configuration."""
        if name in self._servers:
            del self._servers[name]
            return True
        return False

    def get_server(self, name: str) -> Optional[MCPServerConfig]:
        """Get server configuration by name."""
        return self._servers.get(name)

    def list_servers(self) -> list[MCPServerConfig]:
        """List all server configurations."""
        return list(self._servers.values())

    def list_enabled_servers(self) -> list[MCPServerConfig]:
        """List enabled server configurations."""
        return [s for s in self._servers.values() if s.enabled]

    def register_client(self, name: str, client: Any):
        """Register a connected client."""
        self._clients[name] = client

    def unregister_client(self, name: str):
        """Unregister a client."""
        if name in self._clients:
            del self._clients[name]

    def get_client(self, name: str) -> Optional[Any]:
        """Get connected client by name."""
        return self._clients.get(name)

    def list_connected_clients(self) -> list[Any]:
        """List all connected clients."""
        return list(self._clients.values())

    def __repr__(self) -> str:
        return f"MCPRegistry({len(self._servers)} servers, {len(self._clients)} connected)"
