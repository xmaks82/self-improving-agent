"""Phase 3: MCP-server tools bridge into the agentic loop's registry."""

import asyncio

from agent.tools.registry import ToolRegistry
from agent.tools.permissions import PermissionLevel
from agent.mcp.tools import ToolDefinition


class _FakeAdapter:
    def get_tool_definitions(self):
        return [ToolDefinition(
            name="memory_search", description="search memory",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            server_name="claude-memory",
        )]


class _FakeManager:
    def __init__(self):
        self.tool_adapter = _FakeAdapter()
        self.calls = []

    async def execute_tool(self, name, args):
        self.calls.append((name, args))
        return {"success": True, "output": "found 3 memories"}


def test_mcp_tools_bridge(tmp_path):
    reg = ToolRegistry(working_dir=tmp_path, sandbox_mode=True)
    mgr = _FakeManager()

    added = reg.register_mcp_tools(mgr)
    assert added == 1
    assert "memory_search" in reg.get_tool_names()
    assert "memory_search" in [t["name"] for t in reg.get_anthropic_tools()]

    # registry.execute proxies to the MCP manager
    r = asyncio.run(reg.execute("memory_search", query="fcm"))
    assert r.success and "found 3 memories" in r.output
    assert mgr.calls == [("memory_search", {"query": "fcm"})]

    # MCP tools are auto-approved (trusted, configured servers)
    assert reg.permission_manager.get_permission("memory_search") == PermissionLevel.AUTO_APPROVE
