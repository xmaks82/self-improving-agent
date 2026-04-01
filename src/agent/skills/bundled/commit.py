"""Bundled /commit skill — intelligent git commit workflow."""

from ..registry import register_skill

COMMIT_PROMPT = """Create a git commit following this protocol:

1. Run in parallel:
   - `git status` (see all changes)
   - `git diff HEAD` (see what will be committed)
   - `git log --oneline -5` (recent commits for style reference)

2. Analyze changes and draft a commit message:
   - Follow the repo's existing commit message style
   - Summarize the nature (feat/fix/refactor/docs/test)
   - Focus on "why" not "what"
   - 1-2 sentences max

3. Stage relevant files (specific names, NOT `git add .`) and commit:
```
git commit -m "$(cat <<'EOF'
Your commit message here.
EOF
)"
```

RULES:
- NEVER use --no-verify or --amend unless explicitly asked
- NEVER commit .env, credentials, or secrets
- If no changes exist, say so — don't create empty commits
- Create NEW commits, never amend existing ones"""


def register():
    async def get_prompt(args: str) -> str:
        if args.strip():
            return f"{COMMIT_PROMPT}\n\nAdditional context: {args}"
        return COMMIT_PROMPT

    register_skill("commit", "Create a git commit with proper message", get_prompt)
