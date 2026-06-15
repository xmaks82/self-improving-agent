"""Phase 2 verification: shell-injection block, EditFileTool, stale-detection."""

import asyncio
import time

from agent.tools.shell import RunCommandTool
from agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool
from agent.tools.file_state import FileReadStateTracker


# ---------- shell injection ----------

def _allowed(cmd, tmp):
    t = RunCommandTool(working_dir=tmp, sandbox_mode=True)
    ok, _ = t._is_command_allowed(cmd)
    return ok


def test_shell_blocks_chained_denied_command(tmp_path):
    assert _allowed("git status", tmp_path) is True
    assert _allowed("git status; rm -rf foo", tmp_path) is False   # ; chain
    assert _allowed("ls && rm x", tmp_path) is False               # && chain
    assert _allowed("ls || rm x", tmp_path) is False               # || chain


def test_shell_allows_safe_pipe(tmp_path):
    # both heads (grep, head) are in the allow-list → pipe is fine
    assert _allowed("grep foo file | head", tmp_path) is True


def test_shell_blocks_redirect_and_subshell(tmp_path):
    assert _allowed("cat f > out", tmp_path) is False              # redirection
    assert _allowed("echo $(rm x)", tmp_path) is False             # subshell


# ---------- EditFileTool ----------

def test_edit_requires_read_then_works(tmp_path):
    fs = FileReadStateTracker()
    (tmp_path / "a.txt").write_text("hello world\nhello again\n", encoding="utf-8")
    read = ReadFileTool(base_path=tmp_path, file_state=fs)
    edit = EditFileTool(base_path=tmp_path, file_state=fs)

    # edit before read → blocked
    r = asyncio.run(edit.execute(path="a.txt", old_string="world", new_string="there"))
    assert r.success is False

    asyncio.run(read.execute(path="a.txt"))

    # unique replacement works
    r = asyncio.run(edit.execute(path="a.txt", old_string="world", new_string="there"))
    assert r.success is True
    assert (tmp_path / "a.txt").read_text(encoding="utf-8").startswith("hello there")

    # ambiguous match without replace_all → blocked
    r = asyncio.run(edit.execute(path="a.txt", old_string="hello", new_string="hi"))
    assert r.success is False and "appears" in (r.error or "")

    # replace_all succeeds
    r = asyncio.run(edit.execute(path="a.txt", old_string="hello", new_string="hi", replace_all=True))
    assert r.success is True
    assert "hello" not in (tmp_path / "a.txt").read_text(encoding="utf-8")


def test_edit_missing_string(tmp_path):
    fs = FileReadStateTracker()
    (tmp_path / "c.txt").write_text("abc", encoding="utf-8")
    asyncio.run(ReadFileTool(base_path=tmp_path, file_state=fs).execute(path="c.txt"))
    r = asyncio.run(EditFileTool(base_path=tmp_path, file_state=fs).execute(
        path="c.txt", old_string="zzz", new_string="x"))
    assert r.success is False and "not found" in (r.error or "")


# ---------- stale detection ----------

def test_write_blocks_external_change(tmp_path):
    fs = FileReadStateTracker()
    f = tmp_path / "b.txt"
    f.write_text("v1", encoding="utf-8")
    asyncio.run(ReadFileTool(base_path=tmp_path, file_state=fs).execute(path="b.txt"))

    time.sleep(0.05)
    f.write_text("changed externally", encoding="utf-8")  # external edit → mtime moves

    r = asyncio.run(WriteFileTool(base_path=tmp_path, file_state=fs).execute(
        path="b.txt", content="my change"))
    assert r.success is False and "changed on disk" in (r.error or "")


# ---------- confirmation + undo ----------

def test_confirm_callback_blocks_write(tmp_path):
    from agent.tools.registry import ToolRegistry

    async def deny(name, kwargs):
        return False

    reg = ToolRegistry(working_dir=tmp_path, sandbox_mode=True, confirm_callback=deny)
    r = asyncio.run(reg.execute("write_file", path="x.txt", content="hi"))
    assert r.success is False and "Rejected" in (r.error or "")
    assert not (tmp_path / "x.txt").exists()


def test_undo_restores_created_file(tmp_path):
    from agent.tools.registry import ToolRegistry
    from agent.approval.undo import UndoManager

    um = UndoManager(history_path=tmp_path / "undo" / "h.json")
    reg = ToolRegistry(working_dir=tmp_path, sandbox_mode=True, undo_manager=um)

    r = asyncio.run(reg.execute("write_file", path="n.txt", content="created"))
    assert r.success and (tmp_path / "n.txt").read_text(encoding="utf-8") == "created"

    asyncio.run(um.undo())  # undo of file_create = delete
    assert not (tmp_path / "n.txt").exists()


# ---------- SSRF guard ----------

def test_ssrf_blocks_internal_targets(tmp_path):
    from agent.tools.web_fetch import WebFetchTool
    t = WebFetchTool()
    for u in ["http://127.0.0.1/", "http://localhost/admin",
              "http://169.254.169.254/latest/meta-data/"]:
        r = asyncio.run(t.execute(url=u))
        assert r.success is False and "SSRF" in (r.error or ""), u


# ---------- read offset/limit + truncation ----------

def test_read_offset_limit(tmp_path):
    from agent.tools.filesystem import ReadFileTool
    f = tmp_path / "big.txt"
    f.write_text("".join(f"line{i}\n" for i in range(1, 101)), encoding="utf-8")
    r = asyncio.run(ReadFileTool(base_path=tmp_path).execute(path="big.txt", offset=10, limit=3))
    assert r.success and r.output == "line10\nline11\nline12\n"


def test_read_truncates_large_file(tmp_path):
    from agent.tools.filesystem import ReadFileTool
    f = tmp_path / "huge.txt"
    f.write_text("x" * 2_100_000, encoding="utf-8")
    r = asyncio.run(ReadFileTool(base_path=tmp_path).execute(path="huge.txt"))
    assert r.success and r.metadata.get("truncated") is True


# ---------- shell guards run even outside sandbox (re-audit P1) ----------

def test_shell_guards_active_without_sandbox(tmp_path):
    from agent.tools.shell import RunCommandTool
    t = RunCommandTool(working_dir=tmp_path, sandbox_mode=False)
    ok = lambda c: t._is_command_allowed(c)[0]
    # dangerous + redirect + subshell still blocked in trusted mode
    assert ok("git status; rm -rf x") is False   # rm is always-denied
    assert ok("cat f > out") is False            # redirection blocked
    assert ok("echo $(rm x)") is False           # subshell blocked
    # but allow-list no longer restricts in non-sandbox
    assert ok("some_custom_tool --flag") is True
