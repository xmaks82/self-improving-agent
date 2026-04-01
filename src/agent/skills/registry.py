"""Skill registry — manages available skills."""

from typing import Optional
from .base import Skill

_instance: Optional["SkillRegistry"] = None


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill):
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list_skills(self) -> list[Skill]:
        return [s for s in self._skills.values() if s.user_invocable]

    def list_names(self) -> list[str]:
        return [s.name for s in self._skills.values() if s.user_invocable]


def get_skill_registry() -> SkillRegistry:
    global _instance
    if _instance is None:
        _instance = SkillRegistry()
    return _instance


def register_skill(name: str, description: str, get_prompt, **kwargs):
    """Helper to register a skill in the global registry."""
    skill = Skill(name=name, description=description, _get_prompt=get_prompt, **kwargs)
    get_skill_registry().register(skill)
