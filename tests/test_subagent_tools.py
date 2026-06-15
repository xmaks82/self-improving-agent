"""Phase 1 P1: sub-agents run a real tool-loop when a registry is wired."""

import asyncio
from agent.agents.code_reviewer import CodeReviewer
from agent.tools.registry import ToolRegistry
from agent.clients.base import BaseLLMClient, LLMToolResponse, ToolCall


class _FakeClient(BaseLLMClient):
    provider = "fake"
    supports_tools = True

    def __init__(self):
        self.model = "f"
        self._n = 0

    def get_model_name(self):
        return "f"

    def chat(self, *a, **k):
        raise NotImplementedError

    async def stream(self, *a, **k):
        yield ""

    def chat_with_tools(self, messages, tools, system=None, max_tokens=4096):
        self._n += 1
        if self._n == 1:
            return LLMToolResponse(
                content="", tool_calls=[ToolCall(id="t1", name="list_directory", input={"path": "."})],
                input_tokens=1, output_tokens=1)
        return LLMToolResponse(content="Review done.", tool_calls=[], input_tokens=1, output_tokens=1)

    def format_tool_results(self, tool_response, tool_results):
        return {"role": "assistant", "content": "x"}, [{"role": "user", "content": "r"}]


def test_subagent_runs_tool_loop(tmp_path):
    (tmp_path / "f.txt").write_text("hi", encoding="utf-8")
    reg = ToolRegistry(working_dir=tmp_path, sandbox_mode=True)
    agent = CodeReviewer(client=_FakeClient(), tool_registry=reg)
    out = asyncio.run(agent.execute("review the directory", {}))
    assert "Review done." in out


def test_subagent_without_registry_uses_plain(tmp_path):
    # No registry → falls back to plain streaming (fake yields ""), no crash.
    agent = CodeReviewer(client=_FakeClient(), tool_registry=None)
    out = asyncio.run(agent.execute("review", {}))
    assert isinstance(out, str)
