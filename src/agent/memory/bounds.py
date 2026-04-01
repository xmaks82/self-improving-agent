"""Memory bounds enforcement (200 lines / 25KB cap)."""

from dataclasses import dataclass

MAX_MEMORY_LINES = 200
MAX_MEMORY_BYTES = 25_000

TRUNCATION_WARNING = (
    "\n\n[WARNING: Memory content was truncated. "
    "Lines after {max_lines} or bytes after {max_bytes} were removed. "
    "Keep the memory index concise.]"
)


@dataclass
class TruncationResult:
    """Result of memory truncation."""
    content: str
    line_count: int
    byte_count: int
    was_line_truncated: bool
    was_byte_truncated: bool


def truncate_memory_content(
    raw: str,
    max_lines: int = MAX_MEMORY_LINES,
    max_bytes: int = MAX_MEMORY_BYTES,
) -> TruncationResult:
    """
    Truncate memory content to line AND byte caps.

    Line-truncates first (natural boundary), then byte-truncates
    at the last newline before the cap.
    """
    lines = raw.split("\n")
    original_line_count = len(lines)

    # Step 1: Line truncation
    was_line_truncated = False
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        was_line_truncated = True

    content = "\n".join(lines)

    # Step 2: Byte truncation
    was_byte_truncated = False
    encoded = content.encode("utf-8")
    if len(encoded) > max_bytes:
        # Truncate at the last newline before the byte cap
        truncated = encoded[:max_bytes]
        last_newline = truncated.rfind(b"\n")
        if last_newline > 0:
            truncated = truncated[:last_newline]
        content = truncated.decode("utf-8", errors="replace")
        was_byte_truncated = True

    # Add warning if truncated
    if was_line_truncated or was_byte_truncated:
        content += TRUNCATION_WARNING.format(
            max_lines=max_lines, max_bytes=max_bytes
        )

    return TruncationResult(
        content=content,
        line_count=content.count("\n") + 1,
        byte_count=len(content.encode("utf-8")),
        was_line_truncated=was_line_truncated,
        was_byte_truncated=was_byte_truncated,
    )
