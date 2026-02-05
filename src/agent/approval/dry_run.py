"""Dry run mode for previewing actions without execution."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


class ActionStatus(Enum):
    """Status of a planned action."""

    PENDING = "pending"
    WOULD_EXECUTE = "would_execute"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class PlannedAction:
    """An action that would be executed in live mode."""

    action_type: str
    description: str
    target: str
    parameters: dict[str, Any] = field(default_factory=dict)
    status: ActionStatus = ActionStatus.PENDING
    reason: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type,
            "description": self.description,
            "target": self.target,
            "parameters": self.parameters,
            "status": self.status.value,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


class DryRunSession:
    """
    Session for dry run mode.

    Records what actions would be taken without executing them.
    Useful for previewing changes before applying.
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self._actions: list[PlannedAction] = []
        self._active = False
        self._started_at: Optional[datetime] = None

    def start(self):
        """Start dry run session."""
        self._active = True
        self._started_at = datetime.utcnow()
        self._actions = []
        self.console.print(
            Panel(
                "[yellow]DRY RUN MODE ACTIVE[/yellow]\n"
                "Actions will be recorded but not executed.",
                border_style="yellow",
            )
        )

    def stop(self) -> list[PlannedAction]:
        """Stop dry run session and return recorded actions."""
        self._active = False
        actions = self._actions.copy()
        self.show_summary()
        return actions

    @property
    def is_active(self) -> bool:
        """Check if dry run is active."""
        return self._active

    def record(
        self,
        action_type: str,
        description: str,
        target: str,
        parameters: Optional[dict] = None,
        would_execute: bool = True,
        reason: Optional[str] = None,
    ) -> PlannedAction:
        """
        Record a planned action.

        Args:
            action_type: Type of action (write_file, run_command, etc.)
            description: Human-readable description
            target: Target of the action (file path, command, etc.)
            parameters: Action parameters
            would_execute: Whether action would execute in live mode
            reason: Reason if action would be skipped/blocked

        Returns:
            The recorded PlannedAction
        """
        status = (
            ActionStatus.WOULD_EXECUTE if would_execute
            else ActionStatus.BLOCKED if reason
            else ActionStatus.SKIPPED
        )

        action = PlannedAction(
            action_type=action_type,
            description=description,
            target=target,
            parameters=parameters or {},
            status=status,
            reason=reason,
        )

        self._actions.append(action)

        # Show inline notification
        if self._active:
            self._show_action(action)

        return action

    def record_file_write(
        self,
        path: str,
        content: str,
        is_new: bool = False,
    ) -> PlannedAction:
        """Record a file write action."""
        return self.record(
            action_type="write_file",
            description=f"{'Create' if is_new else 'Modify'} file",
            target=path,
            parameters={
                "content_length": len(content),
                "is_new": is_new,
            },
        )

    def record_file_delete(self, path: str) -> PlannedAction:
        """Record a file delete action."""
        return self.record(
            action_type="delete_file",
            description="Delete file",
            target=path,
        )

    def record_command(
        self,
        command: str,
        cwd: Optional[str] = None,
    ) -> PlannedAction:
        """Record a command execution action."""
        return self.record(
            action_type="run_command",
            description="Execute command",
            target=command,
            parameters={"cwd": cwd} if cwd else {},
        )

    def record_git_commit(
        self,
        message: str,
        files: list[str],
    ) -> PlannedAction:
        """Record a git commit action."""
        return self.record(
            action_type="git_commit",
            description="Git commit",
            target=message,
            parameters={"files": files},
        )

    def _show_action(self, action: PlannedAction):
        """Show action notification."""
        status_icons = {
            ActionStatus.WOULD_EXECUTE: "[green]▶[/green]",
            ActionStatus.SKIPPED: "[yellow]⏭[/yellow]",
            ActionStatus.BLOCKED: "[red]⏹[/red]",
        }
        icon = status_icons.get(action.status, "•")

        self.console.print(
            f"  {icon} [dim]Would[/dim] {action.description}: "
            f"[cyan]{action.target[:50]}{'...' if len(action.target) > 50 else ''}[/cyan]"
        )

    def show_summary(self):
        """Show summary of all recorded actions."""
        if not self._actions:
            self.console.print("[dim]No actions recorded.[/dim]")
            return

        table = Table(title="Dry Run Summary", show_header=True)
        table.add_column("#", width=3)
        table.add_column("Action", style="cyan")
        table.add_column("Target")
        table.add_column("Status", width=12)

        for i, action in enumerate(self._actions, 1):
            status_style = {
                ActionStatus.WOULD_EXECUTE: "[green]execute[/green]",
                ActionStatus.SKIPPED: "[yellow]skip[/yellow]",
                ActionStatus.BLOCKED: "[red]blocked[/red]",
            }
            status = status_style.get(action.status, str(action.status.value))

            target = action.target
            if len(target) > 40:
                target = target[:37] + "..."

            table.add_row(str(i), action.action_type, target, status)

        self.console.print(table)

        # Stats
        would_execute = sum(
            1 for a in self._actions if a.status == ActionStatus.WOULD_EXECUTE
        )
        blocked = sum(
            1 for a in self._actions if a.status == ActionStatus.BLOCKED
        )

        self.console.print(
            f"\n[bold]Total:[/bold] {len(self._actions)} actions "
            f"([green]{would_execute} would execute[/green], "
            f"[red]{blocked} blocked[/red])"
        )

    def get_actions(self) -> list[PlannedAction]:
        """Get all recorded actions."""
        return self._actions.copy()

    def get_would_execute(self) -> list[PlannedAction]:
        """Get actions that would execute."""
        return [a for a in self._actions if a.status == ActionStatus.WOULD_EXECUTE]

    def clear(self):
        """Clear recorded actions."""
        self._actions.clear()

    def export(self) -> list[dict]:
        """Export actions as dictionaries."""
        return [a.to_dict() for a in self._actions]
