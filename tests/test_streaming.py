"""Per-token streaming with tool-use (MainAgent stream path)."""

import asyncio
from agent.agents.main_agent import MainAgent
from agent.clients.base import BaseLLMClient, LLMToolResponse, ToolCall
from agent.tools.registry import ToolRegistry


class _FakeStreamClient(BaseLLMClient):
    provider = "fake"
    supports_tools = True
    supports_stream_tools = True

    def __init__(self):
        self.model = "f"
        self._n = 0

    def get_model_name(self):
        return "f"

    def chat(self, *a, **k):
        raise NotImplementedError

    async def stream(self, *a, **k):
        yield ""

    def chat_with_tools(self, *a, **k):
        raise AssertionError("streaming path should be used, not chat_with_tools")

    async def stream_with_tools(self, messages, tools, system=None, max_tokens=4096):
        self._n += 1
        if self._n == 1:
            yield "Let me "
            yield "check.\n"
            r = LLMToolResponse(content="Let me check.\n",
                                tool_calls=[ToolCall(id="t1", name="list_directory", input={"path": "."})],
                                input_tokens=2, output_tokens=2)
            r._raw_response = {"x": 1}
            yield r
        else:
            yield "Done streaming."
            r = LLMToolResponse(content="Done streaming.", tool_calls=[],
                                input_tokens=1, output_tokens=1)
            r._raw_response = {"x": 2}
            yield r

    def format_tool_results(self, tool_response, tool_results):
        return {"role": "assistant", "content": "a"}, [{"role": "user", "content": "r"}]


class _FakePM:
    def get_current(self, name): return "You are test."
    def current_version(self, name): return 1


class _FakeLM:
    async def log_turn(self, **k): pass
    async def log_improvement_event(self, *a, **k): pass
    async def get_recent(self, limit=50): return []


def test_streaming_tool_loop(tmp_path):
    (tmp_path / "x.txt").write_text("hi", encoding="utf-8")
    reg = ToolRegistry(working_dir=tmp_path, sandbox_mode=True)
    agent = MainAgent(client=_FakeStreamClient(), prompt_manager=_FakePM(),
                      log_manager=_FakeLM(), tool_registry=reg)

    async def _run():
        chunks = []
        async for c in agent.process("go"):
            chunks.append(c)
        return chunks

    chunks = asyncio.run(_run())
    joined = "".join(chunks)
    # streamed deltas present (and only once)
    assert "Let me " in chunks and "check.\n" in chunks
    assert "Done streaming." in joined
    assert "[tool] list_directory" in joined
    assert joined.count("Done streaming.") == 1
    # real usage accounted across both streamed steps
    assert agent.cost_tracker.total_tokens == 6
