# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [1.5.0] - 2026-06-15

### Added — the agent now actually executes tools (previously a facade)
- **Real agentic loop:** `MainAgent` runs `think → tool_use → tool_result → repeat`
  via `ToolRegistry` (was a single streaming chat with tools never wired in).
  Bounded iterations, loop-detection, tool-errors returned as `tool_result` for
  recovery, real token accounting from provider usage.
- **EditFileTool** (targeted `old_string→new_string` edits, read-before-edit,
  `replace_all`), atomic writes (temp+rename), stale-detection via mtime.
- **Tool safety wired:** confirmation (Confirmator) for write/run/commit and a
  working undo (UndoManager) — previously dead code. Shell-injection closed
  (each sub-command head validated; redirections/subshells blocked in sandbox).
  SSRF guard for `fetch_url`; read offset/limit + large-file cap.
- **MCP tools in the loop:** any configured MCP server's tools (e.g. a memory
  server) are bridged into the registry and callable mid-conversation.
- **Closed-loop self-improvement:** live per-version feedback metrics +
  auto-rollback on degradation; FeedbackDetector no longer mistakes work
  commands ("fix this bug in X") for negative self-feedback; meta-agents
  (versioner/analyzer) protected from rewrite; real prompt validation.
- **FCM backend:** local free-model router as a first-class provider
  (`FCM_BASE_URL`).
- **CI** (GitHub Actions) + real test suite for the loop/tools/memory/MCP/
  self-improvement.

- **Sub-agents + verification run the same tool-loop** (shared `run_tool_loop`),
  no longer single-shot; sub-agent errors propagate instead of masquerading as
  successful output.

### Fixed
- OAuth→API-key fallback on the tool path; `check_api_keys` covers OpenRouter;
  prompt-version symlink falls back to copy on Windows; plugin loader actually
  runs at startup.
- Hardening from final re-audit: shell guards run even outside sandbox;
  redirect-following re-validates every hop against the SSRF guard; anti-loop
  aborts on first repeat; atomic-write uses unique temp names; oversized files
  skip undo journaling; `/tools` lists core+MCP tools; ruff lint enforced in CI.

## [1.4.1] - 2026-06-01

### Changed
- **Provider model refresh (verified against live APIs / provider docs, 2026-06-01):**
  - **Anthropic** — added `claude-opus-4.8` (new flagship) and `claude-opus-4.7`.
  - **SambaNova** — `minimax-m2.5` → `minimax-m2.7`; added `gemma-4-31b`, `gemma-3-12b`
    (live `/models`); removed `deepseek-r1` (no longer served by SambaNova).
  - **OpenRouter** — `qwen3.6-plus-preview` retired → `qwen3-next` (`qwen3-next-80b-a3b-instruct:free`);
    added `qwen3-coder`, `kimi-k2.6`, `glm-4.5-air-free` (live `/models`). Old `qwen3.6-plus`
    kept as an alias.
  - **Groq** — removed `kimi-k2` (deprecated by Groq 2026-03-23 → gpt-oss-120b); Kimi now
    routes to OpenRouter (`kimi-k2.6`).
  - **Cerebras / Zhipu** — already current (GLM-5.1/5/4.7 line, Qwen3-235B, GLM-4.7) — no change.

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
