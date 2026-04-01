"""Fork subagent — background clone with inherited context.

Key properties:
- Inherits full conversation history (context reuse)
- Shares parent's system prompt (cache parity)
- Runs asynchronously in background
- Cannot fork recursively (guard against infinite spawn)
- Results reported via structured format
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

FORK_BOILERPLATE = """<fork_rules>
STOP. READ THIS FIRST.

You are a forked worker process. You are NOT the main agent.

RULES (non-negotiable):
1. You ARE the fork. Do NOT spawn sub-agents; execute directly.
2. Do NOT converse, ask questions, or suggest next steps.
3. USE your tools directly: shell, read, write, etc.
4. If you modify files, mention what changed.
5. Do NOT emit text between tool calls. Use tools silently, then report once at end.
6. Stay strictly within the directive's scope.
7. Keep report under 500 words unless directive specifies otherwise.
8. Response MUST begin with "Scope:". No preamble.

Output format:
  Scope: <your assigned scope in one sentence>
  Result: <key findings or actions taken>
  Key files: <relevant file paths>
  Files changed: <list if any were modified>
  Issues: <list if any>
</fork_rules>"""


@dataclass
class ForkResult:
    """Result of a fork execution."""
    name: str
    output: str
    success: bool
    duration_ms: int = 0
    error: Optional[str] = None


@dataclass
class ForkManager:
    """Manages background fork agents."""

    _forks: dict[str, asyncio.Task] = field(default_factory=dict)
    _results: dict[str, ForkResult] = field(default_factory=dict)
    _is_fork_child: bool = False  # Guard against recursive forking

    def is_in_fork(self) -> bool:
        """Check if we're inside a fork (prevent recursive forking)."""
        return self._is_fork_child

    async def spawn(
        self,
        name: str,
        directive: str,
        client,
        system_prompt: str,
        conversation_history: list[dict],
    ) -> str:
        """
        Fork the current agent in the background.

        Args:
            name: Short name for the fork (e.g., "research", "implement")
            directive: What the fork should do (specific scope)
            client: LLM client (shared for cache reuse)
            system_prompt: Parent's system prompt (byte-identical)
            conversation_history: Parent's full history (context inheritance)

        Returns:
            Confirmation message
        """
        if self._is_fork_child:
            return "Cannot fork: already inside a fork child."

        if name in self._forks and not self._forks[name].done():
            return f"Fork '{name}' is already running."

        task = asyncio.create_task(
            self._run_fork(name, directive, client, system_prompt, conversation_history)
        )
        self._forks[name] = task
        logger.info("Spawned fork: %s", name)
        return f"Fork '{name}' started in background."

    async def _run_fork(
        self,
        name: str,
        directive: str,
        client,
        system_prompt: str,
        parent_history: list[dict],
    ):
        """Execute a fork in background."""
        start = time.time()
        try:
            # Build fork messages: parent history + directive with boilerplate
            messages = list(parent_history)
            messages.append({
                "role": "user",
                "content": f"{FORK_BOILERPLATE}\n\nDirective: {directive}",
            })

            response = client.chat(
                messages=messages,
                system=system_prompt,
                max_tokens=4096,
            )

            duration = int((time.time() - start) * 1000)
            self._results[name] = ForkResult(
                name=name,
                output=response.content,
                success=True,
                duration_ms=duration,
            )
            logger.info("Fork '%s' completed in %dms", name, duration)

        except Exception as e:
            duration = int((time.time() - start) * 1000)
            self._results[name] = ForkResult(
                name=name,
                output="",
                success=False,
                duration_ms=duration,
                error=str(e),
            )
            logger.warning("Fork '%s' failed: %s", name, e)

    def get_result(self, name: str) -> Optional[ForkResult]:
        """Get a fork's result (None if still running or not found)."""
        return self._results.get(name)

    def get_pending(self) -> list[str]:
        """Get names of still-running forks."""
        return [
            name for name, task in self._forks.items()
            if not task.done()
        ]

    def get_completed(self) -> list[ForkResult]:
        """Get all completed fork results."""
        return list(self._results.values())

    def get_status(self) -> dict:
        """Get status of all forks."""
        return {
            "pending": self.get_pending(),
            "completed": [
                {"name": r.name, "success": r.success, "duration_ms": r.duration_ms}
                for r in self._results.values()
            ],
        }

    async def wait_all(self, timeout: float = 300) -> list[ForkResult]:
        """Wait for all pending forks to complete."""
        pending = [
            task for task in self._forks.values()
            if not task.done()
        ]
        if pending:
            await asyncio.wait(pending, timeout=timeout)
        return list(self._results.values())
