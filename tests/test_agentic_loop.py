"""Phase 1 verification: the agentic tool-loop actually executes tools.

Uses a fake LLM client (no network / API key) + a REAL ToolRegistry so the
think->tool_use->tool_result->repeat wiring is exercised end-to-end, including
real tool execution (list_directory) and real token accounting from usage.
"""

import asyncio
from pathlib import Path

from agent.agents.main_agent import MainAgent
from agent.clients.base import BaseLLMClient, LLMToolResponse, ToolCall
from agent.tools.registry import ToolRegistry


class _FakeClient(BaseLLMClient):
    provider = "fake"
    supports_tools = True

    def __init__(self):
        self.model = "fake-model"
        self._calls = 0

    def get_model_name(self) -> str:
        return self.model

    def chat(self, *a, **k):
        raise NotImplementedError

    async def stream(self, *a, **k):
        yield ""

    def chat_with_tools(self, messages, tools, system=None, max_tokens=4096):
        self._calls += 1
        if self._calls == 1:
            # First turn: ask to list the working directory.
            return LLMToolResponse(
                content="",
                tool_calls=[ToolCall(id="t1", name="list_directory", input={"path": "."})],
                input_tokens=11, output_tokens=7,
            )
        # Second turn: final answer, no tool calls -> loop ends.
        return LLMToolResponse(
            content="Done: I listed the directory.",
            tool_calls=[], input_tokens=9, output_tokens=5,
        )

    def format_tool_results(self, tool_response, tool_results):
        # Minimal shapes; our fake chat_with_tools ignores message content anyway.
        assistant = {"role": "assistant", "content": "[tool_use]"}
        user = {"role": "user", "content": "[tool_results] " + " ".join(r.content[:40] for r in tool_results)}
        return assistant, [user]


class _FakePromptManager:
    def get_current(self, name): return "You are a test agent."
    def current_version(self, name): return 1


class _FakeLogManager:
    async def log_turn(self, **k): pass
    async def log_improvement_event(self, *a, **k): pass
    async def get_recent(self, limit=50): return []


def _make_agent(tmp: Path) -> MainAgent:
    registry = ToolRegistry(working_dir=tmp, sandbox_mode=True)
    return MainAgent(
        client=_FakeClient(),
        prompt_manager=_FakePromptManager(),
        log_manager=_FakeLogManager(),
        tool_registry=registry,
    )


def test_tool_loop_executes_tool(tmp_path):
    (tmp_path / "hello.txt").write_text("hi", encoding="utf-8")
    agent = _make_agent(tmp_path)

    async def _run():
        out = []
        async for chunk in agent.process("list the files"):
            out.append(chunk)
        return "".join(out)

    output = asyncio.run(_run())

    # The tool was actually invoked and the loop reached a final answer.
    assert "[tool] list_directory" in output
    assert "Done: I listed the directory." in output
    # Loop terminated cleanly (no runaway).
    assert "max tool iterations" not in output
    # Real usage was accounted (sum of both turns' provider tokens), not a len//4 guess.
    assert agent.cost_tracker.total_tokens == 32  # (11+7) + (9+5)


def test_no_registry_falls_back(tmp_path):
    """Without a registry the agent must still work via the plain path."""
    agent = MainAgent(
        client=_FakeClient(),
        prompt_manager=_FakePromptManager(),
        log_manager=_FakeLogManager(),
        tool_registry=None,
    )

    async def _run():
        out = []
        async for chunk in agent.process("hi"):
            out.append(chunk)
        return "".join(out)

    # Plain path uses stream() (fake yields ""), so no crash and no tool markers.
    output = asyncio.run(_run())
    assert "[tool]" not in output
