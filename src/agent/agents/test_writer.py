"""Test writer sub-agent."""

from typing import Any

from .sub_agent import SubAgent


class TestWriter(SubAgent):
    """
    Specialized agent for writing tests.

    Creates:
    - Unit tests
    - Integration tests
    - Edge case tests
    - Mock setups
    """

    name = "test_writer"
    description = "Generates unit and integration tests for code"

    system_prompt = """You are an expert test writer. Your task is to create comprehensive tests for code.

Guidelines:
1. **Coverage**: Test all public methods and edge cases
2. **Isolation**: Each test should be independent
3. **Naming**: Use descriptive test names (test_<function>_<scenario>_<expected>)
4. **AAA Pattern**: Arrange, Act, Assert
5. **Mocking**: Use mocks for external dependencies

For Python, use pytest conventions:
- Use fixtures for setup
- Use parametrize for multiple cases
- Use pytest.raises for exception testing

Output format:
- Complete, runnable test code
- Include necessary imports
- Add docstrings explaining test purpose
- Group related tests in classes if appropriate"""

    async def execute(self, task: str, context: dict[str, Any]) -> str:
        """Generate tests."""
        code = context.get("code", "")
        file_path = context.get("file_path", "")
        language = context.get("language", "python")
        test_framework = context.get("framework", "pytest")

        prompt = f"""Generate tests for the following code:

File: {file_path}
Language: {language}
Framework: {test_framework}

```
{code}
```

Task: {task}

{self._format_context({k: v for k, v in context.items() if k not in ['code', 'file_path', 'language', 'framework']})}

Generate comprehensive tests covering:
1. Normal operation (happy path)
2. Edge cases
3. Error handling
4. Boundary conditions

Output complete, runnable test code."""

        return await self._call_llm(prompt)

    async def generate_unit_tests(self, code: str, context: dict[str, Any]) -> str:
        """Generate unit tests for a function/class."""
        context["code"] = code
        return await self.execute("Generate unit tests", context)

    async def generate_integration_tests(
        self,
        components: list[str],
        context: dict[str, Any],
    ) -> str:
        """Generate integration tests for multiple components."""
        prompt = f"""Generate integration tests for the following components:

Components:
{chr(10).join(f'- {c}' for c in components)}

{self._format_context(context)}

Create tests that verify:
1. Components work together correctly
2. Data flows properly between components
3. Error handling across component boundaries
4. Edge cases in component interactions

Output complete, runnable test code."""

        return await self._call_llm(prompt)
