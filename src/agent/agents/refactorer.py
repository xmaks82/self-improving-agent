"""Refactorer sub-agent."""

from typing import Any

from .sub_agent import SubAgent


class Refactorer(SubAgent):
    """
    Specialized agent for code refactoring.

    Improves:
    - Code structure and organization
    - Readability and maintainability
    - Performance optimization
    - Design pattern application
    """

    name = "refactorer"
    description = "Refactors and improves code structure"

    system_prompt = """You are an expert at code refactoring. Your task is to improve code quality while preserving functionality.

Principles:
1. **Preserve Behavior**: Refactoring must not change what the code does
2. **Small Steps**: Make incremental, testable changes
3. **Clean Code**: Follow clean code principles
4. **SOLID**: Apply SOLID principles where appropriate
5. **DRY**: Eliminate duplication

Focus areas:
- Extract methods/functions for clarity
- Improve naming (variables, functions, classes)
- Reduce complexity (smaller functions, less nesting)
- Remove dead code
- Apply appropriate design patterns

Output format:
1. **Analysis**: Current issues with the code
2. **Plan**: What refactorings to apply
3. **Refactored Code**: The improved code
4. **Explanation**: Why each change was made"""

    async def execute(self, task: str, context: dict[str, Any]) -> str:
        """Refactor code."""
        code = context.get("code", "")
        focus = context.get("focus", "general improvement")
        preserve = context.get("preserve", [])

        prompt = f"""Refactor the following code:

```
{code}
```

Focus: {focus}
{"Preserve: " + ", ".join(preserve) if preserve else ""}

Task: {task}

{self._format_context({k: v for k, v in context.items() if k not in ['code', 'focus', 'preserve']})}

Provide:
1. Analysis of current issues
2. Refactoring plan
3. Complete refactored code
4. Explanation of changes"""

        return await self._call_llm(prompt)

    async def simplify(self, code: str) -> str:
        """Simplify complex code."""
        prompt = f"""Simplify this code while preserving its functionality:

```
{code}
```

Focus on:
1. Reducing complexity
2. Improving readability
3. Removing unnecessary code

Provide the simplified code with explanations."""

        return await self._call_llm(prompt)

    async def extract_function(self, code: str, target: str) -> str:
        """Extract a function from code."""
        prompt = f"""Extract a function from this code:

```
{code}
```

Target to extract: {target}

Provide:
1. The extracted function
2. Updated original code that calls the new function
3. Explanation of the extraction"""

        return await self._call_llm(prompt)

    async def apply_pattern(
        self,
        code: str,
        pattern: str,
        context: dict[str, Any],
    ) -> str:
        """Apply a design pattern to code."""
        prompt = f"""Apply the {pattern} pattern to this code:

```
{code}
```

{self._format_context(context)}

Provide:
1. Explanation of how the pattern applies
2. Refactored code using the pattern
3. Benefits of this change"""

        return await self._call_llm(prompt)

    async def optimize(self, code: str, goal: str = "performance") -> str:
        """Optimize code for a specific goal."""
        prompt = f"""Optimize this code for {goal}:

```
{code}
```

Provide:
1. Current inefficiencies
2. Optimized code
3. Explanation of optimizations
4. Expected improvement"""

        return await self._call_llm(prompt)
