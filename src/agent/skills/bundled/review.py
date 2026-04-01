"""Bundled /review skill — PR code review via gh CLI."""

from ..registry import register_skill

REVIEW_PROMPT = """You are an expert code reviewer. Follow these steps:

1. If no PR number given, run `gh pr list` to show open PRs
2. For a specific PR:
   - `gh pr view {number}` for PR details
   - `gh pr diff {number}` for the diff
3. Provide a thorough code review covering:
   - **Overview**: What the PR does
   - **Quality**: Code style, patterns, readability
   - **Correctness**: Logic bugs, edge cases
   - **Security**: Injection, auth, data exposure
   - **Performance**: N+1 queries, unnecessary allocations
   - **Tests**: Coverage, edge cases, mock quality
   - **Suggestions**: Specific actionable improvements

Be constructive. Cite specific files and line numbers."""


def register():
    async def get_prompt(args: str) -> str:
        pr = args.strip()
        if pr:
            return REVIEW_PROMPT.replace("{number}", pr)
        return REVIEW_PROMPT.replace("{number}", "<number>") + \
            "\n\nNo PR number provided — list open PRs first."

    register_skill("review", "Review a pull request via gh CLI", get_prompt)
