"""Confirmation system for dangerous operations."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt


class ActionType(Enum):
    """Types of actions that may require confirmation."""

    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    COMMAND_EXECUTE = "command_execute"
    GIT_COMMIT = "git_commit"
    GIT_PUSH = "git_push"
    NETWORK_REQUEST = "network_request"
    DATABASE_MODIFY = "database_modify"
    DESTRUCTIVE = "destructive"


@dataclass
class PendingAction:
    """An action pending user confirmation."""

    action_type: ActionType
    description: str
    details: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "medium"  # low, medium, high
    reversible: bool = True

    def format_details(self) -> str:
        """Format details for display."""
        lines = []
        for key, value in self.details.items():
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)


class ConfirmationResult(Enum):
    """Result of a confirmation request."""

    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    SKIPPED = "skipped"


@dataclass
class Confirmation:
    """Result of a confirmation request."""

    result: ConfirmationResult
    action: PendingAction
    modifications: Optional[dict] = None
    reason: Optional[str] = None


class Confirmator:
    """
    Handles user confirmation for potentially dangerous actions.

    Features:
    - Risk-based confirmation requirements
    - Batch approval for multiple actions
    - Auto-approve for low-risk actions
    - Detailed action preview
    """

    # Actions that always require confirmation
    ALWAYS_CONFIRM = {
        ActionType.FILE_DELETE,
        ActionType.GIT_PUSH,
        ActionType.DESTRUCTIVE,
    }

    # Actions that can be auto-approved
    AUTO_APPROVE = {
        ActionType.FILE_WRITE,  # With diff preview
        ActionType.COMMAND_EXECUTE,  # Safe commands only
    }

    def __init__(
        self,
        console: Optional[Console] = None,
        auto_approve: bool = False,
        interactive: bool = True,
    ):
        self.console = console or Console()
        self.auto_approve = auto_approve
        self.interactive = interactive
        self._approval_history: list[Confirmation] = []

    async def confirm(
        self,
        action: PendingAction,
        show_details: bool = True,
    ) -> Confirmation:
        """
        Request confirmation for an action.

        Args:
            action: The action to confirm
            show_details: Whether to show action details

        Returns:
            Confirmation result
        """
        # Check auto-approve
        if self.auto_approve and action.action_type not in self.ALWAYS_CONFIRM:
            if action.risk_level == "low":
                result = Confirmation(
                    result=ConfirmationResult.APPROVED,
                    action=action,
                    reason="auto-approved (low risk)",
                )
                self._approval_history.append(result)
                return result

        # Non-interactive mode
        if not self.interactive:
            result = Confirmation(
                result=ConfirmationResult.SKIPPED,
                action=action,
                reason="non-interactive mode",
            )
            self._approval_history.append(result)
            return result

        # Show action details
        if show_details:
            self._display_action(action)

        # Get confirmation
        try:
            response = await asyncio.to_thread(
                self._prompt_user, action
            )
        except (EOFError, KeyboardInterrupt):
            response = ConfirmationResult.REJECTED

        result = Confirmation(
            result=response,
            action=action,
        )
        self._approval_history.append(result)
        return result

    async def confirm_batch(
        self,
        actions: list[PendingAction],
    ) -> list[Confirmation]:
        """
        Request confirmation for multiple actions.

        Args:
            actions: List of actions to confirm

        Returns:
            List of confirmation results
        """
        if not actions:
            return []

        # Show summary
        self._display_batch_summary(actions)

        # Ask for batch approval
        if not self.interactive:
            return [
                Confirmation(
                    result=ConfirmationResult.SKIPPED,
                    action=a,
                    reason="non-interactive mode",
                )
                for a in actions
            ]

        try:
            batch_approved = await asyncio.to_thread(
                Confirm.ask,
                "Approve all actions?",
                default=False,
            )
        except (EOFError, KeyboardInterrupt):
            batch_approved = False

        if batch_approved:
            return [
                Confirmation(
                    result=ConfirmationResult.APPROVED,
                    action=a,
                    reason="batch approved",
                )
                for a in actions
            ]

        # Individual confirmation
        results = []
        for action in actions:
            result = await self.confirm(action)
            results.append(result)

        return results

    def _display_action(self, action: PendingAction):
        """Display action details."""
        risk_colors = {
            "low": "green",
            "medium": "yellow",
            "high": "red",
        }
        risk_color = risk_colors.get(action.risk_level, "yellow")

        content = f"""[bold]Action:[/bold] {action.description}
[bold]Type:[/bold] {action.action_type.value}
[bold]Risk:[/bold] [{risk_color}]{action.risk_level.upper()}[/{risk_color}]
[bold]Reversible:[/bold] {"Yes" if action.reversible else "[red]No[/red]"}

[bold]Details:[/bold]
{action.format_details()}"""

        panel = Panel(
            content,
            title="[yellow]Confirmation Required[/yellow]",
            border_style="yellow",
        )
        self.console.print(panel)

    def _display_batch_summary(self, actions: list[PendingAction]):
        """Display summary of batch actions."""
        from rich.table import Table

        table = Table(title="Pending Actions", show_header=True)
        table.add_column("#", width=3)
        table.add_column("Type", style="cyan")
        table.add_column("Description")
        table.add_column("Risk", width=8)

        for i, action in enumerate(actions, 1):
            risk_colors = {"low": "green", "medium": "yellow", "high": "red"}
            risk = f"[{risk_colors.get(action.risk_level, 'yellow')}]{action.risk_level}[/]"
            table.add_row(str(i), action.action_type.value, action.description[:50], risk)

        self.console.print(table)

    def _prompt_user(self, action: PendingAction) -> ConfirmationResult:
        """Prompt user for confirmation."""
        response = Prompt.ask(
            "Proceed?",
            choices=["y", "n", "s"],
            default="n",
        )

        if response == "y":
            return ConfirmationResult.APPROVED
        elif response == "s":
            return ConfirmationResult.SKIPPED
        else:
            return ConfirmationResult.REJECTED

    def get_history(self) -> list[Confirmation]:
        """Get approval history."""
        return self._approval_history.copy()

    def clear_history(self):
        """Clear approval history."""
        self._approval_history.clear()

    @property
    def approved_count(self) -> int:
        """Count of approved actions."""
        return sum(
            1 for c in self._approval_history
            if c.result == ConfirmationResult.APPROVED
        )

    @property
    def rejected_count(self) -> int:
        """Count of rejected actions."""
        return sum(
            1 for c in self._approval_history
            if c.result == ConfirmationResult.REJECTED
        )
