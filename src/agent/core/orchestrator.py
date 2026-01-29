"""Orchestrator for coordinating the improvement pipeline."""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING
import time

from ..storage.prompts import PromptManager
from ..storage.logs import LogManager
from .feedback import Feedback
from ..config import config

if TYPE_CHECKING:
    from ..agents.analyzer import AnalyzerAgent, AnalysisResult
    from ..agents.versioner import VersionerAgent, PromptVersion


class VersioningError(Exception):
    """Error during prompt versioning."""
    pass


@dataclass
class ImprovementResult:
    """Result of an improvement cycle."""
    success: bool
    old_version: int
    new_version: Optional[int]
    analysis_summary: str
    changes_summary: list[str]
    duration_ms: int
    error: Optional[str] = None


class ImprovementOrchestrator:
    """
    Coordinates the improvement pipeline.

    Flow:
    1. Analyzer examines logs and feedback
    2. Versioner generates improved prompt
    3. New version is saved and activated

    Pattern: Orchestrator-Worker
    Inspired by: https://www.anthropic.com/engineering/multi-agent-research-system
    """

    def __init__(
        self,
        analyzer: "AnalyzerAgent",
        versioner: "VersionerAgent",
        prompt_manager: PromptManager,
        log_manager: LogManager,
    ):
        self.analyzer = analyzer
        self.versioner = versioner
        self.prompt_manager = prompt_manager
        self.log_manager = log_manager

    async def run(
        self,
        feedback: Feedback,
        recent_logs: list[dict],
        target_agent: str = "main_agent",
    ) -> ImprovementResult:
        """
        Run the full improvement cycle.

        Args:
            feedback: The triggering feedback
            recent_logs: Recent conversation logs for analysis
            target_agent: Which agent's prompt to improve

        Returns:
            ImprovementResult with details of what happened
        """
        start_time = time.time()
        old_version = self.prompt_manager.current_version(target_agent)

        try:
            # Step 1: Log improvement start
            await self.log_manager.log_improvement_event(
                "improvement_started",
                {
                    "trigger": "feedback",
                    "feedback_type": feedback.type,
                    "feedback_category": feedback.category,
                    "feedback_text": feedback.raw_text[:200],
                    "target_agent": target_agent,
                    "logs_count": len(recent_logs),
                }
            )

            # Step 2: Analysis
            await self.log_manager.log_improvement_event(
                "analysis_started",
                {"target_agent": target_agent}
            )

            current_prompt = self.prompt_manager.get_current(target_agent)
            analysis_result = await self.analyzer.analyze(
                feedback=feedback,
                recent_logs=recent_logs,
                current_prompt=current_prompt,
            )

            await self.log_manager.log_improvement_event(
                "analysis_completed",
                {
                    "problems_count": len(analysis_result.problems),
                    "hypotheses_count": len(analysis_result.hypotheses),
                    "confidence": analysis_result.confidence_score,
                }
            )

            # Step 3: Check confidence threshold
            if analysis_result.confidence_score < config.thresholds.improvement_confidence:
                await self.log_manager.log_improvement_event(
                    "improvement_skipped",
                    {
                        "reason": "low_confidence",
                        "confidence": analysis_result.confidence_score,
                        "threshold": config.thresholds.improvement_confidence,
                    }
                )

                return ImprovementResult(
                    success=False,
                    old_version=old_version,
                    new_version=None,
                    analysis_summary=f"Analysis confidence too low: {analysis_result.confidence_score:.2f}",
                    changes_summary=[],
                    duration_ms=self._elapsed_ms(start_time),
                    error="Low confidence - improvement skipped",
                )

            # Step 4: Generate new version
            await self.log_manager.log_improvement_event(
                "versioning_started",
                {
                    "target_agent": target_agent,
                    "hypotheses_count": len(analysis_result.hypotheses),
                }
            )

            try:
                new_version = await self.versioner.improve(
                    agent_name=target_agent,
                    analysis_result=analysis_result,
                )
            except VersioningError as e:
                await self.log_manager.log_improvement_event(
                    "versioning_failed",
                    {"error": str(e)}
                )
                raise

            # Step 5: Log success
            await self.log_manager.log_improvement_event(
                "version_created",
                {
                    "agent": target_agent,
                    "old_version": old_version,
                    "new_version": new_version.version,
                    "changes_count": len(new_version.changes),
                    "rationale": new_version.rationale[:500],
                }
            )

            duration_ms = self._elapsed_ms(start_time)

            await self.log_manager.log_improvement_event(
                "improvement_completed",
                {
                    "success": True,
                    "duration_ms": duration_ms,
                    "old_version": old_version,
                    "new_version": new_version.version,
                }
            )

            return ImprovementResult(
                success=True,
                old_version=old_version,
                new_version=new_version.version,
                analysis_summary=analysis_result.raw_analysis[:500],
                changes_summary=[c.description for c in new_version.changes],
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = self._elapsed_ms(start_time)

            await self.log_manager.log_improvement_event(
                "improvement_failed",
                {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": duration_ms,
                }
            )

            return ImprovementResult(
                success=False,
                old_version=old_version,
                new_version=None,
                analysis_summary="",
                changes_summary=[],
                duration_ms=duration_ms,
                error=str(e),
            )

    def _elapsed_ms(self, start_time: float) -> int:
        """Calculate elapsed time in milliseconds."""
        return int((time.time() - start_time) * 1000)


class ManualImprovementOrchestrator(ImprovementOrchestrator):
    """
    Orchestrator variant for manual/explicit feedback.

    Skips some checks and always attempts improvement.
    """

    async def run(
        self,
        feedback: Feedback,
        recent_logs: list[dict],
        target_agent: str = "main_agent",
    ) -> ImprovementResult:
        """
        Run improvement without confidence threshold check.
        """
        # Override confidence to ensure improvement runs
        original_threshold = config.thresholds.improvement_confidence
        config.thresholds.improvement_confidence = 0.0

        try:
            result = await super().run(feedback, recent_logs, target_agent)
        finally:
            # Restore threshold
            config.thresholds.improvement_confidence = original_threshold

        return result
