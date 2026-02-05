"""Base tool interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    output: str
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def ok(cls, output: str, **metadata) -> "ToolResult":
        """Create successful result."""
        return cls(success=True, output=output, metadata=metadata)

    @classmethod
    def fail(cls, error: str, output: str = "", **metadata) -> "ToolResult":
        """Create failed result."""
        return cls(success=False, output=output, error=error, metadata=metadata)


class BaseTool(ABC):
    """
    Base class for all tools.

    Tools provide capabilities for the agent to interact with
    the environment (filesystem, shell, git, etc.)
    """

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with given arguments.

        Args:
            **kwargs: Tool-specific arguments

        Returns:
            ToolResult with success status and output
        """
        pass

    def to_anthropic_format(self) -> dict:
        """Convert to Anthropic tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def to_openai_format(self) -> dict:
        """Convert to OpenAI function format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def validate_args(self, **kwargs) -> Optional[str]:
        """
        Validate arguments against schema.

        Returns:
            Error message if validation fails, None otherwise.
        """
        required = self.parameters.get("required", [])
        for param in required:
            if param not in kwargs:
                return f"Missing required parameter: {param}"
        return None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name})"
