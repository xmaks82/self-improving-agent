# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [1.4.0] - 2026-06-01

### Added
- **Hybrid memory retrieval** — long-term memory now combines vector similarity
  (embeddings) with keyword matching, fused via Reciprocal Rank Fusion (RRF).
  Optional and graceful: without an embeddings backend the agent falls back to
  keyword search, so it works out of the box.
- **Pluggable embeddings backend** — any OpenAI-compatible `/v1/embeddings`
  endpoint (local llama-server, Ollama, OpenAI, …) via `EMBEDDINGS_URL`. New
  `EmbeddingsConfig` + `memory/embeddings.py` client. Best-effort: any failure
  transparently falls back to keyword retrieval. Endpoint stays in your private
  `.env` — nothing of your infrastructure ships in the repo.
- Embeddings are computed on memory write and stored in the existing `embedding`
  column; query embedding + cosine ranking over the embedded pool at recall time.

### Fixed
- **Non-Latin keyword extraction** — keyword tokenizer used an ASCII-only regex
  (`[a-zA-Z]`) and silently dropped Cyrillic (and other scripts), so keyword
  recall returned nothing for non-English queries. Now Unicode-aware (`[^\W\d_]`).

### Changed
- **Claude Opus 4.6** — Anthropic's new flagship model (model ID: `claude-opus-4-6`, 200K context, 128K max output, $5/$25 per 1M tokens)
- Updated Anthropic model mappings: Sonnet 4.5, Haiku 4.5
- Claude Opus 4.5 marked as legacy

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
