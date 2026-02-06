# Contributing to Self-Improving AI Agent

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

```bash
git clone https://github.com/xmaks82/self-improving-agent.git
cd self-improving-agent

python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Add at least GROQ_API_KEY to .env
```

## Project Structure

```
src/agent/
├── agents/       # Main agent + sub-agents
├── clients/      # LLM provider clients
├── tools/        # Built-in tools
├── memory/       # Persistent memory (SQLite)
├── planning/     # Task management
├── mcp/          # Model Context Protocol
├── approval/     # Human-in-the-loop
├── core/         # Feedback detection
├── storage/      # Prompts & logs
└── interfaces/   # CLI
```

## How to Contribute

### Reporting Bugs

Open an issue using the **Bug Report** template. Include:
- Steps to reproduce
- Expected vs actual behavior
- Python version, OS, LLM provider used

### Suggesting Features

Open an issue using the **Feature Request** template.

### Submitting Code

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Run the linter: `ruff check src/`
4. Run tests: `pytest`
5. Open a pull request

### Code Style

- Python 3.12+ with type hints
- Follow existing patterns in the codebase
- Use `async/await` for I/O operations
- Use `logging` module (not `print()`)
- Use `datetime.now(timezone.utc)` (not `datetime.utcnow()`)

### Adding a New LLM Provider

1. Create `src/agent/clients/your_client.py` extending `BaseLLMClient`
2. Implement `chat()`, `stream()`, `chat_with_tools()` methods
3. Add model mappings to `src/agent/clients/factory.py`
4. Add API key handling to `src/agent/config.py` and `.env.example`

### Adding a New Tool

1. Create `src/agent/tools/your_tool.py` extending `BaseTool`
2. Register it in `src/agent/tools/registry.py`

## Good First Issues

Look for issues labeled [`good first issue`](https://github.com/xmaks82/self-improving-agent/labels/good%20first%20issue) — these are specifically chosen to be approachable for new contributors.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
