"""Main conversational agent with feedback detection and logging."""

from typing import AsyncIterator, Optional, TYPE_CHECKING
from datetime import datetime, timezone
import asyncio
import time

from .base import BaseAgent
from ..clients import BaseLLMClient, create_client
from ..storage.prompts import PromptManager
from ..storage.logs import LogManager
from ..core.compactor import ContextCompactor
from ..core.cost_tracker import CostTracker
from ..core.session_memory import SessionMemoryManager
from .fork import ForkManager
from ..config import config

if TYPE_CHECKING:
    from .pipeline import AgentPipeline

if TYPE_CHECKING:
    from ..core.feedback import FeedbackDetector, Feedback
    from ..storage.sessions import SessionStore


class MainAgent(BaseAgent):
    """
    Main conversational agent.

    Features:
    - Streaming responses
    - Multi-provider support
    - Feedback detection
    - Conversation logging
    - Context compaction
    - Cost tracking
    - Session persistence
    - Integration with improvement pipeline
    """

    def __init__(
        self,
        client: BaseLLMClient,
        prompt_manager: PromptManager,
        log_manager: LogManager,
        feedback_detector: Optional["FeedbackDetector"] = None,
        session_store: Optional["SessionStore"] = None,
        cost_tracker: Optional[CostTracker] = None,
        pipeline: Optional["AgentPipeline"] = None,
    ):
        super().__init__(
            client=client,
            prompt_manager=prompt_manager,
            log_manager=log_manager,
            agent_name="main_agent",
        )
        self.feedback_detector = feedback_detector
        self.session_store = session_store
        self.cost_tracker = cost_tracker or CostTracker()
        self.compactor = ContextCompactor(client)
        self.session_memory = SessionMemoryManager(client, self.session_id)
        self.pipeline = pipeline
        self.fork_manager = pipeline.fork_manager if pipeline else ForkManager()
        self._improvement_task: Optional[asyncio.Task] = None
        self._created_at = datetime.now(timezone.utc).isoformat() + "Z"

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

    async def fork(self, name: str, directive: str) -> str:
        """Fork this agent in the background with inherited context."""
        if self.pipeline:
            return await self.pipeline.run_fork(
                name, directive, self.get_system_prompt(), self.conversation_history
            )
        return await self.fork_manager.spawn(
            name=name, directive=directive, client=self.client,
            system_prompt=self.get_system_prompt(),
            conversation_history=self.conversation_history,
        )

    async def plan(self, task: str, context: str = "") -> str:
        """Run the Plan agent for architecture/design tasks."""
        if self.pipeline:
            return await self.pipeline.run_plan(task, context)
        from .plan import PlanAgent
        return await PlanAgent(self.client).plan(task, context)

    async def explore(self, query: str) -> str:
        """Run the Explore agent for codebase search."""
        if self.pipeline:
            return await self.pipeline.run_explore(query)
        from .explore import ExploreAgent
        return await ExploreAgent(self.client).explore(query)

    async def delegate(self, task: str, agent_type=None):
        """Delegate task to a sub-agent via the orchestrator."""
        if self.pipeline:
            return await self.pipeline.delegate(task, agent_type)
        return None

    async def compact_history(self) -> tuple[int, int]:
        """
        Compact conversation history.

        Returns:
            (old_count, new_count) of messages
        """
        old_count = len(self.conversation_history)
        system_prompt = self.get_system_prompt()
        self.conversation_history = await self.compactor.compact(
            self.conversation_history, system_prompt
        )
        return old_count, len(self.conversation_history)

    async def save_session(self):
        """Save current session to persistent storage."""
        if not self.session_store or not self.conversation_history:
            return
        from ..storage.sessions import SessionRecord

        # Use first user message as summary
        summary = ""
        for msg in self.conversation_history:
            if msg["role"] == "user" and not msg["content"].startswith("[Context Summary"):
                summary = msg["content"][:100]
                break
        if not summary:
            summary = f"Session {self.session_id[:8]}"

        record = SessionRecord(
            session_id=self.session_id,
            model=self.model,
            provider=self.provider,
            prompt_version=self.get_prompt_version(),
            conversation_history=self.conversation_history,
            created_at=self._created_at,
            updated_at=datetime.now(timezone.utc).isoformat() + "Z",
            turn_count=len(self.conversation_history) // 2,
            summary=summary,
        )
        await self.session_store.save(record)

    async def load_session(self, session_id: str) -> bool:
        """Load a saved session. Returns True if successful."""
        if not self.session_store:
            return False
        record = await self.session_store.load(session_id)
        if not record:
            return False
        self.conversation_history = record.conversation_history
        self.session_id = record.session_id
        self._created_at = record.created_at
        # Try to switch to the saved model
        try:
            self.set_model(record.model)
        except Exception:
            pass  # Keep current model if saved one unavailable
        return True

    async def process(self, message: str) -> AsyncIterator[str]:
        """
        Process a user message and yield response chunks.

        Args:
            message: User's input message

        Yields:
            Response text chunks (streaming)
        """
        start_time = time.time()

        # Auto-compact if needed
        if self.compactor.should_compact(self.conversation_history):
            await self.compact_history()

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

        # Use unified streaming interface
        async for chunk in self.client.stream(
            messages=self.conversation_history,
            system=system_prompt,
            max_tokens=4096,
        ):
            full_response += chunk
            yield chunk

        # Estimate tokens from text lengths (streaming doesn't return usage)
        input_text = system_prompt + "".join(
            m.get("content", "") for m in self.conversation_history
        )
        input_tokens = len(input_text) // 4
        output_tokens = len(full_response) // 4

        # Record cost
        self.cost_tracker.record(
            self.provider, self.model, input_tokens, output_tokens
        )

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

        # Auto-save session
        await self.save_session()

        # Background session memory extraction
        est_tokens = sum(len(m.get("content", "")) for m in self.conversation_history) // 4
        if self.session_memory.should_extract(est_tokens):
            asyncio.create_task(self.session_memory.extract(self.conversation_history))

        # Auto-verification after 3+ file edits
        if self.pipeline:
            from ..tools.file_state import FileReadStateTracker
            # Access file_state from pipeline's orchestrator if available
            registry = getattr(self, '_tool_registry', None)
            if registry and hasattr(registry, 'file_state'):
                report = await self.pipeline.maybe_verify(
                    registry.file_state, self.conversation_history
                )
                if report:
                    yield f"\n\n---\n{report}\n"

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
