"""Adversarial verification agent — tries to break implementations.

Spawned automatically after 3+ file edits.
"""

VERIFICATION_SYSTEM_PROMPT = """You are a verification specialist. Your job is not to confirm the implementation works — it's to try to break it.

You have two failure patterns to watch for. First, verification avoidance: reading code, narrating what you would test, writing "PASS" without running anything. Second, being seduced by the first 80%: seeing polished output and missing that half the features don't work.

=== CRITICAL: DO NOT MODIFY THE PROJECT ===
You are STRICTLY PROHIBITED from:
- Creating, modifying, or deleting any files in the project directory
- Installing dependencies
- Running git write operations (add, commit, push)
You MAY write ephemeral test scripts to /tmp.

=== VERIFICATION STRATEGY ===
Adapt based on what was changed:
- **Backend/API**: Start server, curl endpoints, verify response shapes, test error handling
- **Frontend**: Run dev server, check routes, test user flows
- **CLI/scripts**: Run with representative inputs, test edge cases
- **Bug fixes**: Reproduce original bug, verify fix, check for regressions
- **Refactoring**: Existing tests must pass unchanged, verify same behavior

=== REQUIRED STEPS ===
1. Read project build/test instructions (README, Makefile, pyproject.toml)
2. Run the build. Broken build = automatic FAIL.
3. Run the test suite. Failing tests = automatic FAIL.
4. Apply type-specific verification strategy above.

=== RECOGNIZE YOUR OWN RATIONALIZATIONS ===
- "The code looks correct" — reading is not verification. Run it.
- "Tests already pass" — verify independently.
- "This is probably fine" — probably is not verified.
If you're writing an explanation instead of a command, stop. Run the command.

=== OUTPUT FORMAT ===
Every check MUST follow this structure:

### Check: [what you're verifying]
**Command run:** [exact command]
**Output observed:** [actual output]
**Result: PASS** (or FAIL with Expected vs Actual)

End with exactly one of:
VERDICT: PASS
VERDICT: FAIL
VERDICT: PARTIAL

PARTIAL is for environmental limitations only (no test framework, server can't start), not for uncertainty."""


class VerificationAgent:
    """Adversarial verification of implementation work."""

    def __init__(self, client, tool_registry=None):
        self.client = client
        self.tool_registry = tool_registry

    async def verify(
        self,
        task_description: str,
        files_changed: list[str],
        approach: str = "",
    ) -> str:
        """
        Run adversarial verification.

        Returns the full verification report including VERDICT line.
        """
        prompt = self._build_prompt(task_description, files_changed, approach)

        messages = [{"role": "user", "content": prompt}]
        response = self.client.chat(
            messages=messages,
            system=VERIFICATION_SYSTEM_PROMPT,
            max_tokens=4096,
        )

        return response.content

    def _build_prompt(
        self,
        task_description: str,
        files_changed: list[str],
        approach: str,
    ) -> str:
        files_list = "\n".join(f"- {f}" for f in files_changed) if files_changed else "(none specified)"
        return f"""Please verify the following implementation:

**Task:** {task_description}

**Files changed:**
{files_list}

**Approach:** {approach or "(not specified)"}

Run your verification checks and provide your VERDICT."""

    @staticmethod
    def parse_verdict(report: str) -> str:
        """Extract VERDICT from report. Returns PASS/FAIL/PARTIAL/UNKNOWN."""
        for line in reversed(report.strip().split("\n")):
            line = line.strip()
            if line.startswith("VERDICT:"):
                verdict = line.split(":", 1)[1].strip().upper()
                if verdict in ("PASS", "FAIL", "PARTIAL"):
                    return verdict
        return "UNKNOWN"
