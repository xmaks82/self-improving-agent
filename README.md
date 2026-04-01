# Self-Improving AI Agent v1.3

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/xmaks82/self-improving-agent)](https://github.com/xmaks82/self-improving-agent/stargazers)
[![Free LLM Providers](https://img.shields.io/badge/Free_LLM_Providers-4-orange)](https://github.com/xmaks82/self-improving-agent#free-4-providers)

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

### Core
- **Self-Improving Prompts** — permanent prompt evolution from user feedback
- **Composable System Prompt** — section-based architecture (intro, tasks, actions, tools, style, efficiency)
- **5 LLM Providers** — Groq, SambaNova (580 t/s), Cerebras, Zhipu (GLM-5.1), Anthropic
- **Verification Agent** — adversarial verification after non-trivial changes (PASS/FAIL/PARTIAL)
- **Explore Agent** — fast read-only codebase navigation

### Tools & Security
- **11 Built-in Tools** — filesystem, git, shell, search, web (with deferred loading)
- **Enhanced Bash Security** — 6-layer validation (command substitution, redirects, variables, control chars, git safety)
- **Read-Before-Edit** — files must be read before modification (prevents blind edits)
- **Permission System** — auto-approve reads, confirm writes, block dangerous operations
- **Git Safety** — 10+ dangerous patterns detected (force-push, hard reset, --no-verify)

### Session & Memory
- **Context Compaction** — automatic history summarization (`/compact`)
- **Session Persistence** — save and resume conversations (`/sessions`, `/resume`)
- **Persistent Memory** — episodic, semantic, procedural, working memory (SQLite)
- **Bounded Memory** — 200 lines / 25KB cap with truncation

### Planning & Agents
- **Task Management** — create, track, complete tasks
- **Sub-agents** — CodeReviewer, TestWriter, Debugger, Researcher, Refactorer
- **MCP Integration** — Model Context Protocol for external tools
- **Human-in-the-Loop** — diff preview, confirmations, dry run, undo/redo

### CLI
- **Cost Tracking** — real-time token usage and cost per model (`/cost`)
- **Runtime Config** — change model, thresholds on the fly (`/config`)
- **Export** — save conversations as Markdown or JSON (`/export`)
- **Prompt Diff** — colored diff between prompt versions (`/diff`)

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
GROQ_API_KEY=gsk_...          # https://console.groq.com/  (recommended)
SAMBANOVA_API_KEY=...         # https://cloud.sambanova.ai/ (fastest, 580 t/s)
CEREBRAS_API_KEY=...          # https://cloud.cerebras.ai/  (1M tokens/day)
ZHIPU_API_KEY=...             # https://open.bigmodel.cn/   (2 free models)
ANTHROPIC_API_KEY=sk-ant-...  # https://console.anthropic.com/ (optional, paid)
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/model [NAME]` | Show or switch model |
| `/compact` | Compress conversation history |
| `/sessions` | List saved sessions |
| `/resume ID` | Resume a saved session |
| `/cost` | Token usage and cost breakdown |
| `/export [md\|json]` | Export conversation to file |
| `/config [set K V]` | View/change runtime config |
| `/diff [V1] [V2]` | Prompt version diff |
| `/tools` | List available tools |
| `/tasks` | List tasks |
| `/task add TEXT` | Create a task |
| `/task done ID` | Complete a task |
| `/prompt` | Show current system prompt |
| `/versions` | Prompt version history |
| `/rollback N` | Rollback to version N |
| `/feedback TEXT` | Submit feedback for improvement |
| `/stats` | Session statistics |
| `/quit` | Exit |

## Models

### Free (4 providers)

#### Groq (recommended, fast)

| Model | ID |
|-------|-----|
| Llama 4 Scout | `llama-4-scout` |
| Llama 3.3 70B | `llama-3.3-70b` |
| Qwen3 32B | `qwen3-32b` |
| Kimi K2 | `kimi-k2` |
| GPT-OSS 120B | `gpt-oss-120b` |
| GPT-OSS 20B | `gpt-oss-20b` |

#### SambaNova (580 t/s — fastest!)

| Model | ID |
|-------|-----|
| Llama 4 Maverick | `llama-4-maverick` |
| Llama 3.3 70B | `samba-llama-70b` |
| DeepSeek V3.2 | `deepseek-v3.2` |
| DeepSeek R1 | `deepseek-r1` |
| GPT-OSS 120B | `gpt-oss-120b-samba` |
| MiniMax M2.5 | `minimax-m2.5` |

#### Cerebras (1M tokens/day, ultra-fast)

| Model | ID |
|-------|-----|
| Llama 3.1 8B | `llama3.1-8b` |
| Qwen3 235B | `qwen3-235b` |
| GPT-OSS 120B | `gpt-oss-120b-cerebras` |
| GLM 4.7 | `glm-4.7-cerebras` |

#### Zhipu AI (free, no daily limits)

| Model | ID |
|-------|-----|
| GLM 4.5 Flash | `glm-4.5-flash` |
| GLM 4.7 Flash | `glm-4.7-flash` |

### Paid

#### Zhipu AI

| Model | ID | Price (input/output per 1M) |
|-------|-----|--------------------------|
| GLM 5.1 | `glm-5.1` | $1.00 / $3.20 |
| GLM 5 | `glm-5` | $1.00 / $3.20 |
| GLM 5 Code | `glm-5-code` | $1.20 / $5.00 |
| GLM 4.7 | `glm-4.7` | $0.60 / $2.20 |
| GLM 4.5 Air | `glm-4.5-air` | $0.20 / $1.10 |

#### Anthropic

| Model | ID | Price (input/output per 1M) |
|-------|-----|--------------------------|
| Claude Opus 4.6 | `claude-opus-4.6` | $5.00 / $25.00 |
| Claude Sonnet 4.6 | `claude-sonnet-4.6` | $3.00 / $15.00 |
| Claude Haiku 4.5 | `claude-haiku` | $1.00 / $5.00 |
| Claude Opus 4.5 | `claude-opus-4.5` | $5.00 / $25.00 |
| Claude Sonnet 4.5 | `claude-sonnet-4.5` | $3.00 / $15.00 |

## Configuration

```bash
# Default model (free)
DEFAULT_MODEL=llama-4-scout

# Improvement pipeline (free)
ANALYZER_MODEL=llama-3.3-70b
VERSIONER_MODEL=llama-3.3-70b
FEEDBACK_MODEL=llama-4-scout
```

## Project Structure

```
src/agent/
├── main.py              # Entry point
├── config.py            # Configuration
├── prompts/             # Composable system prompt sections + tool prompts
├── agents/              # Main agent, sub-agents, verification, explore
├── planning/            # Task management
├── mcp/                 # Model Context Protocol
├── tools/               # 11 built-in tools + security validators
├── memory/              # Persistent memory (SQLite) + bounds
├── approval/            # Human-in-the-loop
├── clients/             # 5 LLM provider clients
├── core/                # Feedback detection, cost tracking, compaction, config
├── storage/             # Versioned prompts, logs, sessions
└── interfaces/          # CLI with 20+ commands
```

## Docker

```bash
make help     # All commands
make run      # Start agent
make build    # Build image
make update   # Update (git pull + rebuild)
make shell    # Shell into container
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT
