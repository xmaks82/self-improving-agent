"""Code reviewer sub-agent."""

from typing import Any

from .sub_agent import SubAgent


class CodeReviewer(SubAgent):
    """
    Specialized agent for code review.

    Analyzes code for:
    - Bugs and potential issues
    - Code style and best practices
    - Security vulnerabilities
    - Performance concerns
    - Maintainability
    """

    name = "code_reviewer"
    description = "Reviews code for bugs, style issues, and improvements"

    system_prompt = """You are an expert code reviewer. Your task is to analyze code and provide constructive feedback.

Focus on:
1. **Bugs**: Logic errors, edge cases, potential crashes
2. **Security**: Vulnerabilities, unsafe patterns, input validation
3. **Performance**: Inefficient algorithms, memory issues, unnecessary operations
4. **Style**: Readability, naming conventions, code organization
5. **Best Practices**: Design patterns, SOLID principles, maintainability

Format your review as:
- Start with a brief summary (1-2 sentences)
- List issues by severity (Critical, Warning, Info)
- Provide specific line references when possible
- Suggest concrete fixes for each issue

Be constructive and professional. Focus on the most important issues first."""

    async def execute(self, task: str, context: dict[str, Any]) -> str:
        """Review code."""
        code = context.get("code", "")
        file_path = context.get("file_path", "unknown")
        language = context.get("language", "")

        prompt = f"""Review the following code:

File: {file_path}
Language: {language}

```
{code}
```

Task: {task}

{self._format_context({k: v for k, v in context.items() if k not in ['code', 'file_path', 'language']})}

Provide a detailed code review."""

        return await self._call_llm(prompt)

    async def review_diff(self, diff: str, context: dict[str, Any]) -> str:
        """Review a git diff."""
        prompt = f"""Review the following code changes:

```diff
{diff}
```

Focus on:
1. Are the changes correct and complete?
2. Do they introduce any bugs or regressions?
3. Are there any security concerns?
4. Is the code style consistent?

{self._format_context(context)}

Provide a concise review of the changes."""

        return await self._call_llm(prompt)
