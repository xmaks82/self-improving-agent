"""Plugin manifest types."""

from dataclasses import dataclass, field


@dataclass
class PluginManifest:
    name: str
    version: str
    description: str = ""
    author: str = ""
    tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
