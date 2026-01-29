"""Analyzer agent for reviewing logs and formulating improvement hypotheses."""

from dataclasses import dataclass, field
from typing import Optional
import json

from anthropic import Anthropic

from ..storage.prompts import PromptManager
from ..storage.logs import LogManager
from ..core.feedback import Feedback
from ..config import config


@dataclass
class Problem:
    """An identified problem from analysis."""
    id: str
    description: str
    severity: str  # "critical", "important", "cosmetic"
    examples: list[str] = field(default_factory=list)


@dataclass
class Hypothesis:
    """An improvement hypothesis."""
    id: str
    problem_ids: list[str]
    suggestion: str
    expected_effect: str
    confidence: float


@dataclass
class AnalysisResult:
    """Result of the analysis process."""
    problems: list[Problem]
    hypotheses: list[Hypothesis]
    evidence: list[dict]
    confidence_score: float
    raw_analysis: str


class AnalyzerAgent:
    """
    Agent for analyzing conversation logs and formulating improvement hypotheses.

    Uses tools to search logs and submit structured analysis.
    """

    TOOLS = [
        {
            "name": "search_logs",
            "description": "Search conversation logs by keywords or patterns",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (keywords or phrases)"
                    },
                    "date_range": {
                        "type": "string",
                        "enum": ["last_day", "last_week", "last_month", "all"],
                        "description": "Date range to search"
                    },
                    "feedback_type": {
                        "type": "string",
                        "enum": ["positive", "negative", "all"],
                        "description": "Filter by feedback type"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "get_conversation",
            "description": "Get full conversation by session ID",
            "input_schema": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID to retrieve"
                    }
                },
                "required": ["session_id"]
            }
        },
        {
            "name": "get_prompt_history",
            "description": "Get history of prompt versions for an agent",
            "input_schema": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "enum": ["main_agent", "analyzer", "versioner"],
                        "description": "Agent name"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum versions to return",
                        "default": 10
                    }
                },
                "required": ["agent_name"]
            }
        },
        {
            "name": "submit_analysis",
            "description": "Submit the final analysis result",
            "input_schema": {
                "type": "object",
                "properties": {
                    "problems": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "description": {"type": "string"},
                                "severity": {
                                    "type": "string",
                                    "enum": ["critical", "important", "cosmetic"]
                                },
                                "examples": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            },
                            "required": ["id", "description", "severity"]
                        }
                    },
                    "hypotheses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "problem_ids": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "suggestion": {"type": "string"},
                                "expected_effect": {"type": "string"},
                                "confidence": {"type": "number"}
                            },
                            "required": ["id", "suggestion", "expected_effect", "confidence"]
                        }
                    },
                    "overall_confidence": {
                        "type": "number",
                        "description": "Overall confidence in the analysis (0.0-1.0)"
                    }
                },
                "required": ["problems", "hypotheses", "overall_confidence"]
            }
        }
    ]

    def __init__(
        self,
        client: Anthropic,
        prompt_manager: PromptManager,
        log_manager: LogManager,
        model: Optional[str] = None,
    ):
        self.client = client
        self.prompt_manager = prompt_manager
        self.log_manager = log_manager
        self.agent_name = "analyzer"
        self.model = model or config.models.analyzer

    def get_system_prompt(self) -> str:
        """Get the current system prompt for this agent."""
        return self.prompt_manager.get_current(self.agent_name)

    async def analyze(
        self,
        feedback: Feedback,
        recent_logs: list[dict],
        current_prompt: str,
    ) -> AnalysisResult:
        """
        Analyze feedback and logs to formulate improvement hypotheses.

        Args:
            feedback: The triggering feedback
            recent_logs: Recent conversation logs
            current_prompt: Current system prompt of main agent

        Returns:
            AnalysisResult with problems and hypotheses
        """
        system_prompt = self.get_system_prompt()

        # Prepare context for analysis
        logs_summary = self._summarize_logs(recent_logs)

        messages = [{
            "role": "user",
            "content": f"""Analyze the following data and formulate improvement hypotheses.

## Triggering Feedback
{feedback.to_json()}

## Current System Prompt (main_agent)
```
{current_prompt}
```

## Recent Conversation Logs Summary
{logs_summary}

## Raw Logs (last {min(10, len(recent_logs))} interactions)
{json.dumps(recent_logs[:10], ensure_ascii=False, indent=2)}

Use the available tools to search for more context if needed, then submit your analysis using submit_analysis.

Focus on:
1. What specific problem does the feedback indicate?
2. Are there similar issues in the logs?
3. What changes to the prompt could address this?
"""
        }]

        analysis_result = None
        raw_analysis = ""

        # Agentic loop
        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                tools=self.TOOLS,
                messages=messages,
            )

            # Collect text content
            for block in response.content:
                if hasattr(block, "text"):
                    raw_analysis += block.text

            # Check for tool use
            if response.stop_reason == "tool_use":
                tool_results = await self._execute_tools(response.content)
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

                # Check if submit_analysis was called
                for block in response.content:
                    if block.type == "tool_use" and block.name == "submit_analysis":
                        analysis_result = self._parse_analysis(block.input, raw_analysis)
                        break

                if analysis_result:
                    break
            else:
                # No more tools - try to parse from text
                if not analysis_result:
                    analysis_result = self._create_fallback_result(feedback, raw_analysis)
                break

        return analysis_result

    def _summarize_logs(self, logs: list[dict]) -> str:
        """Create a summary of logs for context."""
        total = len(logs)
        with_feedback = [l for l in logs if l.get("feedback")]
        negative = [l for l in with_feedback if l.get("feedback", {}).get("type") == "negative"]

        summary = f"""
- Total interactions: {total}
- Interactions with feedback: {len(with_feedback)}
- Negative feedback count: {len(negative)}
"""

        if negative:
            summary += "\nRecent negative feedback:\n"
            for log in negative[:5]:
                fb = log.get("feedback", {})
                summary += f"- [{fb.get('category')}] {fb.get('raw_text', '')[:100]}\n"

        return summary

    async def _execute_tools(self, content: list) -> list:
        """Execute tool calls and return results."""
        results = []

        for block in content:
            if block.type != "tool_use":
                continue

            tool_name = block.name
            tool_input = block.input
            tool_id = block.id

            result = await self._execute_tool(tool_name, tool_input)

            results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps(result, ensure_ascii=False),
            })

        return results

    async def _execute_tool(self, name: str, input_data: dict) -> dict:
        """Execute a single tool."""
        if name == "search_logs":
            logs = await self.log_manager.search(
                query=input_data["query"],
                date_range=input_data.get("date_range", "last_week"),
            )
            # Filter by feedback type if specified
            fb_type = input_data.get("feedback_type")
            if fb_type and fb_type != "all":
                logs = [l for l in logs if l.get("feedback", {}).get("type") == fb_type]
            return {"results": logs[:20], "total": len(logs)}

        elif name == "get_conversation":
            session = await self.log_manager.get_session(input_data["session_id"])
            return {"conversation": session}

        elif name == "get_prompt_history":
            history = self.prompt_manager.get_history(
                input_data["agent_name"],
                input_data.get("limit", 10),
            )
            return {"history": history}

        elif name == "submit_analysis":
            # This is handled in the main loop
            return {"status": "analysis_submitted"}

        return {"error": f"Unknown tool: {name}"}

    def _parse_analysis(self, input_data: dict, raw_analysis: str) -> AnalysisResult:
        """Parse submit_analysis tool input into AnalysisResult."""
        problems = [
            Problem(
                id=p.get("id", f"P{i}"),
                description=p.get("description", ""),
                severity=p.get("severity", "important"),
                examples=p.get("examples", []),
            )
            for i, p in enumerate(input_data.get("problems", []))
        ]

        hypotheses = [
            Hypothesis(
                id=h.get("id", f"H{i}"),
                problem_ids=h.get("problem_ids", []),
                suggestion=h.get("suggestion", ""),
                expected_effect=h.get("expected_effect", ""),
                confidence=h.get("confidence", 0.5),
            )
            for i, h in enumerate(input_data.get("hypotheses", []))
        ]

        return AnalysisResult(
            problems=problems,
            hypotheses=hypotheses,
            evidence=[],  # Could be populated from logs
            confidence_score=input_data.get("overall_confidence", 0.5),
            raw_analysis=raw_analysis,
        )

    def _create_fallback_result(self, feedback: Feedback, raw_analysis: str) -> AnalysisResult:
        """Create a basic result when proper analysis wasn't submitted."""
        return AnalysisResult(
            problems=[
                Problem(
                    id="P1",
                    description=f"User feedback: {feedback.raw_text}",
                    severity="important",
                    examples=[feedback.raw_text],
                )
            ],
            hypotheses=[
                Hypothesis(
                    id="H1",
                    problem_ids=["P1"],
                    suggestion=f"Address feedback about {feedback.category}",
                    expected_effect="Improved user satisfaction",
                    confidence=0.6,
                )
            ],
            evidence=[],
            confidence_score=0.5,
            raw_analysis=raw_analysis,
        )

    async def process(self, message: str):
        """Not used directly - use analyze() instead."""
        raise NotImplementedError("Use analyze() method instead")
