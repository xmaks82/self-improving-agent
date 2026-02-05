"""Agent orchestrator for coordinating sub-agents."""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

from ..clients import BaseLLMClient
from ..storage.prompts import PromptManager
from ..storage.logs import LogManager


class AgentType(Enum):
    """Types of specialized agents."""

    CODE_REVIEWER = "code_reviewer"
    TEST_WRITER = "test_writer"
    DEBUGGER = "debugger"
    RESEARCHER = "researcher"
    REFACTORER = "refactorer"


@dataclass
class AgentResult:
    """Result from an agent execution."""

    agent_type: AgentType
    success: bool
    output: str
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_type.value,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class Task:
    """A task for agent execution."""

    description: str
    agent_type: AgentType
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 0


class AgentOrchestrator:
    """
    Orchestrator for coordinating specialized sub-agents.

    Manages:
    - Agent registration and lifecycle
    - Task delegation to appropriate agents
    - Parallel and sequential execution
    - Result aggregation
    """

    def __init__(
        self,
        client: BaseLLMClient,
        prompt_manager: PromptManager,
        log_manager: LogManager,
    ):
        self.client = client
        self.prompt_manager = prompt_manager
        self.log_manager = log_manager
        self._agents: dict[AgentType, Any] = {}

    def register_agent(self, agent_type: AgentType, agent: Any):
        """Register a sub-agent."""
        self._agents[agent_type] = agent

    def get_agent(self, agent_type: AgentType) -> Optional[Any]:
        """Get registered agent by type."""
        return self._agents.get(agent_type)

    def list_agents(self) -> list[AgentType]:
        """List registered agent types."""
        return list(self._agents.keys())

    async def delegate(
        self,
        task: str,
        agent_type: AgentType,
        context: Optional[dict] = None,
    ) -> AgentResult:
        """
        Delegate a task to a specific agent.

        Args:
            task: Task description
            agent_type: Type of agent to use
            context: Additional context

        Returns:
            AgentResult
        """
        agent = self._agents.get(agent_type)
        if not agent:
            return AgentResult(
                agent_type=agent_type,
                success=False,
                output="",
                error=f"Agent not registered: {agent_type.value}",
            )

        try:
            result = await agent.execute(task, context or {})
            return AgentResult(
                agent_type=agent_type,
                success=True,
                output=result,
                metadata={"context": context},
            )
        except Exception as e:
            return AgentResult(
                agent_type=agent_type,
                success=False,
                output="",
                error=str(e),
            )

    async def parallel_execute(
        self,
        tasks: list[Task],
    ) -> list[AgentResult]:
        """
        Execute multiple tasks in parallel.

        Args:
            tasks: List of tasks

        Returns:
            List of results
        """
        async def execute_task(task: Task) -> AgentResult:
            return await self.delegate(
                task.description,
                task.agent_type,
                task.context,
            )

        results = await asyncio.gather(
            *[execute_task(t) for t in tasks],
            return_exceptions=True,
        )

        # Convert exceptions to AgentResult
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(AgentResult(
                    agent_type=tasks[i].agent_type,
                    success=False,
                    output="",
                    error=str(result),
                ))
            else:
                final_results.append(result)

        return final_results

    async def sequential_execute(
        self,
        tasks: list[Task],
        stop_on_failure: bool = False,
    ) -> list[AgentResult]:
        """
        Execute tasks sequentially.

        Args:
            tasks: List of tasks
            stop_on_failure: Stop if a task fails

        Returns:
            List of results
        """
        results = []

        for task in tasks:
            result = await self.delegate(
                task.description,
                task.agent_type,
                task.context,
            )
            results.append(result)

            if stop_on_failure and not result.success:
                break

        return results

    async def chain_execute(
        self,
        tasks: list[Task],
    ) -> AgentResult:
        """
        Execute tasks in chain, passing output to next task.

        Args:
            tasks: List of tasks

        Returns:
            Final result
        """
        context = {}
        last_result = None

        for task in tasks:
            # Merge context
            task_context = {**context, **task.context}

            result = await self.delegate(
                task.description,
                task.agent_type,
                task_context,
            )

            if not result.success:
                return result

            # Pass output to next task
            context["previous_output"] = result.output
            last_result = result

        return last_result or AgentResult(
            agent_type=AgentType.CODE_REVIEWER,
            success=False,
            output="",
            error="No tasks executed",
        )

    def select_agent(self, task_description: str) -> AgentType:
        """
        Select appropriate agent based on task description.

        Args:
            task_description: Description of the task

        Returns:
            Suggested agent type
        """
        desc_lower = task_description.lower()

        # Keywords for each agent type
        keywords = {
            AgentType.CODE_REVIEWER: [
                "review", "check", "analyze code", "look at",
                "examine", "audit", "inspect"
            ],
            AgentType.TEST_WRITER: [
                "test", "unit test", "integration test",
                "write test", "create test", "testing"
            ],
            AgentType.DEBUGGER: [
                "debug", "fix", "error", "bug", "issue",
                "problem", "crash", "exception", "traceback"
            ],
            AgentType.RESEARCHER: [
                "search", "find", "research", "look up",
                "documentation", "how to", "what is"
            ],
            AgentType.REFACTORER: [
                "refactor", "improve", "optimize", "clean up",
                "restructure", "simplify"
            ],
        }

        # Score each agent type
        scores = {}
        for agent_type, words in keywords.items():
            score = sum(1 for word in words if word in desc_lower)
            if score > 0:
                scores[agent_type] = score

        if scores:
            return max(scores, key=scores.get)

        # Default to code reviewer
        return AgentType.CODE_REVIEWER

    @property
    def agent_count(self) -> int:
        """Number of registered agents."""
        return len(self._agents)

    def __repr__(self) -> str:
        return f"AgentOrchestrator({self.agent_count} agents)"
