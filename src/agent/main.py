"""Main entry point for the self-improving agent."""

import asyncio
import logging
import os
import sys

from .agents.main_agent import MainAgent
from .clients import create_client
from .clients.factory import get_provider
from .storage.prompts import PromptManager
from .storage.logs import LogManager
from .interfaces.cli import AgentCLI
from .config import config

logger = logging.getLogger(__name__)


def check_api_keys(model: str) -> bool:
    """Check if required API keys are available for the model."""
    provider = get_provider(model)

    provider_keys = {
        "anthropic": ("ANTHROPIC_API_KEY", "https://console.anthropic.com/"),
        "zhipu": ("ZHIPU_API_KEY", "https://open.bigmodel.cn/"),
        "groq": ("GROQ_API_KEY", "https://console.groq.com/"),
        "cerebras": ("CEREBRAS_API_KEY", "https://cloud.cerebras.ai/"),
        "sambanova": ("SAMBANOVA_API_KEY", "https://cloud.sambanova.ai/"),
        "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/keys"),
    }

    api_config = provider_keys.get(provider)
    if api_config:
        env_var, key_url = api_config
        if not os.getenv(env_var):
            logger.error(
                "%s environment variable is not set. Get key from: %s",
                env_var,
                key_url,
            )
            return False

    return True


def cli_main():
    """Entry point for CLI."""
    # Get default model from config
    default_model = config.models.default

    # Check API keys
    if not check_api_keys(default_model):
        sys.exit(1)

    # Initialize storage
    prompt_manager = PromptManager()
    log_manager = LogManager()

    # Create main agent client
    try:
        client = create_client(default_model)
    except ValueError as e:
        logger.error("Error creating client: %s", e)
        sys.exit(1)

    # Create feedback detector.
    # Pattern-based detection works without Anthropic; Anthropic only enables LLM fallback.
    feedback_detector = None
    try:
        from .core.feedback import FeedbackDetector

        anthropic_client = None
        if os.getenv("ANTHROPIC_API_KEY"):
            from anthropic import Anthropic
            anthropic_client = Anthropic()
        else:
            logger.warning(
                "ANTHROPIC_API_KEY not set. Using pattern-based feedback detection only."
            )

        feedback_detector = FeedbackDetector(anthropic_client)
    except Exception as e:
        logger.warning("Could not initialize feedback detector: %s", e)

    # Create session store and cost tracker
    from .storage.sessions import SessionStore
    from .core.cost_tracker import CostTracker
    from .core.runtime_config import RuntimeConfig

    session_store = SessionStore()
    cost_tracker = CostTracker()
    runtime_config = RuntimeConfig()

    # Tool registry — powers the agentic loop (filesystem/shell/git/search/web).
    # sandbox_mode=True confines file ops to the launch directory (safe default).
    # Built BEFORE the pipeline so sub-agents/verification get the same tools.
    from pathlib import Path
    import sys as _sys
    from .tools.registry import ToolRegistry
    from .approval.undo import UndoManager
    from .approval.confirmator import (
        Confirmator, PendingAction, ActionType, ConfirmationResult,
    )

    undo_manager = UndoManager()  # records before/after of every file mutation

    # Interactive terminal → confirm write/run/commit. Headless → bypass.
    confirm_callback = None
    if _sys.stdin.isatty():
        _confirmator = Confirmator(interactive=True)
        _ACTION = {
            "write_file": ActionType.FILE_WRITE,
            "edit_file": ActionType.FILE_WRITE,
            "run_command": ActionType.COMMAND_EXECUTE,
            "git_commit": ActionType.GIT_COMMIT,
        }

        async def confirm_callback(name, kwargs):  # noqa: F811
            action = PendingAction(
                action_type=_ACTION.get(name, ActionType.DESTRUCTIVE),
                description=f"{name}: {kwargs.get('path') or kwargs.get('command') or ''}",
                details=kwargs,
                risk_level="medium",
            )
            res = await _confirmator.confirm(action)
            return res.result == ConfirmationResult.APPROVED

    tool_registry = ToolRegistry(
        working_dir=Path.cwd(),
        sandbox_mode=True,
        confirm_callback=confirm_callback,
        undo_manager=undo_manager,
    )

    # Create agent pipeline (connects all agents) — sub-agents share the registry.
    from .agents.orchestrator import AgentOrchestrator
    from .agents.pipeline import AgentPipeline

    orchestrator = AgentOrchestrator(client, prompt_manager, log_manager)
    pipeline = AgentPipeline(client=client, orchestrator=orchestrator, tool_registry=tool_registry)

    # Create main agent with full pipeline
    main_agent = MainAgent(
        client=client,
        prompt_manager=prompt_manager,
        log_manager=log_manager,
        feedback_detector=feedback_detector,
        session_store=session_store,
        cost_tracker=cost_tracker,
        pipeline=pipeline,
        tool_registry=tool_registry,
    )

    # Create and run CLI
    cli = AgentCLI(main_agent, prompt_manager, runtime_config=runtime_config)

    # Run the async event loop
    asyncio.run(cli.run())


if __name__ == "__main__":
    cli_main()
