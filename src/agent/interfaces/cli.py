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
from ..clients.exceptions import RateLimitError
from ..clients.factory import get_fallback_models
from ..planning import TaskManager, TaskStatus
from ..mcp import MCPManager
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
        self.task_manager = TaskManager()
        self.mcp_manager = MCPManager()

        # Setup prompt with history
        history_path = config.paths.base / ".agent_history"
        self.session = PromptSession(
            history=FileHistory(str(history_path))
        )

    async def run(self):
        """Main CLI loop."""
        console.print(Panel(
            "[bold cyan]Self-Improving AI Agent[/bold cyan]\n"
            "Type your message or /help for commands\n"
            f"Model: [bright_white]{self.main_agent.model}[/bright_white] ({self.main_agent.provider})\n"
            f"Prompt version: v{self.prompt_manager.current_version('main_agent')}",
            title="Welcome",
            border_style="cyan",
        ))

        while True:
            try:
                # Get user input (using asyncio.to_thread for Python 3.9+)
                user_input = await asyncio.to_thread(
                    self.session.prompt, "You: "
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

        while True:  # Loop for retry on fallback
            try:
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
                break  # Success - exit retry loop

            except RateLimitError as e:
                # Get fallback options
                fallbacks = get_fallback_models(e.model)

                if not fallbacks:
                    console.print(Panel(
                        f"[red]Rate limit reached for {e.model}.[/red]\n"
                        "No alternative models available.\n"
                        "Please wait and try again later.",
                        title="Rate Limit Error",
                        border_style="red",
                    ))
                    # Remove failed message from history
                    if self.main_agent.conversation_history:
                        self.main_agent.conversation_history.pop()
                    break

                # Show rate limit message and ask for confirmation
                alternative = fallbacks[0]
                if await self._confirm_fallback(e.model, alternative, e.retry_after):
                    # User confirmed - switch model and retry
                    old_model = self.main_agent.model
                    self.main_agent.set_model(alternative)
                    console.print(
                        f"[green]Switched from {old_model} to {self.main_agent.model} "
                        f"({self.main_agent.provider})[/green]"
                    )
                    # Remove failed message from history before retry
                    if self.main_agent.conversation_history:
                        self.main_agent.conversation_history.pop()
                    # Continue loop to retry with new model
                    continue
                else:
                    # User declined
                    console.print(
                        "[yellow]Keeping current model. "
                        "Please wait before sending another message.[/yellow]"
                    )
                    # Remove failed message from history
                    if self.main_agent.conversation_history:
                        self.main_agent.conversation_history.pop()
                    break

    async def _confirm_fallback(
        self,
        current_model: str,
        alternative: str,
        retry_after: float | None = None,
    ) -> bool:
        """Ask user to confirm switching to fallback model."""
        retry_info = ""
        if retry_after:
            retry_info = f" (retry available in {int(retry_after)}s)"

        console.print(Panel(
            f"[yellow]Rate limit reached for {current_model}.[/yellow]{retry_info}\n\n"
            f"Switch to [cyan]{alternative}[/cyan]?",
            title="Rate Limit",
            border_style="yellow",
        ))

        try:
            response = await asyncio.to_thread(
                self.session.prompt,
                "Switch model? [y/n]: "
            )
            return response.strip().lower() in ["y", "yes"]
        except (KeyboardInterrupt, EOFError):
            return False

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

        elif cmd in ["/tasks", "/task"]:
            await self._handle_tasks(args)

        elif cmd == "/mcp":
            await self._handle_mcp(args)

        elif cmd == "/tools":
            self._show_tools()

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
            ("/tasks", "List all tasks"),
            ("/task add TEXT", "Create new task"),
            ("/task done ID", "Mark task as completed"),
            ("/task start ID", "Mark task as in progress"),
            ("/task delete ID", "Delete task"),
            ("/task clear", "Clear completed tasks"),
            ("/tools", "List available MCP tools"),
            ("/mcp list", "List MCP servers"),
            ("/mcp connect NAME", "Connect to MCP server"),
            ("/mcp disconnect NAME", "Disconnect from MCP server"),
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
            border_style="cyan",
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
        # Simple heuristic for explicit feedback - patterns from FeedbackDetector
        negative_patterns = [
            "плохо", "ужас", "ошиб", "неправ", "некорр", "не так", "не то",
            "bad", "wrong", "error", "incorrect", "terrible", "awful"
        ]
        is_negative = any(pattern in args.lower() for pattern in negative_patterns)

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
                    border_style="cyan",
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

    # ==================== Task Management ====================

    async def _handle_tasks(self, args: str):
        """Handle task management commands."""
        parts = args.strip().split(maxsplit=1)
        subcmd = parts[0].lower() if parts else ""
        subargs = parts[1] if len(parts) > 1 else ""

        if not subcmd or subcmd == "list":
            await self._list_tasks()
        elif subcmd == "add":
            await self._add_task(subargs)
        elif subcmd == "done":
            await self._complete_task(subargs)
        elif subcmd == "start":
            await self._start_task(subargs)
        elif subcmd in ["delete", "rm", "del"]:
            await self._delete_task(subargs)
        elif subcmd == "clear":
            await self._clear_tasks()
        else:
            # Treat as task title if no recognized subcommand
            await self._add_task(args)

    async def _list_tasks(self):
        """Display all tasks."""
        tasks = await self.task_manager.list()

        if not tasks:
            console.print("[dim]No tasks. Use /task add <title> to create one.[/dim]")
            return

        table = Table(title="Tasks", show_header=True)
        table.add_column("ID", style="dim", width=6)
        table.add_column("", width=3)  # Status icon
        table.add_column("Title")
        table.add_column("Priority", width=8)

        priority_labels = {0: "", 1: "[yellow]high[/yellow]", 2: "[red]urgent[/red]"}

        for task in tasks:
            style = "dim" if task.is_completed else ""
            status_style = {
                TaskStatus.PENDING: "",
                TaskStatus.IN_PROGRESS: "[cyan]",
                TaskStatus.COMPLETED: "[dim]",
                TaskStatus.BLOCKED: "[red]",
            }[task.status]

            icon = f"{status_style}{task.status_icon}[/]" if status_style else task.status_icon

            table.add_row(
                task.id[:6],
                icon,
                task.title,
                priority_labels.get(task.priority, ""),
                style=style,
            )

        console.print(table)

        # Show summary
        total = len(tasks)
        completed = sum(1 for t in tasks if t.is_completed)
        pending = total - completed
        console.print(f"\n[dim]{pending} pending, {completed} completed[/dim]")

    async def _add_task(self, title: str):
        """Create a new task."""
        if not title.strip():
            console.print("[red]Usage: /task add <title>[/red]")
            return

        task = await self.task_manager.create(title=title.strip())
        console.print(f"[green]Created task {task.id[:6]}:[/green] {task.title}")

    async def _complete_task(self, task_id: str):
        """Mark a task as completed."""
        if not task_id.strip():
            console.print("[red]Usage: /task done <id>[/red]")
            return

        task = await self.task_manager.complete(task_id.strip())
        if task:
            console.print(f"[green]Completed:[/green] {task.title}")
        else:
            console.print(f"[red]Task not found: {task_id}[/red]")

    async def _start_task(self, task_id: str):
        """Mark a task as in progress."""
        if not task_id.strip():
            console.print("[red]Usage: /task start <id>[/red]")
            return

        task = await self.task_manager.start(task_id.strip())
        if task:
            console.print(f"[cyan]Started:[/cyan] {task.title}")
        else:
            console.print(f"[red]Task not found: {task_id}[/red]")

    async def _delete_task(self, task_id: str):
        """Delete a task."""
        if not task_id.strip():
            console.print("[red]Usage: /task delete <id>[/red]")
            return

        deleted = await self.task_manager.delete(task_id.strip())
        if deleted:
            console.print(f"[green]Deleted task {task_id}[/green]")
        else:
            console.print(f"[red]Task not found: {task_id}[/red]")

    async def _clear_tasks(self):
        """Clear all completed tasks."""
        count = await self.task_manager.clear_completed()
        if count > 0:
            console.print(f"[green]Cleared {count} completed task(s)[/green]")
        else:
            console.print("[dim]No completed tasks to clear[/dim]")

    # ==================== MCP Management ====================

    async def _handle_mcp(self, args: str):
        """Handle MCP commands."""
        parts = args.strip().split(maxsplit=1)
        subcmd = parts[0].lower() if parts else ""
        subargs = parts[1] if len(parts) > 1 else ""

        # Initialize MCP manager if needed
        if not self.mcp_manager._initialized:
            await self.mcp_manager.initialize()

        if not subcmd or subcmd == "list":
            self._list_mcp_servers()
        elif subcmd == "connect":
            await self._mcp_connect(subargs)
        elif subcmd == "disconnect":
            await self._mcp_disconnect(subargs)
        elif subcmd == "add":
            self._mcp_add_hint()
        else:
            console.print(f"[red]Unknown MCP command: {subcmd}[/red]")
            console.print("Available: list, connect, disconnect")

    def _list_mcp_servers(self):
        """List all MCP servers."""
        servers = self.mcp_manager.list_servers()

        if not servers:
            console.print("[dim]No MCP servers configured.[/dim]")
            console.print("[dim]Add servers to ~/.agent/mcp.yaml or data/mcp.yaml[/dim]")
            return

        table = Table(title="MCP Servers", show_header=True)
        table.add_column("Name", style="cyan")
        table.add_column("Status", width=12)
        table.add_column("Tools", width=6)
        table.add_column("Command")

        for server in servers:
            if server["connected"]:
                status = "[green]connected[/green]"
            elif server["enabled"]:
                status = "[yellow]ready[/yellow]"
            else:
                status = "[dim]disabled[/dim]"

            table.add_row(
                server["name"],
                status,
                str(server["tools"]) if server["connected"] else "-",
                server["command"],
            )

        console.print(table)

    async def _mcp_connect(self, server_name: str):
        """Connect to an MCP server."""
        if not server_name.strip():
            console.print("[red]Usage: /mcp connect <server_name>[/red]")
            return

        server_name = server_name.strip()

        try:
            console.print(f"[yellow]Connecting to {server_name}...[/yellow]")
            success = await self.mcp_manager.connect(server_name)
            if success:
                client = self.mcp_manager.registry.get_client(server_name)
                tool_count = len(client.tools) if client else 0
                console.print(f"[green]Connected to {server_name} ({tool_count} tools)[/green]")
            else:
                console.print(f"[red]Failed to connect to {server_name}[/red]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
        except Exception as e:
            console.print(f"[red]Connection error: {e}[/red]")

    async def _mcp_disconnect(self, server_name: str):
        """Disconnect from an MCP server."""
        if not server_name.strip():
            console.print("[red]Usage: /mcp disconnect <server_name>[/red]")
            return

        server_name = server_name.strip()
        success = await self.mcp_manager.disconnect(server_name)
        if success:
            console.print(f"[green]Disconnected from {server_name}[/green]")
        else:
            console.print(f"[red]Server not connected: {server_name}[/red]")

    def _mcp_add_hint(self):
        """Show hint for adding MCP servers."""
        console.print("[yellow]To add MCP servers, edit the config file:[/yellow]")
        console.print()
        console.print("~/.agent/mcp.yaml or data/mcp.yaml")
        console.print()
        console.print("[dim]Example:[/dim]")
        console.print("""
servers:
  filesystem:
    command: npx
    args: ["@anthropic/mcp-server-filesystem", "/home/user"]
    description: File system access

  github:
    command: npx
    args: ["@anthropic/mcp-server-github"]
    env:
      GITHUB_TOKEN: your-token
    description: GitHub API access
""")

    def _show_tools(self):
        """List all available MCP tools."""
        tools = self.mcp_manager.list_tools()

        if not tools:
            console.print("[dim]No tools available.[/dim]")
            console.print("[dim]Connect to MCP servers first: /mcp connect <name>[/dim]")
            return

        table = Table(title="Available Tools", show_header=True)
        table.add_column("Tool", style="cyan")
        table.add_column("Server", style="dim")
        table.add_column("Description")

        for tool in tools:
            desc = tool["description"]
            if len(desc) > 60:
                desc = desc[:57] + "..."
            table.add_row(tool["name"], tool["server"], desc)

        console.print(table)
        console.print(f"\n[dim]{len(tools)} tool(s) from {self.mcp_manager.connected_count} server(s)[/dim]")
