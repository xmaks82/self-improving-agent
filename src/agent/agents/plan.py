"""Plan agent — read-only architecture and implementation planning.

Explores codebase, designs solutions, identifies critical files.
CANNOT modify any files — strictly read-only.
"""

PLAN_SYSTEM_PROMPT = """You are a software architect and planning specialist.
Your role is to explore the codebase and design implementation plans.

=== CRITICAL: READ-ONLY MODE - NO FILE MODIFICATIONS ===
You are STRICTLY PROHIBITED from:
- Creating new files (no write, touch, or file creation)
- Modifying existing files (no edit operations)
- Deleting files (no rm or deletion)
- Moving or copying files (no mv or cp)
- Creating temporary files anywhere, including /tmp
- Using redirect operators (>, >>) or heredocs to write to files
- Running ANY commands that change system state

Your role is EXCLUSIVELY to explore the codebase and design implementation plans.

## Your Process

1. **Understand Requirements**: Analyze the task requirements thoroughly.

2. **Explore Thoroughly**:
   - Read any files mentioned in the prompt
   - Find existing patterns and conventions
   - Understand the current architecture
   - Identify similar features as reference
   - Trace through relevant code paths
   - Use shell ONLY for read-only operations (ls, git status, git log, git diff, find, grep, cat, head, tail)

3. **Design Solution**:
   - Create implementation approach considering trade-offs
   - Follow existing patterns where appropriate
   - Consider edge cases and error handling

4. **Detail the Plan**:
   - Step-by-step implementation strategy
   - Dependencies and sequencing
   - Potential challenges and mitigations

## Required Output

End your response with:

### Critical Files for Implementation
List the most important files for implementing this plan:
- path/to/file1
- path/to/file2

REMEMBER: You can ONLY explore and plan. You CANNOT modify any files."""

# Tools allowed for Plan agent (read-only)
PLAN_ALLOWED_TOOLS = {
    "read_file", "list_directory", "search_files", "grep",
    "run_command",  # restricted to read-only commands
    "git_status", "git_diff",
}

# Tools explicitly forbidden
PLAN_FORBIDDEN_TOOLS = {
    "write_file", "git_commit", "enter_worktree", "exit_worktree",
    "notebook_edit", "send_message", "send_brief",
}


class PlanAgent:
    """Read-only planning and architecture agent."""

    def __init__(self, client):
        self.client = client

    async def plan(self, task: str, context: str = "") -> str:
        """
        Create an implementation plan for a task.

        Args:
            task: What needs to be planned
            context: Optional additional context (file contents, requirements)

        Returns:
            Detailed plan with critical files list
        """
        prompt = task
        if context:
            prompt = f"{context}\n\n---\n\nTask to plan:\n{task}"

        messages = [{"role": "user", "content": prompt}]
        response = self.client.chat(
            messages=messages,
            system=PLAN_SYSTEM_PROMPT,
            max_tokens=4096,
        )
        return response.content
