"""Human-in-the-loop approval system."""

from .diff_viewer import DiffViewer, FileDiff
from .confirmator import (
    Confirmator,
    ConfirmationResult,
    Confirmation,
    PendingAction,
    ActionType,
)
from .dry_run import DryRunSession, PlannedAction, ActionStatus
from .undo import UndoManager, Change

__all__ = [
    # Diff viewing
    "DiffViewer",
    "FileDiff",
    # Confirmation
    "Confirmator",
    "ConfirmationResult",
    "Confirmation",
    "PendingAction",
    "ActionType",
    # Dry run
    "DryRunSession",
    "PlannedAction",
    "ActionStatus",
    # Undo
    "UndoManager",
    "Change",
]
