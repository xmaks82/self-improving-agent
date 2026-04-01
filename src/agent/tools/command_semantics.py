"""Command-specific exit code interpretation.

Prevents false negatives: grep exit 1 = no matches (not error),
diff exit 1 = files differ (not error), etc.
"""

import shlex
from dataclasses import dataclass
from typing import Optional, Callable

CommandSemantic = Callable[[int, str, str], "CommandInterpretation"]


@dataclass
class CommandInterpretation:
    """Interpretation of a command's exit code."""
    is_error: bool
    message: Optional[str] = None


def _default(ec: int, o: str, e: str) -> CommandInterpretation:
    return CommandInterpretation(
        is_error=ec != 0,
        message=f"Command failed with exit code {ec}" if ec != 0 else None,
    )


COMMAND_SEMANTICS: dict[str, CommandSemantic] = {
    # grep/rg: 1 = no matches, 2+ = error
    "grep": lambda ec, o, e: CommandInterpretation(
        is_error=ec >= 2, message="No matches found" if ec == 1 else None),
    "rg": lambda ec, o, e: CommandInterpretation(
        is_error=ec >= 2, message="No matches found" if ec == 1 else None),
    "egrep": lambda ec, o, e: CommandInterpretation(
        is_error=ec >= 2, message="No matches found" if ec == 1 else None),
    "fgrep": lambda ec, o, e: CommandInterpretation(
        is_error=ec >= 2, message="No matches found" if ec == 1 else None),
    # diff: 1 = files differ, 2+ = error
    "diff": lambda ec, o, e: CommandInterpretation(
        is_error=ec >= 2, message="Files differ" if ec == 1 else None),
    "colordiff": lambda ec, o, e: CommandInterpretation(
        is_error=ec >= 2, message="Files differ" if ec == 1 else None),
    # find: 1 = partial success (some dirs inaccessible), 2+ = error
    "find": lambda ec, o, e: CommandInterpretation(
        is_error=ec >= 2,
        message="Some directories were inaccessible" if ec == 1 else None),
    # test/[: 1 = condition false, 2+ = error
    "test": lambda ec, o, e: CommandInterpretation(
        is_error=ec >= 2, message="Condition is false" if ec == 1 else None),
    "[": lambda ec, o, e: CommandInterpretation(
        is_error=ec >= 2, message="Condition is false" if ec == 1 else None),
    # locate: 1 = not found, 2+ = error
    "locate": lambda ec, o, e: CommandInterpretation(
        is_error=ec >= 2, message="Not found" if ec == 1 else None),
    # false: always exits 1
    "false": lambda ec, o, e: CommandInterpretation(is_error=False),
}


def extract_base_command(command: str) -> str:
    """Extract the base command name, handling pipes."""
    # Use the LAST piped segment
    segments = command.split("|")
    last = segments[-1].strip()
    try:
        parts = shlex.split(last)
        return parts[0].split("/")[-1] if parts else ""
    except ValueError:
        tokens = last.split()
        return tokens[0].split("/")[-1] if tokens else ""


def interpret_exit_code(
    command: str, exit_code: int, stdout: str = "", stderr: str = "",
) -> CommandInterpretation:
    """Interpret a command's exit code using semantic knowledge."""
    if exit_code == 0:
        return CommandInterpretation(is_error=False)
    base = extract_base_command(command)
    semantic = COMMAND_SEMANTICS.get(base, _default)
    return semantic(exit_code, stdout, stderr)
