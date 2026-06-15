"""Shared bounded tool-loop for non-streaming agents (sub-agents, verification).

Same think→tool_use→tool_result→repeat contract as MainAgent.process(), but
collects the final text instead of streaming it. Bounded iterations, anti-loop
guard, and tool errors returned AS tool_result so the model can recover.
"""
import asyncio
import os

MAX_TOOL_ITERATIONS = int(os.environ.get("AGENT_SUBAGENT_MAX_ITERATIONS", "15"))
MAX_TOOL_OUTPUT = int(os.environ.get("AGENT_MAX_TOOL_OUTPUT", "20000"))


async def run_tool_loop(client, registry, messages, system=None,
                        max_iterations: int = MAX_TOOL_ITERATIONS) -> str:
    """Run the agentic tool-loop and return the final assistant text."""
    from ..clients.base import ToolResult as _ToolResultMsg

    tools = registry.get_anthropic_tools()
    work = list(messages)
    parts: list[str] = []
    last_sig = None
    repeat = 0

    for _step in range(max_iterations):
        resp = await asyncio.to_thread(
            client.chat_with_tools, work, tools, system, 4096
        )
        if resp.content:
            parts.append(resp.content)
        if not resp.has_tool_calls:
            break

        sig = tuple((tc.name, repr(tc.input)) for tc in resp.tool_calls)
        repeat = repeat + 1 if sig == last_sig else 0
        last_sig = sig
        if repeat >= 1:
            parts.append("\n[aborted: repeated identical tool calls]")
            break

        results = []
        for tc in resp.tool_calls:
            try:
                tr = await registry.execute(tc.name, **(tc.input or {}))
                out = tr.output if tr.success else f"ERROR: {tr.error or ''}\n{tr.output or ''}".strip()
            except Exception as e:
                out = f"ERROR: tool '{tc.name}' raised: {e}"
            results.append(_ToolResultMsg(
                tool_call_id=tc.id,
                content=(out or "(no output)")[:MAX_TOOL_OUTPUT],
            ))

        assistant_msg, tool_msgs = client.format_tool_results(resp, results)
        work.append(assistant_msg)
        work.extend(tool_msgs)

    return "".join(parts)
