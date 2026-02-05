"""Main conversational agent with feedback detection and logging."""

from typing import AsyncIterator, Optional, TYPE_CHECKING
import asyncio
import time

from .base import BaseAgent
from ..clients import BaseLLMClient, create_client
from ..storage.prompts import PromptManager
from ..storage.logs import LogManager
from ..config import config

if TYPE_CHECKING:
    from ..core.feedback import FeedbackDetector, Feedback


class MainAgent(BaseAgent):
    """
    Main conversational agent.

    Features:
    - Streaming responses
    - Multi-provider support (Anthropic, Zhipu)
    - Feedback detection
    - Conversation logging
    - Integration with improvement pipeline
    """

    def __init__(
        self,
        client: BaseLLMClient,
        prompt_manager: PromptManager,
        log_manager: LogManager,
        feedback_detector: Optional["FeedbackDetector"] = None,
    ):
        super().__init__(
            client=client,
            prompt_manager=prompt_manager,
            log_manager=log_manager,
            agent_name="main_agent",
        )
        self.feedback_detector = feedback_detector
        self._improvement_task: Optional[asyncio.Task] = None

    @property
    def model(self) -> str:
        """Get current model name."""
        return self.client.get_model_name()

    @property
    def provider(self) -> str:
        """Get current provider name."""
        return self.client.provider

    def set_model(self, model: str):
        """
        Switch to a different model.

        If the new model is from a different provider, creates a new client.
        """
        from ..clients.factory import get_provider, create_client

        current_provider = self.client.provider
        new_provider = get_provider(model)

        if new_provider == current_provider:
            # Same provider - just change model
            self.client.set_model(model)
        else:
            # Different provider - create new client
            self.client = create_client(model)

    async def process(self, message: str) -> AsyncIterator[str]:
        """
        Process a user message and yield response chunks.

        Args:
            message: User's input message

        Yields:
            Response text chunks (streaming)
        """
        start_time = time.time()

        # Get current system prompt
        system_prompt = self.get_system_prompt()
        prompt_version = self.get_prompt_version()

        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": message,
        })

        # Detect feedback (if detector available)
        feedback = None
        if self.feedback_detector:
            feedback = self.feedback_detector.detect(message)

        # Stream response
        full_response = ""
        input_tokens = 0
        output_tokens = 0

        # Use unified streaming interface
        async for chunk in self.client.stream(
            messages=self.conversation_history,
            system=system_prompt,
            max_tokens=4096,
        ):
            full_response += chunk
            yield chunk

        # Add assistant response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": full_response,
        })

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Log the turn
        await self.log_manager.log_turn(
            session_id=self.session_id,
            user_message=message,
            assistant_response=full_response,
            prompt_version=prompt_version,
            feedback=feedback,
            model=self.model,
            tokens={"input": input_tokens, "output": output_tokens},
            latency_ms=latency_ms,
        )

        # Trigger improvement if feedback detected
        if feedback and feedback.should_trigger_improvement:
            yield "\n\n---\n_Feedback detected. Starting improvement analysis..._\n"
            self._improvement_task = asyncio.create_task(
                self._trigger_improvement(feedback)
            )

    async def _trigger_improvement(self, feedback: "Feedback"):
        """
        Trigger the improvement pipeline.

        This runs asynchronously in the background.
        """
        try:
            # Import here to avoid circular imports
            from ..core.orchestrator import ImprovementOrchestrator
            from ..agents.analyzer import AnalyzerAgent
            from ..agents.versioner import VersionerAgent

            # Get recent logs for analysis
            recent_logs = await self.log_manager.get_recent(limit=50)

            # Create clients for analyzer and versioner using factory
            # This allows using any provider that supports tools (Anthropic, Groq, OpenRouter, Zhipu)
            analyzer_client = create_client(config.models.analyzer)
            versioner_client = create_client(config.models.versioner)

            analyzer = AnalyzerAgent(
                client=analyzer_client,
                prompt_manager=self.prompt_manager,
                log_manager=self.log_manager,
                model=config.models.analyzer,
            )
            versioner = VersionerAgent(
                client=versioner_client,
                prompt_manager=self.prompt_manager,
                model=config.models.versioner,
            )

            orchestrator = ImprovementOrchestrator(
                analyzer=analyzer,
                versioner=versioner,
                prompt_manager=self.prompt_manager,
                log_manager=self.log_manager,
            )

            result = await orchestrator.run(
                feedback=feedback,
                recent_logs=recent_logs,
                target_agent="main_agent",
            )

            if result.success:
                await self.log_manager.log_improvement_event(
                    "improvement_completed",
                    {
                        "old_version": result.old_version,
                        "new_version": result.new_version,
                        "changes": result.changes_summary,
                    },
                )
        except Exception as e:
            await self.log_manager.log_improvement_event(
                "improvement_failed",
                {"error": str(e)},
            )

    async def chat(self, message: str) -> AsyncIterator[str]:
        """Alias for process() for convenience."""
        async for chunk in self.process(message):
            yield chunk

    def get_improvement_status(self) -> Optional[str]:
        """Check if an improvement is in progress."""
        if self._improvement_task is None:
            return None
        if self._improvement_task.done():
            try:
                self._improvement_task.result()
                return "completed"
            except Exception as e:
                return f"failed: {e}"
        return "in_progress"
