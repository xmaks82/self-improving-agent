"""Diff viewer for showing changes before applying."""

import difflib
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table


@dataclass
class FileDiff:
    """Represents a diff between two versions of a file."""

    path: str
    original: str
    modified: str
    is_new: bool = False
    is_deleted: bool = False

    @property
    def unified_diff(self) -> str:
        """Generate unified diff."""
        original_lines = self.original.splitlines(keepends=True)
        modified_lines = self.modified.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{self.path}",
            tofile=f"b/{self.path}",
            lineterm="",
        )
        return "".join(diff)

    @property
    def stats(self) -> dict:
        """Get diff statistics."""
        original_lines = self.original.splitlines()
        modified_lines = self.modified.splitlines()

        # Count additions and deletions
        matcher = difflib.SequenceMatcher(None, original_lines, modified_lines)
        additions = 0
        deletions = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "insert":
                additions += j2 - j1
            elif tag == "delete":
                deletions += i2 - i1
            elif tag == "replace":
                additions += j2 - j1
                deletions += i2 - i1

        return {
            "additions": additions,
            "deletions": deletions,
            "original_lines": len(original_lines),
            "modified_lines": len(modified_lines),
        }


class DiffViewer:
    """
    Viewer for displaying file diffs.

    Shows changes in a clear, colorful format
    before applying modifications.
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def show_diff(self, diff: FileDiff, context_lines: int = 3):
        """
        Display a file diff.

        Args:
            diff: The diff to display
            context_lines: Number of context lines around changes
        """
        stats = diff.stats

        # Header
        if diff.is_new:
            title = f"[green]NEW FILE: {diff.path}[/green]"
        elif diff.is_deleted:
            title = f"[red]DELETE FILE: {diff.path}[/red]"
        else:
            title = f"[yellow]MODIFY: {diff.path}[/yellow]"

        # Stats line
        stats_line = f"[green]+{stats['additions']}[/green] [red]-{stats['deletions']}[/red]"

        # Generate unified diff
        unified = diff.unified_diff

        if unified:
            # Color the diff
            colored_lines = []
            for line in unified.splitlines():
                if line.startswith("+++") or line.startswith("---"):
                    colored_lines.append(f"[bold]{line}[/bold]")
                elif line.startswith("@@"):
                    colored_lines.append(f"[cyan]{line}[/cyan]")
                elif line.startswith("+"):
                    colored_lines.append(f"[green]{line}[/green]")
                elif line.startswith("-"):
                    colored_lines.append(f"[red]{line}[/red]")
                else:
                    colored_lines.append(line)

            content = "\n".join(colored_lines)
        else:
            content = "[dim](no changes)[/dim]"

        panel = Panel(
            content,
            title=f"{title} {stats_line}",
            border_style="blue",
        )
        self.console.print(panel)

    def show_multiple_diffs(self, diffs: list[FileDiff]):
        """Display multiple file diffs."""
        # Summary table
        table = Table(title="Changes Summary", show_header=True)
        table.add_column("File", style="cyan")
        table.add_column("Status", width=10)
        table.add_column("Changes", width=15)

        total_additions = 0
        total_deletions = 0

        for diff in diffs:
            stats = diff.stats
            total_additions += stats["additions"]
            total_deletions += stats["deletions"]

            if diff.is_new:
                status = "[green]NEW[/green]"
            elif diff.is_deleted:
                status = "[red]DELETE[/red]"
            else:
                status = "[yellow]MODIFY[/yellow]"

            changes = f"[green]+{stats['additions']}[/green] [red]-{stats['deletions']}[/red]"
            table.add_row(diff.path, status, changes)

        self.console.print(table)
        self.console.print(
            f"\n[bold]Total:[/bold] [green]+{total_additions}[/green] "
            f"[red]-{total_deletions}[/red] in {len(diffs)} file(s)\n"
        )

        # Show each diff
        for diff in diffs:
            self.show_diff(diff)
            self.console.print()

    def preview_file_write(
        self,
        path: str,
        new_content: str,
        original_content: Optional[str] = None,
    ) -> FileDiff:
        """
        Create and display a preview for a file write operation.

        Args:
            path: File path
            new_content: New content to write
            original_content: Original content (None if new file)

        Returns:
            FileDiff object
        """
        is_new = original_content is None

        diff = FileDiff(
            path=path,
            original=original_content or "",
            modified=new_content,
            is_new=is_new,
        )

        self.show_diff(diff)
        return diff

    def preview_file_delete(self, path: str, content: str) -> FileDiff:
        """
        Create and display a preview for a file delete operation.

        Args:
            path: File path
            content: Current content

        Returns:
            FileDiff object
        """
        diff = FileDiff(
            path=path,
            original=content,
            modified="",
            is_deleted=True,
        )

        self.show_diff(diff)
        return diff

    def format_diff_text(self, diff: FileDiff) -> str:
        """Format diff as plain text."""
        lines = []
        stats = diff.stats

        if diff.is_new:
            lines.append(f"NEW FILE: {diff.path}")
        elif diff.is_deleted:
            lines.append(f"DELETE FILE: {diff.path}")
        else:
            lines.append(f"MODIFY: {diff.path}")

        lines.append(f"+{stats['additions']} -{stats['deletions']}")
        lines.append("")
        lines.append(diff.unified_diff)

        return "\n".join(lines)
