"""Bundled /debug skill — structured debugging workflow."""

from ..registry import register_skill

DEBUG_PROMPT = """You are in structured debugging mode. Follow this protocol:

1. **Reproduce**: Run the failing command/test to see the exact error
2. **Hypothesize**: List 2-3 most likely causes based on the error
3. **Investigate**: For each hypothesis, check the relevant code/logs:
   - Read the stack trace carefully
   - Search for related code with grep
   - Check recent changes with `git log --oneline -10` and `git diff`
4. **Root cause**: Identify the actual root cause (not symptoms)
5. **Fix**: Apply the minimal fix to the root cause
6. **Verify**: Run the original failing command again to confirm the fix

RULES:
- Fix root causes, not symptoms
- Don't make unrelated changes
- If multiple issues, fix one at a time
- Run the test/command after EVERY fix attempt"""


def register():
    async def get_prompt(args: str) -> str:
        if args.strip():
            return f"{DEBUG_PROMPT}\n\nThe issue: {args}"
        return DEBUG_PROMPT + "\n\nDescribe the issue or point me to the failing test/command."

    register_skill("debug", "Structured debugging workflow", get_prompt)
