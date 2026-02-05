"""Researcher sub-agent."""

from typing import Any

from .sub_agent import SubAgent


class Researcher(SubAgent):
    """
    Specialized agent for research tasks.

    Handles:
    - Documentation lookup
    - Best practices research
    - Technology comparison
    - Solution exploration
    """

    name = "researcher"
    description = "Researches topics, finds solutions, explains concepts"

    system_prompt = """You are an expert researcher and technical writer. Your task is to research topics and provide clear, accurate information.

Guidelines:
1. **Accuracy**: Provide correct, up-to-date information
2. **Clarity**: Explain complex topics simply
3. **Examples**: Include code examples when relevant
4. **Sources**: Mention official docs or well-known resources
5. **Alternatives**: Present multiple options when applicable

Output format:
- Start with a concise answer
- Provide detailed explanation
- Include practical examples
- List relevant resources/links
- Note any caveats or considerations

Be thorough but concise. Focus on practical, actionable information."""

    async def execute(self, task: str, context: dict[str, Any]) -> str:
        """Research a topic."""
        topic = context.get("topic", task)
        scope = context.get("scope", "general")

        prompt = f"""Research the following topic:

Topic: {topic}
Scope: {scope}

Task: {task}

{self._format_context({k: v for k, v in context.items() if k not in ['topic', 'scope']})}

Provide comprehensive information including:
1. Clear explanation
2. Practical examples
3. Best practices
4. Common pitfalls
5. Relevant resources"""

        return await self._call_llm(prompt)

    async def explain_concept(self, concept: str, level: str = "intermediate") -> str:
        """Explain a technical concept."""
        prompt = f"""Explain the following concept at a {level} level:

Concept: {concept}

Include:
1. What it is
2. Why it's useful
3. How it works
4. Simple example
5. When to use it"""

        return await self._call_llm(prompt)

    async def compare_options(
        self,
        options: list[str],
        criteria: list[str],
        context: dict[str, Any],
    ) -> str:
        """Compare multiple options."""
        prompt = f"""Compare the following options:

Options: {', '.join(options)}

Criteria for comparison:
{chr(10).join(f'- {c}' for c in criteria)}

{self._format_context(context)}

Provide:
1. Brief description of each option
2. Comparison table
3. Pros and cons of each
4. Recommendation based on the context"""

        return await self._call_llm(prompt)

    async def find_solution(self, problem: str, constraints: list[str]) -> str:
        """Find solutions to a problem."""
        prompt = f"""Find solutions for the following problem:

Problem: {problem}

Constraints:
{chr(10).join(f'- {c}' for c in constraints)}

Provide:
1. Multiple possible solutions
2. Pros and cons of each
3. Recommended approach
4. Implementation steps"""

        return await self._call_llm(prompt)

    async def summarize_docs(self, docs: str, focus: str = "") -> str:
        """Summarize documentation."""
        prompt = f"""Summarize the following documentation:

```
{docs}
```

{"Focus on: " + focus if focus else ""}

Provide:
1. Key points
2. Important APIs/functions
3. Common usage patterns
4. Gotchas and tips"""

        return await self._call_llm(prompt)
