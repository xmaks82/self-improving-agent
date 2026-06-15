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
