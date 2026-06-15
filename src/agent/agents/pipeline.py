"""Agent pipeline — connects ALL agents into a coherent execution flow.

This is the central wiring that makes agents work together:

1. MainAgent processes user input (always)
2. FeedbackDetector triggers improvement pipeline (on feedback)
3. ContextCompactor compresses history (auto, >20 msgs)
4. SessionMemory maintains notes (auto, background)
5. VerificationAgent verifies after 3+ file edits (auto)
6. ExploreAgent for /explore command (manual)
7. PlanAgent for /plan command (manual)
8. ForkManager for /fork command (manual)
9. Sub-agents via orchestrator (delegated by LLM or /review etc.)
10. Skills dispatch /commit /review /simplify /debug (manual)
"""

import logging
from typing import Optional, TYPE_CHECKING

from .orchestrator import AgentOrchestrator, AgentType
from .verification import VerificationAgent
from .explore import ExploreAgent
from .plan import PlanAgent
from .fork import ForkManager
from ..core.mailbox import AgentMailbox

if TYPE_CHECKING:
    from ..clients.base import BaseLLMClient
    from ..tools.file_state import FileReadStateTracker

logger = logging.getLogger(__name__)

# Verification threshold — trigger after this many file edits
VERIFICATION_THRESHOLD = 3


class AgentPipeline:
    """
    Central pipeline connecting all agents.

    Responsibilities:
    - Initialize and register all agents
    - Auto-trigger verification after non-trivial changes
    - Provide explore/plan/fork/delegate methods
    - Manage inter-agent mailbox
    """

    def __init__(self, client: "BaseLLMClient", orchestrator: AgentOrchestrator,
                 tool_registry=None):
        self.client = client
        self.orchestrator = orchestrator
        self.tool_registry = tool_registry
        self.mailbox = AgentMailbox()
        self.fork_manager = ForkManager()

        # Specialized agents (verification gets tools to actually run checks)
        self.verification = VerificationAgent(client=client, tool_registry=tool_registry)
        self.explore = ExploreAgent(client=client)
        self.plan = PlanAgent(client=client)

        # Register sub-agents in orchestrator
        self._register_sub_agents()

        # Tracking
        self._verification_done = False

    def _register_sub_agents(self):
        """Register all sub-agents with the orchestrator."""
        from .code_reviewer import CodeReviewer
        from .test_writer import TestWriter
        from .debugger import Debugger
        from .researcher import Researcher
        from .refactorer import Refactorer

        reg = self.tool_registry
        agents = {
            AgentType.CODE_REVIEWER: CodeReviewer(client=self.client, tool_registry=reg),
            AgentType.TEST_WRITER: TestWriter(client=self.client, tool_registry=reg),
            AgentType.DEBUGGER: Debugger(client=self.client, tool_registry=reg),
            AgentType.RESEARCHER: Researcher(client=self.client, tool_registry=reg),
            AgentType.REFACTORER: Refactorer(client=self.client, tool_registry=reg),
        }
        for agent_type, agent in agents.items():
            self.orchestrator.register_agent(agent_type, agent)

        logger.info(
            "Pipeline initialized: %d sub-agents + verification + explore + plan + fork",
            len(agents),
        )

    async def maybe_verify(
        self,
        file_state: "FileReadStateTracker",
        conversation_history: list[dict],
    ) -> Optional[str]:
        """
        Auto-trigger verification if edit threshold reached.

        Returns verification report or None.
        """
        if self._verification_done:
            return None
        if file_state.edit_count < VERIFICATION_THRESHOLD:
            return None

        self._verification_done = True

        # Extract what was changed from conversation
        task_summary = self._extract_task_summary(conversation_history)
        files_changed = self._extract_changed_files(conversation_history)

        logger.info(
            "Auto-verification triggered: %d edits, files: %s",
            file_state.edit_count, files_changed,
        )

        try:
            report = await self.verification.verify(
                task_description=task_summary,
                files_changed=files_changed,
            )
            verdict = VerificationAgent.parse_verdict(report)
            return f"[Auto-Verification: {verdict}]\n{report}"
        except Exception as e:
            logger.warning("Auto-verification failed: %s", e)
            return None

    async def run_explore(self, query: str) -> str:
        """Run the Explore agent."""
        return await self.explore.explore(query)

    async def run_plan(self, task: str, context: str = "") -> str:
        """Run the Plan agent."""
        return await self.plan.plan(task, context)

    async def run_fork(
        self,
        name: str,
        directive: str,
        system_prompt: str,
        conversation_history: list[dict],
    ) -> str:
        """Fork the agent in background."""
        return await self.fork_manager.spawn(
            name=name,
            directive=directive,
            client=self.client,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
        )

    async def delegate(self, task: str, agent_type: Optional[AgentType] = None):
        """
        Delegate task to an appropriate sub-agent.

        If agent_type is None, auto-selects based on keywords.
        """
        if agent_type is None:
            agent_type = self.orchestrator.select_agent(task)
        return await self.orchestrator.delegate(task, agent_type)

    def reset_verification(self):
        """Reset verification flag (e.g., after /reset)."""
        self._verification_done = False

    def _extract_task_summary(self, history: list[dict]) -> str:
        """Extract task summary from first user message."""
        for msg in history:
            if msg["role"] == "user":
                content = msg.get("content", "")
                if not content.startswith("[Context Summary"):
                    return content[:500]
        return "Implementation task"

    def _extract_changed_files(self, history: list[dict]) -> list[str]:
        """Extract file paths mentioned in write/edit tool results."""
        import re
        files = set()
        for msg in history:
            content = msg.get("content", "")
            # Look for file write patterns
            for pattern in [
                r"Written \d+ bytes to (.+)",
                r"path['\"]:\s*['\"]([^'\"]+)",
                r"Notebook: \w+d cell .+ (.+\.ipynb)",
            ]:
                for match in re.finditer(pattern, content):
                    files.add(match.group(1))
        return list(files)[:20]  # cap at 20 files
