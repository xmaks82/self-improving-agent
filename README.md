# Self-Improving AI Agent

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/xmaks82/self-improving-agent)](https://github.com/xmaks82/self-improving-agent/stargazers)
[![Free LLM Providers](https://img.shields.io/badge/Free_LLM_Providers-6-orange)](#free-6-providers)

> **[Версия на русском](README_RU.md)**

**AI agents forget. This one permanently evolves.**

A multi-agent system with **16 interconnected agents**, composable prompts, and permanent prompt evolution from user feedback. Runs on **6 free LLM providers** or Claude subscription via OAuth.

```
You: "Your answers are too long"
     ↓ FeedbackDetector
[Analyzer] examines logs, formulates hypotheses
     ↓
[Versioner] generates an improved system prompt
     ↓
New prompt version saved (v1 → v2 → v3...)
     ↓
Next responses use the upgraded "brain"
```

## Features

### 16-Agent Pipeline
- **MainAgent** — primary conversational agent with streaming
- **AnalyzerAgent + VersionerAgent** — self-improvement pipeline
- **5 Sub-agents** — CodeReviewer, TestWriter, Debugger, Researcher, Refactorer (auto-selected by keywords)
- **VerificationAgent** — adversarial testing, auto-triggered after 3+ file edits (PASS/FAIL/PARTIAL)
- **ExploreAgent** — fast read-only codebase search (`/explore`)
- **PlanAgent** — read-only architecture design (`/plan`)
- **ForkManager** — background clones with inherited context (`/fork`)
- **AgentOrchestrator** — coordinates sub-agents with auto-selection
- **SessionMemory, ContextCompactor, FeedbackDetector** — LLM-powered services

### 6 Free LLM Providers
| Provider | Speed | Models | Key |
|----------|-------|--------|-----|
| **Groq** | Fast | Llama 4 Scout, Llama 3.3 70B, Qwen3 32B, Kimi K2, GPT-OSS | [console.groq.com](https://console.groq.com/) |
| **SambaNova** | 580 t/s | Llama 4 Maverick, DeepSeek V3.2/R1, GPT-OSS | [cloud.sambanova.ai](https://cloud.sambanova.ai/) |
| **Cerebras** | Ultra-fast | Llama 3.1 8B, Qwen3 235B, GPT-OSS, GLM 4.7 | [cloud.cerebras.ai](https://cloud.cerebras.ai/) |
| **OpenRouter** | 1M ctx | Qwen 3.6 Plus (1M context, tool use) | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **Zhipu** | No limits | GLM 4.5 Flash, GLM 4.7 Flash | [open.bigmodel.cn](https://open.bigmodel.cn/) |
| **Anthropic** | OAuth/API | Claude Opus 4.6, Sonnet 4.6, Haiku 4.5 | [console.anthropic.com](https://console.anthropic.com/) |

**Claude subscription auth**: Use your Pro/Max subscription via OAuth — `/auth paste` with setup-token. Auto-fallback to API key if blocked.

### Tools & Security
- **13 Core Tools** + 4 deferred — filesystem, git, shell, search, web, worktree, notebook, messaging
- **6-Layer Bash Security** — command substitution, redirects, variables, control chars, Unicode, git safety
- **Command Semantics** — grep exit 1 = "no matches" not error; diff exit 1 = "files differ"
- **Read-Before-Edit** — files must be read before modification
- **Permission System** — auto-approve reads, confirm writes, block dangerous operations
- **Secret Scanner** — detects 8 credential patterns before sharing in team memory

### Skills (Slash Commands)
| Skill | Description |
|-------|-------------|
| `/commit` | Intelligent git commit with safety protocol |
| `/review [PR]` | PR code review via gh CLI |
| `/simplify` | Review changed code for quality |
| `/debug [issue]` | Structured debugging workflow |

### Session & Memory
- **Context Compaction** — auto-summarize old messages (`/compact`)
- **Session Memory** — background auto-notes maintained by LLM (`/summary`)
- **Session Persistence** — save/resume across restarts (`/sessions`, `/resume`)
- **Team Memory** — shared knowledge per-repo with secret scanning (`/team`)
- **Bounded Memory** — 200 lines / 25KB cap with truncation
- **Plugin System** — load external plugins from `~/.agent/plugins/`

## Quick Start

```bash
git clone https://github.com/xmaks82/self-improving-agent.git
cd self-improving-agent
cp .env.example .env
nano .env  # Add at least one free API key
make run   # Docker (recommended)
```

Or local install:
```bash
python -m venv venv && source venv/bin/activate
pip install -e . && agent
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `/model [NAME]` | Show or switch model |
| `/plan TASK` | Architecture design (read-only) |
| `/explore QUERY` | Codebase search (read-only) |
| `/fork NAME TASK` | Fork agent in background |
| `/forks` | Show fork status/results |
| `/verify` | Run adversarial verification |
| `/auth [status\|paste]` | Manage Claude subscription auth |
| `/compact` | Compress conversation history |
| `/sessions` | List saved sessions |
| `/resume ID` | Resume a saved session |
| `/cost` | Token usage and cost breakdown |
| `/export [md\|json]` | Export conversation to file |
| `/config [set K V]` | Runtime config |
| `/diff [V1] [V2]` | Prompt version diff |
| `/style [NAME]` | Output style (default/concise/explanatory/teaching) |
| `/commit` | Git commit skill |
| `/review [PR]` | PR review skill |
| `/simplify` | Code quality skill |
| `/debug [issue]` | Debugging skill |
| `/summary` | Session notes |
| `/team list\|add\|show` | Team shared memory |
| `/plugins` | List loaded plugins |
| `/voice` | Push-to-talk voice input |
| `/tasks` | Task management |
| `/prompt` | Current system prompt |
| `/versions` | Prompt version history |
| `/feedback TEXT` | Submit feedback |
| `/stats` | Session statistics |

## Configuration

```bash
# Free API keys (need at least one)
GROQ_API_KEY=gsk_...
SAMBANOVA_API_KEY=...
CEREBRAS_API_KEY=...
OPENROUTER_API_KEY=sk-or-...
ZHIPU_API_KEY=...

# Or Claude subscription (OAuth)
# Run: claude setup-token → then /auth paste TOKEN

# Or Anthropic API key (paid)
ANTHROPIC_API_KEY=sk-ant-...

# Model config
DEFAULT_MODEL=llama-4-scout
ANALYZER_MODEL=llama-3.3-70b
VERSIONER_MODEL=llama-3.3-70b
```

## Project Structure

```
src/agent/
├── main.py              # Entry point
├── config.py            # Configuration
├── auth/                # OAuth subscription auth
├── prompts/             # Composable system prompt (10 sections)
├── agents/              # 16 agents + pipeline orchestration
│   ├── pipeline.py      # Central agent wiring
│   ├── main_agent.py    # Primary agent
│   ├── verification.py  # Adversarial verifier
│   ├── explore.py       # Read-only search
│   ├── plan.py          # Architecture design
│   ├── fork.py          # Background clones
│   └── ...              # Sub-agents, analyzer, versioner
├── skills/              # Extensible slash commands
├── plugins/             # External plugin loader
├── tools/               # 13 core + 4 deferred tools
├── memory/              # SQLite memory + team sync + secret scanner
├── core/                # Feedback, cost, compaction, session memory, mailbox
├── storage/             # Versioned prompts, logs, sessions
├── clients/             # 6 LLM provider clients + OAuth
├── planning/            # Task management
├── mcp/                 # Model Context Protocol
├── approval/            # Human-in-the-loop
└── interfaces/          # CLI (35+ commands) + voice
```

## License

MIT
