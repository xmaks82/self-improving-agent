# Self-Improving AI Agent

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/xmaks82/self-improving-agent)](https://github.com/xmaks82/self-improving-agent/stargazers)
[![CI](https://github.com/xmaks82/self-improving-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/xmaks82/self-improving-agent/actions)

> **[Версия на русском](README_RU.md)**

**A terminal coding agent that actually executes tools — and rewrites its own prompt from your feedback.**

It runs a real `think → tool → result` loop (read/edit/write/shell/git/search/web),
asks before mutating, can undo, and talks to external **MCP servers** mid-conversation.
When you give feedback, a background pipeline analyzes the logs and ships an
improved system prompt — with **metrics + automatic rollback** if the new version
underperforms. Runs free out of the box via the **FCM** local model router, or on
any of 6 keyed providers / your Claude subscription.

```
You: "Your answers are too long"
     ↓ FeedbackDetector  (ignores work commands like "fix this bug")
[Analyzer] reads logs, forms hypotheses
     ↓
[Versioner] writes an improved system prompt  (meta-agents protected)
     ↓
New version goes live  →  feedback metrics tracked
     ↓
If it underperforms (≥60% negative over ≥4 samples) → auto-rollback to parent
```

## Highlights (v1.5.0)

- **Real agentic loop** — `think → tool_use → tool_result → repeat`, bounded
  iterations, loop-detection, tool-errors fed back for recovery, real token
  accounting. Output is **token-streamed during tool-use** (Anthropic +
  OpenAI-compatible/FCM), with graceful fallback.
- **Tools with guardrails** — read / **edit** (targeted) / write (atomic +
  stale-detection) / shell / git / search / web / worktree / notebook.
  Confirmation for writes/commands, working **undo**, shell-injection blocked
  (every sub-command head validated; redirects/subshells refused), SSRF guard
  that re-validates every redirect hop.
- **MCP in the loop** — tools from any configured MCP server (e.g. a memory
  server) are callable by the model mid-conversation.
- **Closed-loop self-improvement** — per-version feedback metrics + auto-rollback;
  the feedback detector won't mistake "fix this bug in X" for criticism of itself;
  the versioner can't rewrite its own / the analyzer's prompt.
- **Sub-agents with tools** — CodeReviewer / TestWriter / Debugger / Researcher /
  Refactorer and the adversarial verifier all run the same tool-loop.
- **Free by default** — `fcm` router aggregates free models with health-probe +
  auto-failover, so there are no stale model ids to maintain.

## LLM Providers
| Provider | Notes | Key |
|----------|-------|-----|
| **FCM** (default) | Local router: free-model aggregation, health-probe, auto-failover | none — set `FCM_BASE_URL` |
| **Groq** | Fast free tier | [console.groq.com](https://console.groq.com/) |
| **SambaNova** | ~580 t/s | [cloud.sambanova.ai](https://cloud.sambanova.ai/) |
| **Cerebras** | Free, ultra-fast | [cloud.cerebras.ai](https://cloud.cerebras.ai/) |
| **OpenRouter** | Free tier, 1M ctx | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **Zhipu** | GLM flash free | [open.bigmodel.cn](https://open.bigmodel.cn/) |
| **Anthropic** | Claude via OAuth subscription or API key (auto-fallback) | [console.anthropic.com](https://console.anthropic.com/) |

Keyed providers expose curated model shortcuts; treat their static lists as
best-effort and prefer `fcm` (or verify with your own key) — provider catalogs
change often.

## Quick Start

```bash
git clone https://github.com/xmaks82/self-improving-agent.git
cd self-improving-agent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
agent      # runs free via FCM by default (no key required)
```

To use a keyed provider instead: put a key in `.env` (`cp .env.example .env`)
and set `DEFAULT_MODEL` (e.g. `llama-3.3-70b` for Groq). Docker: `make run`.

### Connect a memory backend (optional)

Point the agent at an MCP memory server in `~/.agent/mcp.yaml`:

```yaml
servers:
  memory:
    command: /path/to/python
    args: [/path/to/memory_server.py]
    env: {MEMORY_DIR: /path/to/memory}
    enabled: true
```

Its tools (search/save/recall…) are bridged into the loop automatically at start.

## Configuration (env)

```bash
# Free by default — nothing required. To pin the local router model:
FCM_BASE_URL=http://localhost:9999/v1   # OpenAI-compatible endpoint
FCM_MODEL=fcm                            # or fcm:free-coding

# Keyed providers (optional) — set a key + choose the model
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...
ANTHROPIC_API_KEY=sk-ant-...             # or Claude OAuth: claude setup-token → /auth paste
DEFAULT_MODEL=fcm                        # default; e.g. llama-3.3-70b, claude-haiku, …

# Tuning
AGENT_MAX_TOOL_ITERATIONS=25
FACT_DISTILL=1
```

## Key CLI Commands

| Command | Description |
|---------|-------------|
| `/model [NAME]` | Show or switch model |
| `/tools` | List all tools (local + MCP) |
| `/mcp connect\|list` | Manage MCP servers |
| `/plan TASK` · `/explore QUERY` | Read-only design / codebase search |
| `/fork NAME TASK` · `/forks` | Background agent clones |
| `/verify` | Adversarial verification (tool-enabled) |
| `/auth [status\|paste]` | Claude subscription auth |
| `/compact` · `/sessions` · `/resume ID` | History / session management |
| `/cost` · `/stats` · `/export [md\|json]` | Usage, stats, export |
| `/commit` · `/review [PR]` · `/simplify` · `/debug` | Skills |
| `/feedback TEXT` · `/versions` · `/diff [V1] [V2]` · `/prompt` | Self-improvement |
| `/team` · `/summary` · `/plugins` · `/voice` | Memory, notes, plugins, voice |

## Project Structure

```
src/agent/
├── main.py            # Entry point (builds registry → pipeline → CLI)
├── config.py          # Configuration (default model: fcm)
├── agents/            # main_agent, sub-agents, verification, analyzer, versioner,
│                      #   pipeline, _tool_loop (shared bounded tool-loop)
├── tools/             # filesystem(edit/atomic/stale), shell(hardened), git, search,
│                      #   web(SSRF guard), worktree, notebook, registry, permissions
├── approval/          # confirmation + undo (wired into the registry)
├── clients/           # provider clients + FCM + OpenAI-compat + OAuth; stream_with_tools
├── mcp/               # MCP client/manager + bridge into the tool registry
├── memory/            # SQLite hybrid memory (vector+keyword RRF), secret scanner, bounds
├── core/              # feedback (closed loop), cost, compaction, session memory
├── storage/           # versioned prompts (metrics + auto-rollback), logs, sessions
├── prompts/ · skills/ · plugins/ · planning/ · interfaces/   # composer, slash-skills, plugins, tasks, CLI+voice
tests/                 # loop, tool-safety, MCP bridge, self-improve, streaming, …
```

## Development

```bash
pip install -e ".[dev]"
pytest -q          # test suite
ruff check src tests
```

## License

MIT
