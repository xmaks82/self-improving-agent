"""Debugger sub-agent."""

from typing import Any

from .sub_agent import SubAgent


class Debugger(SubAgent):
    """
    Specialized agent for debugging issues.

    Analyzes:
    - Error messages and tracebacks
    - Code logic for bugs
    - Runtime behavior
    - Suggests fixes
    """

    name = "debugger"
    description = "Analyzes errors and bugs, suggests fixes"

    system_prompt = """You are an expert debugger. Your task is to analyze errors and help fix bugs.

Approach:
1. **Understand**: Read the error message and traceback carefully
2. **Locate**: Find the root cause, not just the symptom
3. **Analyze**: Understand why the error occurred
4. **Fix**: Propose a concrete solution
5. **Prevent**: Suggest how to avoid similar issues

Output format:
1. **Error Analysis**: What went wrong and why
2. **Root Cause**: The underlying issue
3. **Solution**: Step-by-step fix with code
4. **Prevention**: How to avoid this in the future

Be specific and provide working code fixes. Explain your reasoning."""

    async def execute(self, task: str, context: dict[str, Any]) -> str:
        """Debug an issue."""
        error = context.get("error", "")
        traceback = context.get("traceback", "")
        code = context.get("code", "")

        prompt = f"""Debug the following issue:

Error: {error}

Traceback:
```
{traceback}
```

Related code:
```
{code}
```

Task: {task}

{self._format_context({k: v for k, v in context.items() if k not in ['error', 'traceback', 'code']})}

Analyze the error and provide:
1. What went wrong
2. Why it happened
3. How to fix it (with code)
4. How to prevent similar issues"""

        return await self._call_llm(prompt)

    async def analyze_traceback(self, traceback: str) -> str:
        """Analyze a traceback and explain the error."""
        prompt = f"""Analyze this traceback and explain what went wrong:

```
{traceback}
```

Provide:
1. A clear explanation of the error
2. The likely cause
3. Suggested fixes"""

        return await self._call_llm(prompt)

    async def find_bug(self, code: str, description: str) -> str:
        """Find a bug based on description of unexpected behavior."""
        prompt = f"""Find the bug in this code:

```
{code}
```

Problem description: {description}

Identify:
1. Where the bug is
2. Why it causes the described behavior
3. How to fix it"""

        return await self._call_llm(prompt)

    async def suggest_fix(
        self,
        code: str,
        error: str,
        context: dict[str, Any],
    ) -> str:
        """Suggest a fix for an error."""
        prompt = f"""Suggest a fix for this error:

Error: {error}

Code:
```
{code}
```

{self._format_context(context)}

Provide a complete, working fix."""

        return await self._call_llm(prompt)
