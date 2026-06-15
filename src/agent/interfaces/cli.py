"""CLI interface for the self-improving agent."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiofiles
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.table import Table
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from ..agents.main_agent import MainAgent
from ..storage.prompts import PromptManager
from ..clients import get_free_models
from ..clients.exceptions import RateLimitError
from ..clients.factory import get_fallback_models
from ..planning import TaskManager, TaskStatus
from ..mcp import MCPManager
from ..config import config
from ..skills.registry import get_skill_registry
from ..skills.bundled import init_bundled_skills
from ..core.output_styles import set_style, list_styles, get_style_name

console = Console()


class AgentCLI:
    """CLI interface for interacting with the self-improving agent."""

    def __init__(
        self,
        main_agent: MainAgent,
        prompt_manager: PromptManager,
        runtime_config=None,
    ):
        self.main_agent = main_agent
        self.prompt_manager = prompt_manager
        self.runtime_config = runtime_config
        self.task_manager = TaskManager()
        self.mcp_manager = MCPManager()

        # Setup prompt with history
        history_path = config.paths.base / ".agent_history"
        self.session = PromptSession(
            history=FileHistory(str(history_path))
        )

        # Initialize bundled skills
        init_bundled_skills()

    async def run(self):
        """Main CLI loop."""
        # Load runtime config
        if self.runtime_config:
            await self.runtime_config.load()

        # Connect configured MCP servers (e.g. claude-memory) and bridge their
        # tools into the agentic loop. Best-effort: never block startup.
        try:
            await self.mcp_manager.initialize()
            results = await self.mcp_manager.connect_all()
            connected = [n for n, ok in results.items() if ok]
            registry = getattr(self.main_agent, "_tool_registry", None)
            if connected and registry is not None:
                added = registry.register_mcp_tools(self.mcp_manager)
                console.print(f"[dim]MCP: {len(connected)} server(s) connected, +{added} tool(s)[/dim]")
        except Exception as e:
            console.print(f"[yellow]MCP setup skipped: {e}[/yellow]")

        console.print(Panel(
            "[bold cyan]Self-Improving AI Agent[/bold cyan]\n"
            "Type your message or /help for commands\n"
            f"Model: [bright_white]{self.main_agent.model}[/bright_white] ({self.main_agent.provider})\n"
            f"Prompt version: v{self.prompt_manager.current_version('main_agent')}",
            title="Welcome",
            border_style="cyan",
        ))

        try:
            while True:
                try:
                    user_input = await asyncio.to_thread(
                        self.session.prompt, "You: "
                    )

                    if not user_input.strip():
                        continue

                    if user_input.startswith("/"):
                        should_exit = await self._handle_command(user_input)
                        if should_exit:
                            break
                        continue

                    await self._chat(user_input)

                except KeyboardInterrupt:
                    console.print("\n[yellow]Interrupted. Type /quit to exit.[/yellow]")
                except EOFError:
                    break
        finally:
            # Auto-save session on exit
            await self.main_agent.save_session()
            try:
                await self.mcp_manager.shutdown()
            except Exception:
                pass

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

        elif cmd == "/compact":
            await self._handle_compact()

        elif cmd == "/sessions":
            await self._handle_sessions()

        elif cmd == "/resume":
            await self._handle_resume(args)

        elif cmd == "/cost":
            self._show_cost()

        elif cmd == "/export":
            await self._handle_export(args)

        elif cmd == "/config":
            await self._handle_config(args)

        elif cmd == "/diff":
            self._handle_diff(args)

        elif cmd == "/style":
            self._handle_style(args)

        elif cmd == "/plugins":
            self._handle_plugins()

        elif cmd == "/voice":
            await self._handle_voice()

        elif cmd == "/team":
            await self._handle_team(args)

        elif cmd == "/summary":
            await self._handle_summary()

        elif cmd == "/auth":
            await self._handle_auth(args)

        elif cmd == "/fork":
            await self._handle_fork(args)

        elif cmd == "/forks":
            self._show_forks()

        elif cmd == "/plan":
            await self._handle_plan(args)

        elif cmd == "/explore":
            await self._handle_explore(args)

        elif cmd == "/verify":
            await self._handle_verify()

        else:
            # Check skills registry before giving up
            skill_name = cmd.lstrip("/")
            skill = get_skill_registry().get(skill_name)
            if skill:
                await self._execute_skill(skill, args)
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
            ("/compact", "Compress conversation history"),
            ("/sessions", "List saved sessions"),
            ("/resume ID", "Resume a saved session"),
            ("/cost", "Show token usage and costs"),
            ("/export [md|json]", "Export conversation to file"),
            ("/config [set K V]", "View/change runtime config"),
            ("/diff [V1] [V2]", "Show diff between prompt versions"),
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
            ("/style [NAME]", "Switch output style (default/concise/explanatory/teaching)"),
            ("/plugins", "List loaded plugins"),
            ("/fork NAME DIRECTIVE", "Fork agent in background with inherited context"),
            ("/forks", "Show status of all forks"),
            ("/plan TASK", "Run Plan agent (read-only architecture design)"),
            ("/explore QUERY", "Run Explore agent (read-only codebase search)"),
            ("/verify", "Run Verification agent on recent changes"),
            ("/auth [status|paste]", "Manage Claude subscription auth"),
            ("/voice", "Push-to-talk voice input"),
            ("/team list|add|show", "Team shared memory"),
            ("/summary", "Show/update session notes"),
            ("/clear", "Clear screen"),
            ("/reset", "Reset conversation"),
        ]

        # Append registered skills
        skill_names = get_skill_registry().list_names()
        if skill_names:
            for sname in skill_names:
                skill = get_skill_registry().get(sname)
                if skill:
                    commands.append((f"/{sname}", f"[skill] {skill.description}"))

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
        from ..core.feedback import Feedback, FeedbackDetector

        # Use FeedbackDetector's pattern matching to classify
        detector = FeedbackDetector()
        detected = detector.detect(args)
        is_negative = detected.type == "negative" if detected else False

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

        # Cost tracking
        ct = self.main_agent.cost_tracker
        table.add_row("Tokens", f"{ct.total_tokens:,}")
        table.add_row("Requests", str(ct.total_requests))
        cost = ct.total_cost
        table.add_row("Cost", f"${cost:.4f}" if cost > 0 else "FREE")

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

    # ==================== New Features ====================

    async def _handle_compact(self):
        """Compact conversation history."""
        history = self.main_agent.conversation_history
        if len(history) <= 4:
            console.print("[dim]History too short to compact.[/dim]")
            return
        console.print("[yellow]Compacting conversation history...[/yellow]")
        old_count, new_count = await self.main_agent.compact_history()
        console.print(
            f"[green]Compacted: {old_count} messages -> {new_count} messages[/green]"
        )

    async def _handle_sessions(self):
        """List saved sessions."""
        if not self.main_agent.session_store:
            console.print("[dim]Session storage not available.[/dim]")
            return
        sessions = await self.main_agent.session_store.list_sessions(limit=15)
        if not sessions:
            console.print("[dim]No saved sessions.[/dim]")
            return

        table = Table(title="Saved Sessions", show_header=True)
        table.add_column("ID", style="cyan", width=14)
        table.add_column("Summary", max_width=40)
        table.add_column("Model", style="dim")
        table.add_column("Turns", justify="right", width=6)
        table.add_column("Updated", style="dim", width=19)

        current_id = self.main_agent.session_id
        for s in sessions:
            sid = s.session_id[:12]
            if s.session_id == current_id:
                sid += " *"
            table.add_row(
                sid,
                s.summary[:40],
                s.model.split("/")[-1] if "/" in s.model else s.model,
                str(s.turn_count),
                s.updated_at[:19],
            )
        console.print(table)
        console.print("[dim]Use /resume <id> to load a session[/dim]")

    async def _handle_resume(self, args: str):
        """Resume a saved session."""
        if not args.strip():
            console.print("[red]Usage: /resume <session_id>[/red]")
            return
        session_id = args.strip()
        success = await self.main_agent.load_session(session_id)
        if success:
            turns = len(self.main_agent.conversation_history) // 2
            console.print(
                f"[green]Resumed session {self.main_agent.session_id[:12]} "
                f"({turns} turns, model: {self.main_agent.model})[/green]"
            )
        else:
            console.print(f"[red]Session not found: {session_id}[/red]")

    def _show_cost(self):
        """Show token usage and cost breakdown."""
        ct = self.main_agent.cost_tracker
        breakdown = ct.get_breakdown()

        if not breakdown:
            console.print("[dim]No usage recorded yet.[/dim]")
            return

        table = Table(title="Token Usage & Cost", show_header=True)
        table.add_column("Model", style="cyan")
        table.add_column("Input", justify="right")
        table.add_column("Output", justify="right")
        table.add_column("Total", justify="right", style="bold")
        table.add_column("Requests", justify="right")
        table.add_column("Cost", justify="right", style="green")

        for entry in breakdown:
            cost_str = f"${entry['cost']:.4f}" if entry["cost"] > 0 else "FREE"
            table.add_row(
                entry["model"],
                f"{entry['input_tokens']:,}",
                f"{entry['output_tokens']:,}",
                f"{entry['total_tokens']:,}",
                str(entry["requests"]),
                cost_str,
            )

        # Totals
        table.add_section()
        total_cost = ct.total_cost
        table.add_row(
            "TOTAL",
            "", "",
            f"{ct.total_tokens:,}",
            str(ct.total_requests),
            f"${total_cost:.4f}" if total_cost > 0 else "FREE",
            style="bold",
        )
        console.print(table)

    async def _handle_export(self, args: str):
        """Export conversation to file."""
        parts = args.strip().split()
        fmt = parts[0] if parts else "md"
        custom_path = parts[1] if len(parts) > 1 else None

        if fmt not in ("md", "json"):
            console.print("[red]Format must be 'md' or 'json'[/red]")
            return

        history = self.main_agent.conversation_history
        if not history:
            console.print("[dim]No conversation to export.[/dim]")
            return

        # Build export dir
        export_dir = config.paths.data / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        sid = self.main_agent.session_id[:8]
        filename = custom_path or str(export_dir / f"{sid}_{ts}.{fmt}")

        ct = self.main_agent.cost_tracker
        metadata = {
            "session_id": self.main_agent.session_id,
            "model": self.main_agent.model,
            "provider": self.main_agent.provider,
            "prompt_version": self.prompt_manager.current_version("main_agent"),
            "turns": len(history) // 2,
            "tokens": ct.total_tokens,
            "cost": ct.total_cost,
            "exported_at": datetime.now(timezone.utc).isoformat() + "Z",
        }

        if fmt == "json":
            content = json.dumps(
                {"metadata": metadata, "messages": history},
                indent=2, ensure_ascii=False,
            )
        else:
            lines = [
                f"# Conversation Export",
                f"",
                f"- **Session**: {metadata['session_id']}",
                f"- **Model**: {metadata['model']} ({metadata['provider']})",
                f"- **Turns**: {metadata['turns']}",
                f"- **Tokens**: {metadata['tokens']:,}",
                f"- **Exported**: {metadata['exported_at'][:19]}",
                f"",
                "---",
                "",
            ]
            for msg in history:
                role = "You" if msg["role"] == "user" else "Assistant"
                lines.append(f"## {role}\n")
                lines.append(msg.get("content", "") + "\n")
            content = "\n".join(lines)

        async with aiofiles.open(filename, "w") as f:
            await f.write(content)
        console.print(f"[green]Exported to {filename}[/green]")

    async def _handle_config(self, args: str):
        """View or change runtime config."""
        if not self.runtime_config:
            console.print("[dim]Runtime config not available.[/dim]")
            return

        parts = args.strip().split(maxsplit=2)

        if not parts:
            # Show all config
            all_cfg = self.runtime_config.list_all()
            table = Table(title="Runtime Configuration", show_header=True)
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="green")
            table.add_column("Default", style="dim")
            table.add_column("", width=3)

            for key, info in all_cfg.items():
                marker = "[yellow]*[/yellow]" if info["overridden"] else ""
                table.add_row(key, str(info["value"]), str(info["default"]), marker)
            console.print(table)
            console.print("[dim]* = overridden. Use /config set KEY VALUE or /config reset KEY[/dim]")
            return

        subcmd = parts[0].lower()
        if subcmd == "set" and len(parts) >= 3:
            key, value = parts[1], parts[2]
            ok, msg = await self.runtime_config.set(key, value)
            if ok:
                # If model changed, apply to agent
                if key == "model":
                    try:
                        self.main_agent.set_model(value)
                        msg += f" (switched to {self.main_agent.model})"
                    except Exception as e:
                        msg += f" (failed to switch: {e})"
                console.print(f"[green]{msg}[/green]")
            else:
                console.print(f"[red]{msg}[/red]")
        elif subcmd == "reset" and len(parts) >= 2:
            ok, msg = await self.runtime_config.reset(parts[1])
            console.print(f"[green]{msg}[/green]" if ok else f"[red]{msg}[/red]")
        else:
            console.print("[red]Usage: /config, /config set KEY VALUE, /config reset KEY[/red]")

    def _handle_diff(self, args: str):
        """Show diff between prompt versions."""
        parts = args.strip().split()
        current = self.prompt_manager.current_version("main_agent")

        try:
            if len(parts) == 0:
                if current <= 1:
                    console.print("[yellow]Only one version exists.[/yellow]")
                    return
                version_a, version_b = current - 1, current
            elif len(parts) == 1:
                version_a, version_b = int(parts[0]), current
            elif len(parts) == 2:
                version_a, version_b = int(parts[0]), int(parts[1])
            else:
                console.print("[red]Usage: /diff [V1] [V2][/red]")
                return
        except ValueError:
            console.print("[red]Version numbers must be integers.[/red]")
            return

        try:
            diff_data = self.prompt_manager.get_diff("main_agent", version_a, version_b)
        except FileNotFoundError as e:
            console.print(f"[red]{e}[/red]")
            return

        if not diff_data["diff"]:
            console.print("[green]No differences between versions.[/green]")
            return

        syntax = Syntax(diff_data["diff"], "diff", theme="monokai", line_numbers=True)
        console.print(Panel(
            syntax,
            title=f"Diff: v{version_a} -> v{version_b} "
                  f"(+{diff_data['added_lines']}/-{diff_data['removed_lines']})",
            border_style="cyan",
        ))

    async def _handle_fork(self, args: str):
        """Fork the agent in background."""
        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            console.print("[red]Usage: /fork NAME DIRECTIVE[/red]")
            console.print("[dim]Example: /fork research Find all API endpoints in the codebase[/dim]")
            return
        name, directive = parts[0], parts[1]
        result = await self.main_agent.fork(name, directive)
        console.print(f"[green]{result}[/green]")

    def _show_forks(self):
        """Show status of all forks."""
        fm = self.main_agent.fork_manager
        status = fm.get_status()
        pending = status["pending"]
        completed = status["completed"]

        if not pending and not completed:
            console.print("[dim]No forks. Use /fork NAME DIRECTIVE to spawn one.[/dim]")
            return

        if pending:
            console.print(f"[yellow]Running: {', '.join(pending)}[/yellow]")

        if completed:
            table = Table(title="Fork Results", show_header=True)
            table.add_column("Name", style="cyan")
            table.add_column("Status")
            table.add_column("Duration", justify="right")

            for c in completed:
                status_str = "[green]OK[/green]" if c["success"] else "[red]FAIL[/red]"
                table.add_row(c["name"], status_str, f"{c['duration_ms']}ms")
            console.print(table)

        # Show detailed results for completed forks
        for result in fm.get_completed():
            if result.output:
                console.print(Panel(
                    Markdown(result.output[:2000]),
                    title=f"Fork: {result.name}",
                    border_style="green" if result.success else "red",
                ))

    async def _handle_plan(self, args: str):
        """Run Plan agent for architecture design."""
        if not args.strip():
            console.print("[red]Usage: /plan TASK_DESCRIPTION[/red]")
            return
        console.print("[yellow]Planning...[/yellow]")
        result = await self.main_agent.plan(args.strip())
        console.print(Panel(
            Markdown(result),
            title="Implementation Plan",
            border_style="cyan",
        ))

    async def _handle_explore(self, args: str):
        """Run Explore agent for codebase search."""
        if not args.strip():
            console.print("[red]Usage: /explore QUERY[/red]")
            return
        console.print("[yellow]Exploring...[/yellow]")
        result = await self.main_agent.explore(args.strip())
        console.print(Panel(Markdown(result), title="Explore Results", border_style="cyan"))

    async def _handle_verify(self):
        """Manually trigger Verification agent."""
        if not self.main_agent.pipeline:
            console.print("[red]Pipeline not initialized.[/red]")
            return
        console.print("[yellow]Running adversarial verification...[/yellow]")
        from ..agents.verification import VerificationAgent
        va = self.main_agent.pipeline.verification
        # Build context from conversation
        task = ""
        for msg in self.main_agent.conversation_history:
            if msg["role"] == "user" and not msg["content"].startswith("[Context"):
                task = msg["content"][:500]
                break
        report = await va.verify(task or "Recent changes", [], "")
        verdict = VerificationAgent.parse_verdict(report)
        color = "green" if verdict == "PASS" else ("red" if verdict == "FAIL" else "yellow")
        console.print(Panel(
            Markdown(report),
            title=f"Verification: [{color}]{verdict}[/{color}]",
            border_style=color,
        ))

    async def _execute_skill(self, skill, args: str):
        """Execute a registered skill."""
        prompt = await skill.get_prompt(args)
        console.print(f"[dim]Running /{skill.name}...[/dim]")
        await self._chat(prompt)

    def _handle_style(self, args: str):
        """Switch output style."""
        if not args.strip():
            styles = list_styles()
            table = Table(title="Output Styles", show_header=True)
            table.add_column("Name", style="cyan")
            table.add_column("Description")
            table.add_column("", width=3)
            for s in styles:
                marker = "[green]*[/green]" if s["active"] else ""
                table.add_row(s["name"], s["description"], marker)
            console.print(table)
            return
        if set_style(args.strip()):
            console.print(f"[green]Output style: {get_style_name()}[/green]")
        else:
            console.print(f"[red]Unknown style: {args.strip()}. Use /style to see options.[/red]")

    def _handle_plugins(self):
        """List loaded plugins."""
        try:
            from ..plugins.loader import PluginLoader
            loader = PluginLoader()
            plugins = loader.list_plugins()
            if not plugins:
                discovered = loader.discover()
                if discovered:
                    console.print(f"[yellow]{len(discovered)} plugin(s) found but not loaded.[/yellow]")
                else:
                    console.print("[dim]No plugins found in ~/.agent/plugins/[/dim]")
                return
            table = Table(title="Loaded Plugins", show_header=True)
            table.add_column("Name", style="cyan")
            table.add_column("Version")
            table.add_column("Description")
            for p in plugins:
                table.add_row(p.name, p.version, p.description)
            console.print(table)
        except Exception as e:
            console.print(f"[red]Plugin error: {e}[/red]")

    async def _handle_auth(self, args: str):
        """Manage Claude subscription authentication."""
        from ..auth.oauth import OAuthManager

        parts = args.strip().split(maxsplit=1)
        subcmd = parts[0].lower() if parts else "status"

        mgr = OAuthManager()

        if subcmd == "status":
            tokens = mgr.load_tokens()
            if not tokens:
                console.print("[dim]No OAuth token found.[/dim]")
                console.print(
                    "[dim]Options:\n"
                    "  1. Run `claude setup-token` in Claude Code CLI, then /auth paste TOKEN\n"
                    "  2. Set CLAUDE_CODE_OAUTH_TOKEN env var\n"
                    "  3. Use ANTHROPIC_API_KEY for pay-per-token billing[/dim]"
                )
                return

            table = Table(title="Auth Status", show_header=False)
            table.add_column("Key", style="cyan")
            table.add_column("Value")
            table.add_row("Mode", "Subscription (OAuth)" if tokens.is_subscriber else "OAuth")
            table.add_row("Expired", "[red]Yes[/red]" if tokens.is_expired else "[green]No[/green]")
            if tokens.subscription_type:
                table.add_row("Plan", tokens.subscription_type.upper())
            if tokens.scopes:
                table.add_row("Scopes", ", ".join(tokens.scopes))
            console.print(table)

            # Try to get subscription info
            console.print("[dim]Fetching subscription info...[/dim]")
            info = await mgr.get_subscription_info()
            if info:
                if info.email:
                    console.print(f"  Email: {info.email}")
                if info.subscription_type:
                    console.print(f"  Plan: [green]{info.subscription_type.upper()}[/green]")
                if info.rate_limit_tier:
                    console.print(f"  Rate tier: {info.rate_limit_tier}")

        elif subcmd == "paste":
            token = parts[1].strip() if len(parts) > 1 else ""
            if not token:
                console.print("[yellow]Paste your OAuth token (from `claude setup-token`):[/yellow]")
                token = await asyncio.to_thread(self.session.prompt, "Token: ")
                token = token.strip()
            if not token:
                console.print("[red]No token provided.[/red]")
                return

            # Save to credentials file
            import json
            cred_path = Path.home() / ".claude" / ".credentials.json"
            cred_path.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if cred_path.exists():
                try:
                    data = json.loads(cred_path.read_text())
                except Exception:
                    pass
            data["claudeAiOauth"] = {
                "accessToken": token,
                "scopes": ["user:profile", "user:inference"],
            }
            cred_path.write_text(json.dumps(data, indent=2))
            console.print(f"[green]Token saved to {cred_path}[/green]")
            console.print("[dim]Restart the agent or switch to a Claude model to use it.[/dim]")

        elif subcmd == "refresh":
            tokens = await mgr.refresh_if_needed()
            if tokens:
                console.print("[green]Token refreshed.[/green]")
            else:
                console.print("[red]Refresh failed. Re-run `claude setup-token`.[/red]")

        else:
            console.print("[dim]Usage: /auth [status|paste|refresh][/dim]")

    async def _handle_voice(self):
        """Push-to-talk voice input."""
        from .voice import check_voice_deps, VoiceRecorder, transcribe
        import tempfile

        available, reason = check_voice_deps()
        if not available:
            console.print(f"[red]{reason}[/red]")
            return

        recorder = VoiceRecorder()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            audio_path = f.name

        console.print("[yellow]Press Enter to start recording...[/yellow]")
        await asyncio.to_thread(self.session.prompt, "")
        recorder.start(audio_path)
        console.print("[green]Recording... Press Enter to stop.[/green]")
        await asyncio.to_thread(self.session.prompt, "")
        recorder.stop()

        console.print("[yellow]Transcribing...[/yellow]")
        text = await transcribe(audio_path)

        import os
        os.unlink(audio_path)

        if text:
            console.print(f"[cyan]You said:[/cyan] {text}")
            await self._chat(text)
        else:
            console.print("[red]Could not transcribe audio.[/red]")

    async def _handle_team(self, args: str):
        """Team shared memory management."""
        from ..memory.team_sync import TeamMemorySync
        team = TeamMemorySync()
        parts = args.strip().split(maxsplit=1)
        subcmd = parts[0].lower() if parts else "list"
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd == "list":
            entries = team.list_entries()
            if not entries:
                console.print("[dim]No team memory entries.[/dim]")
            else:
                for e in entries:
                    console.print(f"  - {e}")
        elif subcmd == "show" and subargs:
            content = team.load(subargs)
            if content:
                from rich.markdown import Markdown as RichMD
                console.print(Panel(RichMD(content), title=f"Team: {subargs}", border_style="cyan"))
            else:
                console.print(f"[red]Entry not found: {subargs}[/red]")
        elif subcmd == "add" and subargs:
            console.print("[yellow]Enter content (end with empty line):[/yellow]")
            lines = []
            while True:
                line = await asyncio.to_thread(self.session.prompt, "  ")
                if not line.strip():
                    break
                lines.append(line)
            content = "\n".join(lines)
            ok, msg = team.save(subargs, content)
            console.print(f"[green]{msg}[/green]" if ok else f"[red]{msg}[/red]")
        elif subcmd == "delete" and subargs:
            if team.delete(subargs):
                console.print(f"[green]Deleted: {subargs}[/green]")
            else:
                console.print(f"[red]Not found: {subargs}[/red]")
        else:
            console.print("[dim]Usage: /team list | /team add KEY | /team show KEY | /team delete KEY[/dim]")

    async def _handle_summary(self):
        """Show or update session memory notes."""
        sm = self.main_agent.session_memory
        content = sm.get_content()
        if content:
            console.print(Panel(
                Markdown(content),
                title="Session Notes",
                border_style="cyan",
            ))
        else:
            console.print("[yellow]No session notes yet. Generating...[/yellow]")
            result = await sm.extract(self.main_agent.conversation_history)
            if result:
                console.print(Panel(Markdown(result), title="Session Notes", border_style="green"))
            else:
                console.print("[dim]Not enough conversation to extract notes.[/dim]")

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
