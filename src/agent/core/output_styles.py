"""Switchable output styles for the agent."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class OutputStyleConfig:
    name: str
    description: str
    prompt: str


OUTPUT_STYLES: dict[str, Optional[OutputStyleConfig]] = {
    "default": None,
    "explanatory": OutputStyleConfig(
        name="Explanatory",
        description="Explains implementation choices and codebase patterns",
        prompt="You explain your implementation choices. Before and after writing code, "
               "provide brief educational insights about patterns, trade-offs, and conventions.",
    ),
    "concise": OutputStyleConfig(
        name="Concise",
        description="Minimal output, just actions and results",
        prompt="Be extremely brief. Output only actions taken and their results. "
               "No explanations unless asked. One-line status updates. Skip preamble entirely.",
    ),
    "teaching": OutputStyleConfig(
        name="Teaching",
        description="Detailed explanations for learning",
        prompt="Explain every step as if teaching a junior developer. Include why each "
               "decision was made, what alternatives exist, and what concepts are at play.",
    ),
}

_current_style: str = "default"


def get_current_style() -> Optional[OutputStyleConfig]:
    return OUTPUT_STYLES.get(_current_style)


def set_style(name: str) -> bool:
    global _current_style
    if name in OUTPUT_STYLES:
        _current_style = name
        return True
    return False


def get_style_name() -> str:
    return _current_style


def list_styles() -> list[dict]:
    return [
        {
            "name": k,
            "description": v.description if v else "Default agent behavior",
            "active": k == _current_style,
        }
        for k, v in OUTPUT_STYLES.items()
    ]
