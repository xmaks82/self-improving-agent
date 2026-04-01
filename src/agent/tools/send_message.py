"""Inter-agent messaging tool."""

from .base import BaseTool, ToolResult
from ..core.mailbox import AgentMailbox, AgentMessage


class SendMessageTool(BaseTool):
    """Send a message to another agent."""

    name = "send_message"
    description = "Send a message to another agent by name."
    parameters = {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient agent name."},
            "message": {"type": "string", "description": "Message content."},
            "summary": {"type": "string", "description": "5-10 word summary."},
        },
        "required": ["to", "message"],
    }

    def __init__(self, mailbox: AgentMailbox, sender_name: str = "main_agent"):
        self.mailbox = mailbox
        self.sender_name = sender_name

    async def execute(self, to: str, message: str, summary: str = "", **kwargs) -> ToolResult:
        msg = AgentMessage(
            sender=self.sender_name, recipient=to,
            content=message, summary=summary or message[:50],
        )
        await self.mailbox.send(msg)
        return ToolResult.ok(f"Message sent to {to}: {summary or message[:50]}")
