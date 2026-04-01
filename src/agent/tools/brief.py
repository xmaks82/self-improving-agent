"""Brief tool — formatted output with attachments."""

from pathlib import Path
from datetime import datetime, timezone

from .base import BaseTool, ToolResult


class BriefTool(BaseTool):
    """Send a formatted message to the user with optional file attachments."""

    name = "send_brief"
    description = "Send a structured message to the user with optional file attachments."
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Markdown message."},
            "attachments": {
                "type": "array", "items": {"type": "string"},
                "description": "File paths to attach.",
            },
        },
        "required": ["message"],
    }

    async def execute(self, message: str, attachments: list[str] = None, **kwargs) -> ToolResult:
        resolved = []
        for path_str in (attachments or []):
            p = Path(path_str)
            if not p.is_absolute():
                p = Path.cwd() / p
            if not p.exists():
                return ToolResult.fail(f"Attachment not found: {path_str}")
            resolved.append({
                "path": str(p), "size": p.stat().st_size,
                "name": p.name,
                "is_image": p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".svg"},
            })

        return ToolResult.ok(
            message,
            attachments=resolved,
            sent_at=datetime.now(timezone.utc).isoformat(),
        )
