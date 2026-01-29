"""CLI interface for the self-improving agent."""

import asyncio
from typing import Optional
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from pathlib import Path

from ..agents.main_agent import MainAgent
from ..storage.prompts import PromptManager
from ..clients import get_available_models, get_free_models
from ..config import config


console = Console()


class AgentCLI:
    """
    CLI interface for interacting with the self-improving agent.

    Commands:
    - /quit, /exit - Exit the agent
    - /help - Show available commands
    - /model [NAME] - Show or switch model
    - /history - Show conversation history
    - /prompt - Show current system prompt
    - /versions - Show prompt version history
    - /rollback N - Rollback to version N
    - /feedback TEXT - Submit explicit feedback
    - /stats - Show session statistics
    - /clear - Clear screen
    - /reset - Reset conversation
    """

    def __init__(self, main_agent: MainAgent, prompt_manager: PromptManager):
        self.main_agent = main_agent
        self.prompt_manager = prompt_manager

        # Setup prompt with history
        history_path = config.paths.base / ".agent_history"
        self.session = PromptSession(
            history=FileHistory(str(history_path))
        )

    async def run(self):
        """Main CLI loop."""
        console.print(Panel(
            "[bold blue]Self-Improving AI Agent[/bold blue]\n"
            "Type your message or /help for commands\n"
            f"Model: [cyan]{self.main_agent.model}[/cyan] ({self.main_agent.provider})\n"
            f"Prompt version: v{self.prompt_manager.current_version('main_agent')}",
            title="Welcome",
            border_style="blue",
        ))

        while True:
            try:
                # Get user input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.session.prompt("You: ")
                )

                if not user_input.strip():
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    should_exit = await self._handle_command(user_input)
                    if should_exit:
                        break
                    continue

                # Regular message - send to agent
                await self._chat(user_input)

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted. Type /quit to exit.[/yellow]")
            except EOFError:
                break

        console.print("[green]Goodbye![/green]")

    async def _chat(self, message: str):
        """Send message to agent and display streaming response."""
        console.print()

        response_text = ""
        spinner = Spinner("dots", text="Thinking...")

        with Live(spinner, refresh_per_second=10, transient=True) as live:
            async for chunk in self.main_agent.chat(message):
                response_text += chunk
                # Update display with markdown rendering
                live.update(Markdown(response_text))

        # Final render
        console.print(Panel(
            Markdown(response_text),
            title="Assistant",
            border_style="green",
        ))
        console.print()

    async def _handle_command(self, command: str) -> bool:
        """
        Handle a command.

        Returns:
            True if should exit, False otherwise
        """
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ["/quit", "/exit", "/q"]:
            return True

        elif cmd == "/help":
            self._show_help()

        elif cmd == "/model":
            self._handle_model(args)

        elif cmd == "/prompt":
            self._show_prompt()

        elif cmd == "/versions":
            self._show_versions()

        elif cmd == "/rollback":
            await self._rollback(args)

        elif cmd == "/feedback":
            await self._submit_feedback(args)

        elif cmd == "/stats":
            self._show_stats()

        elif cmd == "/history":
            self._show_history()

        elif cmd == "/clear":
            console.clear()

        elif cmd == "/reset":
            self.main_agent.reset_conversation()
            console.print("[green]Conversation reset.[/green]")

        elif cmd == "/status":
            self._show_improvement_status()

        else:
            console.print(f"[red]Unknown command: {cmd}[/red]")
            console.print("Type /help for available commands.")

        return False

    def _show_help(self):
        """Display help information."""
        help_table = Table(title="Available Commands", show_header=True)
        help_table.add_column("Command", style="cyan")
        help_table.add_column("Description")

        commands = [
            ("/quit, /exit, /q", "Exit the agent"),
            ("/help", "Show this help message"),
            ("/model [NAME]", "Show current model or switch to NAME"),
            ("/prompt", "Show current system prompt"),
            ("/versions", "Show prompt version history"),
            ("/rollback N", "Rollback to version N"),
            ("/feedback TEXT", "Submit explicit feedback"),
            ("/stats", "Show session statistics"),
            ("/history", "Show conversation history"),
            ("/status", "Show improvement pipeline status"),
            ("/clear", "Clear screen"),
            ("/reset", "Reset conversation"),
        ]

        for cmd, desc in commands:
            help_table.add_row(cmd, desc)

        console.print(help_table)

    def _handle_model(self, args: str):
        """Show or switch the current model."""
        if not args.strip():
            # Show current model and available models
            table = Table(title="Model Configuration", show_header=False)
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Current Model", self.main_agent.model)
            table.add_row("Provider", self.main_agent.provider)

            console.print(table)
            console.print()

            # Show FREE models first
            free_models = get_free_models()
            console.print("[bold green]FREE Models:[/bold green]")
            for provider, models in free_models.items():
                console.print(f"  [cyan]{provider}:[/cyan] {', '.join(models)}")

            console.print()

            # Show paid models
            console.print("[bold yellow]Paid Models:[/bold yellow]")
            console.print("  [cyan]anthropic:[/cyan] claude-opus-4.5, claude-sonnet, claude-haiku")

            console.print()
            console.print("[dim]Usage: /model <name> to switch[/dim]")
            return

        # Switch model
        new_model = args.strip()
        try:
            old_model = self.main_agent.model
            self.main_agent.set_model(new_model)
            console.print(
                f"[green]Switched from {old_model} to {self.main_agent.model} "
                f"({self.main_agent.provider})[/green]"
            )
        except Exception as e:
            console.print(f"[red]Failed to switch model: {e}[/red]")

    def _show_prompt(self):
        """Display current system prompt."""
        prompt = self.prompt_manager.get_current("main_agent")
        version = self.prompt_manager.current_version("main_agent")

        console.print(Panel(
            Markdown(f"```\n{prompt}\n```"),
            title=f"Current System Prompt (v{version})",
            border_style="blue",
        ))

    def _show_versions(self):
        """Display prompt version history."""
        history = self.prompt_manager.get_history("main_agent", limit=10)

        if not history:
            console.print("[yellow]No version history available.[/yellow]")
            return

        table = Table(title="Prompt Version History", show_header=True)
        table.add_column("Version", style="cyan")
        table.add_column("Created", style="green")
        table.add_column("Author")
        table.add_column("Changes")

        current_version = self.prompt_manager.current_version("main_agent")

        for v in history:
            version_str = f"v{v['version']}"
            if v['version'] == current_version:
                version_str += " [current]"

            changes = ", ".join(v.get("changes_summary", [])[:2])
            if len(v.get("changes_summary", [])) > 2:
                changes += "..."

            table.add_row(
                version_str,
                v.get("created_at", "")[:19],
                v.get("author", "unknown"),
                changes or "(initial)",
            )

        console.print(table)

    async def _rollback(self, args: str):
        """Rollback to a specific version."""
        if not args.strip().isdigit():
            console.print("[red]Usage: /rollback VERSION_NUMBER[/red]")
            return

        version = int(args.strip())
        success = self.prompt_manager.rollback(
            "main_agent",
            version,
            "Manual rollback via CLI",
        )

        if success:
            console.print(f"[green]Rolled back to version {version}[/green]")
            console.print("The agent will use the new prompt for subsequent messages.")
        else:
            console.print(f"[red]Version {version} not found[/red]")

    async def _submit_feedback(self, args: str):
        """Submit explicit feedback."""
        if not args.strip():
            console.print("[red]Usage: /feedback YOUR_FEEDBACK_TEXT[/red]")
            return

        # Import here to avoid circular imports
        from ..core.feedback import Feedback

        # Determine feedback type based on content
        negative_words = ["плохо", "не", "ужас", "ошиб", "неправ", "bad", "wrong", "error"]
        is_negative = any(word in args.lower() for word in negative_words)

        feedback = Feedback(
            type="negative" if is_negative else "positive",
            category="explicit",
            raw_text=args,
            confidence=1.0,
            triggered_improvement=True,
        )

        console.print("[yellow]Processing feedback...[/yellow]")

        # Trigger improvement
        await self.main_agent._trigger_improvement(feedback)

        console.print("[green]Feedback submitted. Improvement analysis started.[/green]")
        console.print("Use /status to check progress.")

    def _show_stats(self):
        """Display session statistics."""
        table = Table(title="Session Statistics", show_header=False)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Session ID", self.main_agent.session_id)
        table.add_row("Turns", str(len(self.main_agent.conversation_history) // 2))
        table.add_row("Prompt Version", f"v{self.prompt_manager.current_version('main_agent')}")
        table.add_row("Model", self.main_agent.model)

        # Improvement status
        status = self.main_agent.get_improvement_status()
        if status:
            table.add_row("Improvement", status)

        console.print(table)

    def _show_history(self):
        """Display conversation history."""
        if not self.main_agent.conversation_history:
            console.print("[yellow]No conversation history.[/yellow]")
            return

        for i, msg in enumerate(self.main_agent.conversation_history):
            role = msg["role"]
            content = msg["content"]

            if role == "user":
                console.print(Panel(
                    content[:500] + ("..." if len(content) > 500 else ""),
                    title=f"[{i+1}] You",
                    border_style="blue",
                ))
            else:
                console.print(Panel(
                    content[:500] + ("..." if len(content) > 500 else ""),
                    title=f"[{i+1}] Assistant",
                    border_style="green",
                ))

    def _show_improvement_status(self):
        """Show status of improvement pipeline."""
        status = self.main_agent.get_improvement_status()

        if status is None:
            console.print("[dim]No improvement in progress.[/dim]")
        elif status == "completed":
            console.print("[green]Last improvement completed successfully.[/green]")
            new_version = self.prompt_manager.current_version("main_agent")
            console.print(f"Current prompt version: v{new_version}")
        elif status == "in_progress":
            console.print("[yellow]Improvement in progress...[/yellow]")
        else:
            console.print(f"[red]Improvement {status}[/red]")
