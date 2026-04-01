"""Jupyter notebook cell editing tool."""

import json
from pathlib import Path
from typing import Optional

from .base import BaseTool, ToolResult
from .file_state import FileReadStateTracker


class NotebookEditTool(BaseTool):
    """Edit Jupyter notebook cells (replace, insert, delete)."""

    name = "notebook_edit"
    description = "Edit a Jupyter notebook cell by index or ID."
    parameters = {
        "type": "object",
        "properties": {
            "notebook_path": {"type": "string", "description": "Path to .ipynb file."},
            "edit_mode": {
                "type": "string", "enum": ["replace", "insert", "delete"],
                "description": "Edit mode. Default: replace.",
            },
            "cell_number": {"type": "integer", "description": "Cell index (0-based)."},
            "new_source": {"type": "string", "description": "New cell source content."},
            "cell_type": {
                "type": "string", "enum": ["code", "markdown"],
                "description": "Cell type (required for insert).",
            },
        },
        "required": ["notebook_path", "edit_mode"],
    }

    def __init__(self, file_state: Optional[FileReadStateTracker] = None):
        self.file_state = file_state

    async def execute(
        self, notebook_path: str, edit_mode: str = "replace",
        cell_number: int = 0, new_source: str = "",
        cell_type: str = "code", **kwargs,
    ) -> ToolResult:
        path = Path(notebook_path)
        if path.suffix != ".ipynb":
            return ToolResult.fail("File must be a .ipynb notebook.")
        if not path.exists():
            return ToolResult.fail(f"Notebook not found: {notebook_path}")
        if self.file_state and not self.file_state.has_been_read(str(path.resolve())):
            return ToolResult.fail("Read the notebook first before editing.")

        try:
            nb = json.loads(path.read_text())
        except json.JSONDecodeError:
            return ToolResult.fail("Invalid notebook JSON.")

        cells = nb.get("cells", [])

        if edit_mode == "delete":
            if cell_number < 0 or cell_number >= len(cells):
                return ToolResult.fail(f"Cell index {cell_number} out of range (0-{len(cells)-1}).")
            cells.pop(cell_number)

        elif edit_mode == "insert":
            new_cell = {
                "cell_type": cell_type,
                "source": new_source,
                "metadata": {},
                **({"outputs": [], "execution_count": None} if cell_type == "code" else {}),
            }
            insert_at = min(cell_number + 1, len(cells))
            cells.insert(insert_at, new_cell)

        elif edit_mode == "replace":
            if cell_number < 0 or cell_number >= len(cells):
                return ToolResult.fail(f"Cell index {cell_number} out of range (0-{len(cells)-1}).")
            cells[cell_number]["source"] = new_source
            if cells[cell_number].get("cell_type") == "code":
                cells[cell_number]["outputs"] = []
                cells[cell_number]["execution_count"] = None

        nb["cells"] = cells
        path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")

        if self.file_state:
            self.file_state.record_write(str(path.resolve()))

        return ToolResult.ok(f"Notebook: {edit_mode}d cell {cell_number}. Total cells: {len(cells)}.")
