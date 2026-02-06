# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/).

## [1.0.0] - 2026-02-06

### Added
- **Planning System** — task management with decomposition (pending/in_progress/completed/blocked)
- **MCP Integration** — Model Context Protocol for external tools (GitHub, Slack, databases)
- **11 Built-in Tools** — read_file, write_file, list_directory, run_command, git_status, git_diff, git_commit, search_files, grep, web_search, fetch_url
- **Persistent Memory** — SQLite-backed memory with 4 types: episodic, semantic, procedural, working
- **Memory Consolidation** — importance decay, promotion, stale cleanup
- **Sub-agents** — CodeReviewer, TestWriter, Debugger, Researcher, Refactorer
- **Human-in-the-Loop** — DiffViewer, Confirmator, DryRunSession, UndoManager
- **SambaNova provider** — free, 580 tokens/sec on 70B models
- **Web tools** — web_search and fetch_url for internet access

### Fixed
- Sub-agent LLM calls (chat→stream, system_prompt→system parameter)
- Zhipu default model (glm-4→glm-4.5-flash)
- Web tools not registered in ToolRegistry
- Default models changed from paid Claude to free Llama
- Stream method type signature (sync→async AsyncIterator)
- Dangerous shell ops now logged instead of silently ignored
- Symlink traversal protection in filesystem tools (is_relative_to)
- datetime.utcnow() deprecated calls → datetime.now(timezone.utc)
- Rate limit handling deduplicated across providers
- Dead code removed (stream_with_usage, get_all_model_names, get_orchestrator)

## [0.3.0] - 2026-01-30

### Added
- Cerebras integration (1M tokens/day free, ultra-fast)
- Rate limit fallback across providers
- Automatic provider failover

## [0.2.0] - 2026-01-25

### Added
- Multi-provider support (Groq, Zhipu, Anthropic)
- Provider auto-detection from model name
- Configurable models via environment variables

## [0.1.0] - 2026-01-20

### Added
- Initial release
- Self-improving prompt pipeline (FeedbackDetector → Analyzer → Versioner)
- Versioned YAML prompt storage with symlinks
- JSONL conversation logging
- Rich CLI interface with prompt_toolkit
- Groq provider (free)
