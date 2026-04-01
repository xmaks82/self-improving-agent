"""Per-tool detailed usage prompts for each built-in tool."""

BASH_TOOL_PROMPT = """Executes a shell command and returns its output.

Working directory persists between commands, but shell state does not.

IMPORTANT: Avoid using this tool to run `find`, `grep`, `cat`, `head`, `tail`, `sed`, `awk` commands unless explicitly instructed. Use the appropriate dedicated tool instead:
 - File search: Use search_files (NOT find or ls)
 - Content search: Use grep tool (NOT grep command)
 - Read files: Use read_file (NOT cat/head/tail)
 - Write files: Use write_file (NOT echo/cat redirect)

# Instructions
 - Always quote file paths with spaces using double quotes
 - Try to use absolute paths to maintain working directory
 - Commands timeout after 30s by default
 - When issuing multiple commands:
   - Independent commands: make separate tool calls in parallel
   - Dependent commands: chain with `&&`
   - Use `;` only when you don't care if earlier commands fail
 - For git commands:
   - Create NEW commits, never amend existing ones unless explicitly asked
   - Never skip hooks (--no-verify) or bypass signing unless explicitly asked
   - Never force-push to main/master
   - Stage specific files, not `git add .` (prevents accidental secrets)
   - Only commit when user explicitly asks
 - Avoid unnecessary `sleep` commands
 - NEVER run destructive operations (rm -rf, git reset --hard) without user confirmation"""

READ_FILE_PROMPT = """Reads a file from the local filesystem.

Usage:
- The file_path must be an absolute path
- By default reads up to 2000 lines from the beginning
- Use offset and limit parameters for large files
- Can read images (PNG, JPG), PDFs (with page ranges), and Jupyter notebooks
- Can only read files, not directories (use list_directory for directories)
- If a file exists but is empty, a warning will be returned"""

WRITE_FILE_PROMPT = """Writes a file to the local filesystem.

Usage:
- Overwrites the existing file if there is one at the provided path
- If this is an existing file, you MUST use read_file first. This tool will fail if you did not read the file first.
- Prefer the edit tool for modifying existing files - it only sends the diff
- Only use this tool to create NEW files or for complete rewrites
- NEVER create documentation files (*.md) or README files unless explicitly requested
- Only use emojis if the user explicitly requests it"""

EDIT_FILE_PROMPT = """Performs exact string replacements in files.

Usage:
- You MUST use read_file at least once before editing. This tool will error if you attempt an edit without reading the file.
- Preserve the exact indentation (tabs/spaces) from the file content
- ALWAYS prefer editing existing files. NEVER write new files unless explicitly required.
- The edit will FAIL if old_string is not unique in the file. Provide more surrounding context to make it unique, or use replace_all.
- Use replace_all for renaming variables/strings across the file
- Only use emojis if the user explicitly requests it"""

SEARCH_FILES_PROMPT = """Fast file pattern matching tool.
- Supports glob patterns like "**/*.py" or "src/**/*.ts"
- Returns matching file paths
- Use this when you need to find files by name patterns
- For open-ended searches requiring multiple rounds, use the agent orchestrator instead"""

GREP_PROMPT = """Powerful content search tool.

Usage:
- ALWAYS use this for search tasks. NEVER invoke grep as a Bash command.
- Supports full regex syntax (e.g., "log.*Error", "function\\\\s+\\\\w+")
- Filter files with file_pattern parameter (e.g., "*.py", "*.tsx")
- Supports context lines: before_context (-B), after_context (-A), context_lines (-C)
- Use case_insensitive=True for case-insensitive search
- For open-ended searches requiring multiple rounds, use the agent orchestrator"""

WEB_SEARCH_PROMPT = """Search the web for up-to-date information.
- Returns search results with links
- Use for information beyond the agent's knowledge cutoff
- After answering, include relevant source URLs"""

WEB_FETCH_PROMPT = """Fetch and extract content from a URL.
- Fetches the URL, converts HTML to text
- The URL must be a fully-formed valid URL
- Results may be summarized if content is very large
- Use for retrieving and analyzing web content"""

GIT_STATUS_PROMPT = """Show the working tree status of a git repository."""

GIT_DIFF_PROMPT = """Show changes between commits, the working tree, etc."""

GIT_COMMIT_PROMPT = """Create a git commit with staged changes.
- Stage specific files, avoid `git add .`
- Only commit when explicitly asked by the user
- Never amend existing commits unless explicitly asked"""

# Map tool names to their prompts
TOOL_PROMPTS: dict[str, str] = {
    "run_command": BASH_TOOL_PROMPT,
    "read_file": READ_FILE_PROMPT,
    "write_file": WRITE_FILE_PROMPT,
    "list_directory": "Lists files and directories in the specified path.",
    "search_files": SEARCH_FILES_PROMPT,
    "grep": GREP_PROMPT,
    "web_search": WEB_SEARCH_PROMPT,
    "fetch_url": WEB_FETCH_PROMPT,
    "git_status": GIT_STATUS_PROMPT,
    "git_diff": GIT_DIFF_PROMPT,
    "git_commit": GIT_COMMIT_PROMPT,
}
