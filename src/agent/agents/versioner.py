"""Versioner agent for generating improved system prompts."""

from dataclasses import dataclass, field
from typing import Optional
import json

from anthropic import Anthropic

from .analyzer import AnalysisResult
from ..storage.prompts import PromptManager
from ..config import config


@dataclass
class PromptChange:
    """A single change to the prompt."""
    section: str
    change_type: str  # "add", "modify", "remove"
    description: str
    hypothesis_id: str


@dataclass
class PromptVersion:
    """A new version of the prompt."""
    version: int
    content: str
    changes: list[PromptChange]
    hypothesis_ids: list[str]
    rationale: str


class VersionerAgent:
    """
    Agent for generating improved system prompts based on analysis.

    Uses tools to read prompts, validate changes, and create new versions.
    """

    TOOLS = [
        {
            "name": "get_current_prompt",
            "description": "Get the current system prompt for an agent",
            "input_schema": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "enum": ["main_agent", "analyzer", "versioner"],
                        "description": "Agent name"
                    }
                },
                "required": ["agent_name"]
            }
        },
        {
            "name": "get_prompt_diff",
            "description": "Compare two versions of a prompt",
            "input_schema": {
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string"},
                    "version_a": {"type": "integer"},
                    "version_b": {"type": "integer"}
                },
                "required": ["agent_name", "version_a", "version_b"]
            }
        },
        {
            "name": "validate_prompt",
            "description": "Validate a prompt for length, format, and potential issues",
            "input_schema": {
                "type": "object",
                "properties": {
                    "prompt_content": {
                        "type": "string",
                        "description": "The prompt content to validate"
                    }
                },
                "required": ["prompt_content"]
            }
        },
        {
            "name": "create_prompt_version",
            "description": "Create a new version of the prompt",
            "input_schema": {
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string"},
                    "new_prompt": {
                        "type": "string",
                        "description": "The complete new prompt content"
                    },
                    "changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "section": {"type": "string"},
                                "change_type": {
                                    "type": "string",
                                    "enum": ["add", "modify", "remove"]
                                },
                                "description": {"type": "string"},
                                "hypothesis_id": {"type": "string"}
                            },
                            "required": ["section", "change_type", "description"]
                        }
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Overall explanation of the improvements"
                    }
                },
                "required": ["agent_name", "new_prompt", "changes", "rationale"]
            }
        }
    ]

    # Maximum prompt length in characters (roughly 4000 tokens)
    MAX_PROMPT_LENGTH = 16000

    def __init__(
        self,
        client: Anthropic,
        prompt_manager: PromptManager,
        model: Optional[str] = None,
    ):
        # Note: VersionerAgent doesn't need log_manager
        self.client = client
        self.prompt_manager = prompt_manager
        self.model = model or config.models.versioner
        self.agent_name = "versioner"

    def get_system_prompt(self) -> str:
        """Get the versioner's system prompt."""
        return self.prompt_manager.get_current(self.agent_name)

    async def improve(
        self,
        agent_name: str,
        analysis_result: AnalysisResult,
    ) -> PromptVersion:
        """
        Generate an improved prompt based on analysis.

        Args:
            agent_name: Name of the agent whose prompt to improve
            analysis_result: Analysis with problems and hypotheses

        Returns:
            PromptVersion with the new prompt
        """
        system_prompt = self.get_system_prompt()
        current_prompt = self.prompt_manager.get_current(agent_name)
        current_version = self.prompt_manager.current_version(agent_name)

        # Format analysis for the prompt
        problems_text = "\n".join([
            f"- [{p.id}] {p.description} (severity: {p.severity})"
            for p in analysis_result.problems
        ])

        hypotheses_text = "\n".join([
            f"- [{h.id}] {h.suggestion} -> {h.expected_effect} (confidence: {h.confidence})"
            f"\n  Addresses: {', '.join(h.problem_ids)}"
            for h in analysis_result.hypotheses
        ])

        messages = [{
            "role": "user",
            "content": f"""Improve the system prompt for agent "{agent_name}" based on the analysis.

## Current Prompt (v{current_version})
```
{current_prompt}
```

## Analysis Results

### Problems Identified
{problems_text}

### Improvement Hypotheses
{hypotheses_text}

### Analysis Summary
{analysis_result.raw_analysis[:2000]}

## Instructions
1. First, use validate_prompt to check the current prompt
2. Make targeted improvements based on the hypotheses
3. Keep changes minimal but effective
4. Use create_prompt_version to save the improved prompt

Remember:
- Don't remove existing functionality without clear reason
- Maintain the overall structure and tone
- Each change should address a specific hypothesis
- Maximum prompt length: {self.MAX_PROMPT_LENGTH} characters
"""
        }]

        new_version = None

        # Agentic loop
        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=system_prompt,
                tools=self.TOOLS,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                tool_results = await self._execute_tools(response.content, agent_name)
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

                # Check if create_prompt_version was called
                for block in response.content:
                    if block.type == "tool_use" and block.name == "create_prompt_version":
                        new_version = await self._save_version(block.input, analysis_result)
                        break

                if new_version:
                    break
            else:
                # Agent finished without creating version - error
                raise VersioningError(
                    "Versioner did not create a new version. "
                    "The agent should use the create_prompt_version tool."
                )

        return new_version

    async def _execute_tools(self, content: list, target_agent: str) -> list:
        """Execute tool calls and return results."""
        results = []

        for block in content:
            if block.type != "tool_use":
                continue

            tool_name = block.name
            tool_input = block.input
            tool_id = block.id

            result = await self._execute_tool(tool_name, tool_input, target_agent)

            results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps(result, ensure_ascii=False),
            })

        return results

    async def _execute_tool(self, name: str, input_data: dict, target_agent: str) -> dict:
        """Execute a single tool."""
        if name == "get_current_prompt":
            agent = input_data.get("agent_name", target_agent)
            prompt = self.prompt_manager.get_current(agent)
            version = self.prompt_manager.current_version(agent)
            return {
                "prompt": prompt,
                "version": version,
                "length": len(prompt),
            }

        elif name == "get_prompt_diff":
            diff = self.prompt_manager.get_diff(
                input_data["agent_name"],
                input_data["version_a"],
                input_data["version_b"],
            )
            return diff

        elif name == "validate_prompt":
            prompt = input_data["prompt_content"]
            issues = []

            # Check length
            if len(prompt) > self.MAX_PROMPT_LENGTH:
                issues.append(f"Prompt too long: {len(prompt)} chars (max: {self.MAX_PROMPT_LENGTH})")

            # Check for common issues
            if not prompt.strip():
                issues.append("Prompt is empty")

            if "{{" in prompt or "}}" in prompt:
                issues.append("Prompt contains template syntax that may not be filled")

            # Check structure
            has_sections = "##" in prompt or "**" in prompt
            if len(prompt) > 500 and not has_sections:
                issues.append("Long prompt without clear sections - consider adding headers")

            return {
                "valid": len(issues) == 0,
                "length": len(prompt),
                "issues": issues,
                "estimated_tokens": len(prompt) // 4,  # Rough estimate
            }

        elif name == "create_prompt_version":
            # Validate before saving
            validation = await self._execute_tool(
                "validate_prompt",
                {"prompt_content": input_data["new_prompt"]},
                target_agent,
            )

            if not validation["valid"]:
                return {
                    "error": "Validation failed",
                    "issues": validation["issues"],
                }

            # Will be handled in _save_version
            return {"status": "version_created"}

        return {"error": f"Unknown tool: {name}"}

    async def _save_version(
        self,
        input_data: dict,
        analysis_result: AnalysisResult,
    ) -> PromptVersion:
        """Save the new prompt version."""
        agent_name = input_data["agent_name"]
        new_prompt = input_data["new_prompt"]
        changes_data = input_data.get("changes", [])
        rationale = input_data.get("rationale", "")

        # Parse changes
        changes = [
            PromptChange(
                section=c.get("section", ""),
                change_type=c.get("change_type", "modify"),
                description=c.get("description", ""),
                hypothesis_id=c.get("hypothesis_id", ""),
            )
            for c in changes_data
        ]

        # Create improvement info
        improvement_info = {
            "trigger": "feedback",
            "feedback_summary": analysis_result.problems[0].description if analysis_result.problems else "",
            "hypothesis_ids": [h.id for h in analysis_result.hypotheses],
            "analyzer_confidence": analysis_result.confidence_score,
        }

        # Save version
        new_version_num = self.prompt_manager.create_version(
            agent_name=agent_name,
            new_prompt=new_prompt,
            changes=[
                {
                    "section": c.section,
                    "change_type": c.change_type,
                    "description": c.description,
                    "hypothesis_id": c.hypothesis_id,
                }
                for c in changes
            ],
            improvement_info=improvement_info,
            author="versioner_agent",
        )

        return PromptVersion(
            version=new_version_num,
            content=new_prompt,
            changes=changes,
            hypothesis_ids=[h.id for h in analysis_result.hypotheses],
            rationale=rationale,
        )

    async def process(self, message: str):
        """Not used directly - use improve() instead."""
        raise NotImplementedError("Use improve() method instead")


class VersioningError(Exception):
    """Error during prompt versioning."""
    pass
