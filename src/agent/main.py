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

    if provider == "anthropic":
        if not os.getenv("ANTHROPIC_API_KEY"):
            logger.error("ANTHROPIC_API_KEY environment variable is not set.")
            return False
    elif provider == "zhipu":
        if not os.getenv("ZHIPU_API_KEY"):
            logger.error("ZHIPU_API_KEY environment variable is not set. Get key from: https://open.bigmodel.cn/")
            return False

    return True


def cli_main():
    """Entry point for CLI."""
    # Get default model from config
    default_model = config.models.default

    # Check API keys
    if not check_api_keys(default_model):
        sys.exit(1)

    # Also need Anthropic for feedback detector and improvement pipeline
    if get_provider(default_model) != "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY not set. Feedback detection disabled.")

    # Initialize storage
    prompt_manager = PromptManager()
    log_manager = LogManager()

    # Create main agent client
    try:
        client = create_client(default_model)
    except ValueError as e:
        logger.error("Error creating client: %s", e)
        sys.exit(1)

    # Create feedback detector (uses Anthropic)
    feedback_detector = None
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            from anthropic import Anthropic
            from .core.feedback import FeedbackDetector
            anthropic_client = Anthropic()
            feedback_detector = FeedbackDetector(anthropic_client)
        except Exception as e:
            logger.warning("Could not initialize feedback detector: %s", e)

    # Create main agent
    main_agent = MainAgent(
        client=client,
        prompt_manager=prompt_manager,
        log_manager=log_manager,
        feedback_detector=feedback_detector,
    )

    # Create and run CLI
    cli = AgentCLI(main_agent, prompt_manager)

    # Run the async event loop
    asyncio.run(cli.run())


if __name__ == "__main__":
    cli_main()
