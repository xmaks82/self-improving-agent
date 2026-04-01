"""Base skill definition."""

from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable


@dataclass
class Skill:
    """A slash-command skill."""
    name: str
    description: str
    source: str = "bundled"  # bundled | user | plugin
    user_invocable: bool = True
    _get_prompt: Optional[Callable[[str], Awaitable[str]]] = field(
        default=None, repr=False
    )

    async def get_prompt(self, args: str = "") -> str:
        if self._get_prompt:
            return await self._get_prompt(args)
        return ""
