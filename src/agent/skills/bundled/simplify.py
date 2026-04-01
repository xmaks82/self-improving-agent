"""Bundled /simplify skill — review changed code for quality."""

from ..registry import register_skill

SIMPLIFY_PROMPT = """Review recently changed code for reuse, quality, and efficiency.

Steps:
1. Run `git diff HEAD~1` to see recent changes (or `git diff --cached` for staged)
2. For each changed file, check:
   - **Duplication**: Is similar code repeated elsewhere? Can it be DRY'd?
   - **Complexity**: Can logic be simplified? Nested ifs → early returns?
   - **Naming**: Are names clear and consistent?
   - **Dead code**: Any unused variables, imports, or functions?
   - **Performance**: Obvious inefficiencies?
3. Fix any issues found directly — don't just report them
4. If everything looks good, say so briefly"""


def register():
    async def get_prompt(args: str) -> str:
        if args.strip():
            return f"{SIMPLIFY_PROMPT}\n\nFocus on: {args}"
        return SIMPLIFY_PROMPT

    register_skill("simplify", "Review changed code for reuse, quality, efficiency", get_prompt)
