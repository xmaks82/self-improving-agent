"""Core components for the self-improving agent."""

from .feedback import Feedback, FeedbackDetector

# Import orchestrator lazily to avoid circular imports
def get_orchestrator():
    from .orchestrator import ImprovementOrchestrator, ImprovementResult
    return ImprovementOrchestrator, ImprovementResult

__all__ = [
    "Feedback",
    "FeedbackDetector",
    "get_orchestrator",
]
