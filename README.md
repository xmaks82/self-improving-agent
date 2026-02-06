# Self-Improving AI Agent

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/xmaks82/self-improving-agent)](https://github.com/xmaks82/self-improving-agent/stargazers)
[![Free LLM Providers](https://img.shields.io/badge/Free_LLM_Providers-5-orange)](https://github.com/xmaks82/self-improving-agent#free-4-providers)

> **[Версия на русском](README_RU.md)**

**AI agents forget. This one permanently evolves.**

Unlike regular chatbots where context fades over time, this agent **permanently rewrites its own system prompt** based on your feedback. Every improvement is saved forever — v1 becomes v2, v3, v47...

```
You: "Your answers are too long"
     ↓
[Analyzer] examines logs, formulates hypotheses
     ↓
[Versioner] generates an improved system prompt
     ↓
New prompt version saved (v1 → v2 → v3...)
     ↓
Next responses use the upgraded "brain"
```

Runs entirely on **free LLM APIs** — no paid subscriptions needed.

## Features

- **Self-Improving Prompts** — permanent prompt evolution from user feedback
- **5 LLM Providers** — Groq, SambaNova (580 t/s), Cerebras, Zhipu, Anthropic
- **Planning System** — task management with decomposition
- **Persistent Memory** — episodic, semantic, procedural, working memory across sessions
- **MCP Integration** — Model Context Protocol for external tools (GitHub, Slack, databases)
- **11 Built-in Tools** — filesystem, git, shell, search, web fetch
- **Sub-agents** — CodeReviewer, TestWriter, Debugger, Researcher, Refactorer
- **Human-in-the-Loop** — diff preview, confirmations, dry run, undo/redo

## Quick Start

### Docker (recommended)

```bash
git clone https://github.com/xmaks82/self-improving-agent.git
cd self-improving-agent

cp .env.example .env
nano .env  # Add your GROQ_API_KEY

make run
```

### Local install

```bash
git clone https://github.com/xmaks82/self-improving-agent.git
cd self-improving-agent

python -m venv venv
source venv/bin/activate
pip install -e .

cp .env.example .env
agent
```

### API Keys

You only need **one free key** to get started:

```bash
# Groq — recommended (free, fast)
GROQ_API_KEY=gsk_...          # https://console.groq.com/

# SambaNova — fastest (580 t/s, free)
SAMBANOVA_API_KEY=...         # https://cloud.sambanova.ai/

# Cerebras — 1M tokens/day free, ultra-fast
CEREBRAS_API_KEY=...          # https://cloud.cerebras.ai/

# Zhipu AI — glm-4.5-flash is free
ZHIPU_API_KEY=...             # https://open.bigmodel.cn/
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                              CLI / API                               │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────┐
│                         MAIN AGENT + PLANNER                         │
│                    Planning, Task Decomposition                      │
└───────┬───────────────────────────────────────────────────┬─────────┘
        │                                                   │
        ▼                                                   ▼
┌───────────────────┐                           ┌───────────────────────┐
│   SUB-AGENTS      │                           │    MEMORY SYSTEM      │
│                   │                           │                       │
│ • CodeReviewer    │                           │ • Episodic Memory     │
│ • TestWriter      │                           │ • Semantic Memory     │
│ • Debugger        │                           │ • Working Memory      │
│ • Researcher      │                           │ • Consolidation       │
│ • Refactorer      │                           │                       │
│ • Analyzer        │                           │                       │
│ • Versioner       │                           │                       │
└───────┬───────────┘                           └───────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────────┐
│                              TOOLS LAYER                              │
│                                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  Filesystem │  │    Shell    │  │     Git     │  │  Web/Search │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                     MCP Server Registry                          │ │
│  │  GitHub, Slack, Database, Browser, Custom Servers...             │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                         IMPROVEMENT PIPELINE                          │
│     Feedback Detection → Analyzer → Versioner → Prompt Update        │
└───────────────────────────────────────────────────────────────────────┘
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/model [NAME]` | Show or switch model |
| `/tools` | List available tools |
| `/tasks` | List tasks |
| `/task add TEXT` | Create a task |
| `/task done ID` | Complete a task |
| `/prompt` | Show current system prompt |
| `/versions` | Prompt version history |
| `/rollback N` | Rollback to version N |
| `/feedback TEXT` | Send feedback to improve the agent |
| `/mcp list` | List MCP servers |
| `/mcp connect NAME` | Connect an MCP server |
| `/stats` | Session statistics |
| `/quit` | Exit |

## Models

### Free (4 providers)

#### Groq (recommended)

| Model | ID |
|-------|-----|
| Llama 4 Maverick | `llama-4-maverick` |
| Llama 3.3 70B | `llama-3.3-70b` |
| Qwen3 32B | `qwen3-32b` |
| Kimi K2 | `kimi-k2` |

#### SambaNova (580 t/s — fastest!)

| Model | ID |
|-------|-----|
| Llama 3.3 70B | `samba-llama-70b` |
| Llama 3.1 8B | `samba-llama-8b` |
| DeepSeek V3 | `deepseek-v3` |
| DeepSeek R1 70B | `deepseek-r1-70b` |
| QwQ 32B | `qwq-32b` |

#### Cerebras (1M tokens/day)

| Model | ID |
|-------|-----|
| Llama 3.1 8B | `llama3.1-8b` |

#### Zhipu AI

| Model | ID |
|-------|-----|
| GLM 4.5 Flash | `glm-4.5-flash` |

### Paid

#### Zhipu AI

| Model | ID | Price (input/output per 1M) |
|-------|-----|--------------------------|
| GLM 4.7 | `glm-4.7` | $0.60 / $2.20 |
| GLM 4.5 Air | `glm-4.5-air` | $0.20 / $1.10 |

#### Anthropic

| Model | ID |
|-------|-----|
| Claude Opus 4.5 | `claude-opus-4.5` |
| Claude Sonnet 4 | `claude-sonnet` |

## Modules

| Module | Path | Description |
|--------|------|-------------|
| **Agents** | `src/agent/agents/` | Main agent, sub-agents (CodeReviewer, TestWriter, Debugger, Researcher, Refactorer), analyzer, versioner |
| **Planning** | `src/agent/planning/` | Task management with JSONL storage |
| **Memory** | `src/agent/memory/` | SQLite-backed persistent memory (episodic, semantic, procedural, working) |
| **Tools** | `src/agent/tools/` | 11 built-in tools: filesystem, shell, git, search, grep, web search, web fetch |
| **MCP** | `src/agent/mcp/` | Model Context Protocol client, registry, tool adapter |
| **Approval** | `src/agent/approval/` | Diff viewer, confirmations, dry run mode, undo/redo |
| **Clients** | `src/agent/clients/` | LLM provider clients with rate limit fallback |
| **Core** | `src/agent/core/` | Feedback detection pipeline |
| **Storage** | `src/agent/storage/` | Versioned YAML prompts, JSONL conversation logs |

## Configuration

```bash
# API keys
GROQ_API_KEY=gsk_...
SAMBANOVA_API_KEY=...
CEREBRAS_API_KEY=...

# Default model (free)
DEFAULT_MODEL=llama-4-maverick

# Improvement pipeline (requires Anthropic API key)
ANALYZER_MODEL=claude-sonnet
VERSIONER_MODEL=claude-sonnet
FEEDBACK_MODEL=claude-haiku
```

MCP servers are configured in `~/.agent/mcp.yaml`:

```yaml
servers:
  filesystem:
    command: npx
    args: ["-y", "@anthropic/mcp-server-filesystem", "/workspace"]

  github:
    command: npx
    args: ["-y", "@anthropic/mcp-server-github"]
    env:
      GITHUB_TOKEN: ${GITHUB_TOKEN}
```

## Docker

```bash
make help     # All commands
make run      # Start agent
make build    # Build image
make update   # Update (git pull + rebuild)
make version  # Show version
make shell    # Shell into container
```

## Project Structure

```
src/agent/
├── main.py              # Entry point
├── config.py            # Configuration
├── agents/              # Main agent + sub-agents
├── planning/            # Task management
├── mcp/                 # Model Context Protocol
├── tools/               # Built-in tools (11)
├── memory/              # Persistent memory (SQLite)
├── approval/            # Human-in-the-loop
├── clients/             # LLM provider clients
├── core/                # Feedback detection
├── storage/             # Prompts & logs
└── interfaces/          # CLI
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT

## Inspiration

- [ERC3 Winning Solution](https://erc.timetoact-group.at/assets/erc3.html)
- [Anthropic Multi-Agent Systems](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Model Context Protocol](https://modelcontextprotocol.io/)
