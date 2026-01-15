"""Main TUI application for Third Chair."""

import json
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Footer, Header, Static

from .screens import CaseSelectionScreen, FileViewerScreen, discover_cases
from .widgets import CaseDirectoryTree, CaseInfoPanel, ChatPanel
from .vault_screen import PasswordDialog

# NOTE: intent_extractor imports are deferred to function-level for faster startup
# from ..chat.intent_extractor import extract_intent, format_confirmation_prompt, ExtractedIntent, IntentResult


class ThirdChairApp(App):
    """Third Chair TUI Application.

    A terminal-based interface for legal case research with:
    - Directory tree navigation (left panel)
    - Interactive chat assistant (right panel)
    """

    TITLE = "Third Chair"
    SUB_TITLE = "Legal Discovery Assistant"

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-container {
        layout: horizontal;
        height: 1fr;
    }

    #left-panel {
        width: 35%;
        height: 100%;
        border: solid $primary;
        padding: 0 1;
    }

    #right-panel {
        width: 65%;
        height: 100%;
        padding: 0 1;
    }

    #case-info {
        dock: top;
        height: 1;
        padding: 0 1;
        background: $surface;
    }

    #directory-tree {
        height: 100%;
    }

    .panel-title {
        dock: top;
        text-align: center;
        text-style: bold;
        padding: 0 1;
        margin-bottom: 1;
    }

    Footer {
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("tab", "switch_panel", "Switch Panel", show=True),
        Binding("?", "show_help", "Help", show=True),
        Binding("ctrl+l", "clear_chat", "Clear Chat", show=False),
    ]

    def __init__(
        self,
        case_path: Optional[Path] = None,
        search_paths: Optional[list[Path]] = None,
    ) -> None:
        """Initialize the application.

        Args:
            case_path: Path to case directory (skips selection if provided).
            search_paths: Paths to search for cases.
        """
        super().__init__()
        self.case_path = case_path
        self.search_paths = search_paths or [
            Path.cwd(),
            Path("/mnt/d/Third_Chair"),
        ]
        self.case = None
        self.registry = None
        self._active_panel = "chat"  # "tree" or "chat"

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield Header()
        yield Static("", id="case-info")
        with Horizontal(id="main-container"):
            with Container(id="left-panel"):
                yield Static("Case Files", classes="panel-title")
                # Tree will be mounted after case is loaded
            with Container(id="right-panel"):
                yield Static("Research Assistant", classes="panel-title")
                yield ChatPanel(id="chat-panel")
        yield Footer()

    def on_mount(self) -> None:
        """Handle mount event."""
        if self.case_path and self.case_path.exists():
            # Load case directly
            self.call_after_refresh(self._load_case_and_focus, self.case_path)
        else:
            # Show case selection screen with callback
            self.push_screen(
                CaseSelectionScreen(self.search_paths),
                callback=self._on_case_selected,
            )

    def _on_case_selected(self, result: Optional[dict]) -> None:
        """Handle case selection result.

        Args:
            result: Selected case info dict or None if cancelled.
        """
        if result is None:
            self.exit()
            return
        self.call_after_refresh(self._load_case_and_focus, result["path"])

    async def _load_case_and_focus(self, case_path: Path) -> None:
        """Load case and focus chat input.

        Args:
            case_path: Path to case directory.
        """
        await self._load_case(case_path)
        try:
            chat_panel = self.query_one("#chat-panel", ChatPanel)
            chat_panel.focus_input()
        except Exception:
            pass

    async def _load_case(self, case_path: Path, password_error: str = None) -> None:
        """Load a case and update the UI.

        Handles encrypted vaults by showing a password dialog.

        Args:
            case_path: Path to case directory.
            password_error: Error message from previous password attempt.
        """
        from ..models import Case
        from ..chat import ToolRegistry

        case_file = case_path / "case.json"
        encrypted_case_file = case_path / "case.json.enc"

        if not case_file.exists() and not encrypted_case_file.exists():
            self.notify(f"Case not found: {case_path}", severity="error")
            self.exit()
            return

        # Check if vault is encrypted and needs unlocking
        try:
            from ..vault import is_vault_encrypted, is_vault_unlocked, VaultManager, InvalidPasswordError

            if is_vault_encrypted(case_path) and not is_vault_unlocked(case_path):
                # Show password dialog
                self.push_screen(
                    PasswordDialog(
                        case_name=case_path.name,
                        error_message=password_error,
                    ),
                    callback=lambda password: self._on_vault_password(case_path, password),
                )
                return
        except ImportError:
            pass  # Vault module not available

        # Load case (vault is either unlocked or unencrypted)
        try:
            self.case = Case.load(case_file)
        except Exception as e:
            self.notify(f"Error loading case: {e}", severity="error")
            self.exit()
            return

        self.case_path = case_path
        self.registry = ToolRegistry(self.case)

        # Show vault status in title if encrypted
        try:
            from ..vault import is_vault_encrypted
            if is_vault_encrypted(case_path):
                self.sub_title = f"Case: {self.case.case_id} [Encrypted]"
        except ImportError:
            pass

        # Update case info
        info_widget = self.query_one("#case-info", Static)
        info_text = (
            f"[bold]Case:[/bold] {self.case.case_id} | "
            f"[dim]Evidence:[/dim] {self.case.evidence_count} | "
            f"[dim]Witnesses:[/dim] {len(self.case.witnesses.witnesses)} | "
            f"[dim]Propositions:[/dim] {len(self.case.propositions)}"
        )
        info_widget.update(info_text)

        # Mount directory tree
        left_panel = self.query_one("#left-panel", Container)
        tree = CaseDirectoryTree(case_path, id="directory-tree")
        await left_panel.mount(tree)

        # Update title
        self.sub_title = f"Case: {self.case.case_id}"

    def _on_vault_password(self, case_path: Path, password: str | None) -> None:
        """Handle vault password dialog result.

        Args:
            case_path: Path to the case directory.
            password: Password entered, or None if cancelled.
        """
        if password is None:
            # User cancelled - exit or show case selection
            self.notify("Vault unlock cancelled", severity="warning")
            self.exit()
            return

        # Try to unlock the vault
        try:
            from ..vault import VaultManager, InvalidPasswordError

            vm = VaultManager(case_path)
            vm.unlock(password)

            # Success - continue loading the case
            self.call_after_refresh(self._load_case_and_focus, case_path)

        except InvalidPasswordError:
            # Wrong password - show dialog again with error
            self.call_after_refresh(
                self._load_case,
                case_path,
                "Invalid password. Please try again.",
            )

        except Exception as e:
            self.notify(f"Vault error: {e}", severity="error")
            self.exit()

    def on_chat_panel_chat_submitted(self, event: ChatPanel.ChatSubmitted) -> None:
        """Handle chat submission."""
        query = event.query
        chat_panel = self.query_one("#chat-panel", ChatPanel)

        # Process the command
        response = self._process_chat_command(query)
        # Only add response if not empty (async commands handle their own response)
        if response:
            chat_panel.add_response(response)

    def _process_chat_command(self, cmd: str) -> str:
        """Process a chat command and return the response.

        Args:
            cmd: The command to process.

        Returns:
            Response text.
        """
        if not self.registry or not self.case:
            return "[red]No case loaded.[/red]"

        cmd_lower = cmd.lower().strip()

        # Help command
        if cmd_lower in ("help", "?", "h"):
            return self._get_help_text()

        # Case info
        if cmd_lower == "case":
            return self._get_case_info()

        # Witnesses
        if cmd_lower == "witnesses":
            return self._get_witnesses()

        # Timeline
        if cmd_lower == "timeline":
            return self._get_timeline()

        # Threats
        if cmd_lower == "threats":
            return self._get_flagged_statements("THREAT_KEYWORD")

        # Violence
        if cmd_lower == "violence":
            return self._get_flagged_statements("VIOLENCE_KEYWORD")

        # Propositions
        if cmd_lower == "propositions":
            return self._get_propositions()

        # Tools list
        if cmd_lower == "tools":
            return self._get_tools()

        # Sync timeline
        if cmd_lower == "sync-timeline" or cmd_lower == "sync":
            return self._get_sync_timeline()

        # Search command
        if cmd_lower.startswith("search "):
            query = cmd[7:].strip()
            return self._search_transcripts(query)

        # Who said command
        if cmd_lower.startswith("who said "):
            quote = cmd[9:].strip()
            return self._who_said(quote)

        # Open/view file command (instant, no LLM)
        if cmd_lower.startswith("open "):
            filename = cmd[5:].strip()
            return self._open_file(filename)

        if cmd_lower.startswith("view "):
            filename = cmd[5:].strip()
            return self._open_file(filename)

        # NLP fallback: Try to extract intent from natural language
        return self._try_nlp_intent(cmd)

    def _get_help_text(self) -> str:
        """Get help text."""
        return """[bold]Available Commands:[/bold]
  [cyan]search <query>[/cyan]    Search transcripts for keywords
  [cyan]threats[/cyan]           Show threat statements
  [cyan]violence[/cyan]          Show violence statements
  [cyan]witnesses[/cyan]         List all witnesses
  [cyan]case[/cyan]              Show case information
  [cyan]timeline[/cyan]          Show timeline (first 20 events)
  [cyan]sync-timeline[/cyan]     Show synchronized multi-camera timeline
  [cyan]propositions[/cyan]      List propositions
  [cyan]tools[/cyan]             List all available tools
  [cyan]who said <quote>[/cyan]  Find who said a quote
  [cyan]open <filename>[/cyan]   Open a .md or .txt file
  [cyan]help[/cyan]              Show this help

[bold]Natural Language:[/bold]
  You can also ask questions naturally, e.g.:
  - "show me all the threats"
  - "who talked about the knife"
  - "find statements about self defense"

  If I'm unsure what you mean, I'll ask for confirmation."""

    def _get_case_info(self) -> str:
        """Get case information."""
        if not self.case:
            return "[red]No case loaded.[/red]"

        lines = [
            "[bold]Case Information[/bold]",
            f"  Case ID: {self.case.case_id}",
            f"  Court Case: {self.case.court_case or '-'}",
            f"  Incident Date: {self.case.incident_date or '-'}",
            f"  Evidence Items: {self.case.evidence_count}",
            f"  Media Files: {self.case.media_count}",
            f"  Witnesses: {len(self.case.witnesses.witnesses)}",
            f"  Propositions: {len(self.case.propositions)}",
        ]
        return "\n".join(lines)

    def _get_witnesses(self) -> str:
        """Get witness list."""
        if not self.case:
            return "[red]No case loaded.[/red]"

        witnesses = self.case.witnesses.witnesses
        if not witnesses:
            return "[yellow]No witnesses found.[/yellow]"

        lines = [f"[bold]Witnesses ({len(witnesses)})[/bold]"]
        for w in witnesses[:15]:
            role = w.role.value if hasattr(w.role, "value") else str(w.role)
            lines.append(f"  {w.display_name} [{role}]")

        if len(witnesses) > 15:
            lines.append(f"  ... and {len(witnesses) - 15} more")

        return "\n".join(lines)

    def _get_timeline(self) -> str:
        """Get timeline events."""
        if not self.case:
            return "[red]No case loaded.[/red]"

        timeline = self.case.timeline
        if not timeline:
            return "[yellow]No timeline events.[/yellow]"

        lines = [f"[bold]Timeline ({len(timeline)} events)[/bold]"]
        for event in timeline[:20]:
            # Prefer timecode_seconds if available (recording offset)
            if event.metadata and "timecode_seconds" in event.metadata:
                total_secs = int(event.metadata["timecode_seconds"])
                mins, secs = divmod(total_secs, 60)
                timestamp = f"{mins}:{secs:02d}"
            elif event.timestamp:
                timestamp = event.timestamp.strftime("%H:%M:%S")
            else:
                timestamp = "?"
            desc = event.description[:60] + "..." if len(event.description) > 60 else event.description
            lines.append(f"  [{timestamp}] {desc}")

        if len(timeline) > 20:
            lines.append(f"  ... and {len(timeline) - 20} more events")

        return "\n".join(lines)

    def _get_flagged_statements(self, flag_type: str) -> str:
        """Get flagged statements."""
        if not self.case:
            return "[red]No case loaded.[/red]"

        statements = []
        for evidence in self.case.evidence_items:
            if not evidence.transcript:
                continue

            for segment in evidence.transcript.segments:
                if not segment.review_flags:
                    continue

                flag_names = [str(f.value) if hasattr(f, "value") else str(f) for f in segment.review_flags]
                if flag_type in flag_names:
                    statements.append({
                        "filename": evidence.filename,
                        "time": segment.start_time,
                        "text": segment.text,
                    })

        if not statements:
            return f"[yellow]No {flag_type.replace('_', ' ').lower()} statements found.[/yellow]"

        label = "Threat" if "THREAT" in flag_type else "Violence"
        lines = [f"[bold]{label} Statements ({len(statements)} found)[/bold]"]

        for stmt in statements[:15]:
            mins = int(stmt["time"] // 60)
            secs = int(stmt["time"] % 60)
            text = stmt["text"][:50] + "..." if len(stmt["text"]) > 50 else stmt["text"]
            lines.append(f"  {stmt['filename']} @ {mins}:{secs:02d}")
            lines.append(f"    \"{text}\"")

        if len(statements) > 15:
            lines.append(f"  ... and {len(statements) - 15} more")

        return "\n".join(lines)

    def _get_propositions(self) -> str:
        """Get propositions."""
        if not self.case:
            return "[red]No case loaded.[/red]"

        propositions = self.case.propositions
        if not propositions:
            return "[yellow]No propositions extracted. Run 'extract-propositions' first.[/yellow]"

        lines = [f"[bold]Propositions ({len(propositions)})[/bold]"]
        for prop in propositions[:10]:
            eval_snap = prop.evaluation
            holds = eval_snap.holds_under_scrutiny.value if eval_snap else "?"
            weight = f"{eval_snap.weight:.2f}" if eval_snap else "?"
            proposit_count = len(prop.skanda.proposits)
            stmt = prop.statement[:40] + "..." if len(prop.statement) > 40 else prop.statement
            lines.append(f"  {prop.id}: {stmt}")
            lines.append(f"    Holds: {holds} | Weight: {weight} | Proposits: {proposit_count}")

        if len(propositions) > 10:
            lines.append(f"  ... and {len(propositions) - 10} more")

        return "\n".join(lines)

    def _get_tools(self) -> str:
        """Get available tools."""
        if not self.registry:
            return "[red]No registry available.[/red]"

        tools = self.registry.list_tools()
        lines = [f"[bold]Available Tools ({len(tools)})[/bold]"]
        for tool in tools[:20]:
            lines.append(f"  {tool.name}: {tool.description[:50]}...")

        if len(tools) > 20:
            lines.append(f"  ... and {len(tools) - 20} more")

        return "\n".join(lines)

    def _get_sync_timeline(self) -> str:
        """Get synchronized multi-camera timeline."""
        if not self.case:
            return "[red]No case loaded.[/red]"

        # Check if synchronized timeline exists in metadata
        sync_data = self.case.metadata.get("synchronized_timeline")
        if not sync_data:
            return (
                "[yellow]No synchronized timeline found.[/yellow]\n\n"
                "Run the following command to build it:\n"
                "  [cyan]third-chair sync-timeline /path/to/case --extract-watermarks[/cyan]"
            )

        camera_views = sync_data.get("camera_views", [])
        events = sync_data.get("events", [])

        lines = [f"[bold]Synchronized Timeline[/bold]"]
        lines.append(f"Cameras: {len(camera_views)} | Events: {len(events)}\n")

        # Camera summary
        lines.append("[cyan]Cameras:[/cyan]")
        for view in camera_views[:5]:
            officer = f" ({view.get('officer')})" if view.get("officer") else ""
            utc_start = view.get("utc_start", "?")[:19]
            lines.append(f"  {view.get('filename', '?')}{officer}")
            lines.append(f"    Start: {utc_start} UTC")

        if len(camera_views) > 5:
            lines.append(f"  ... and {len(camera_views) - 5} more cameras")

        # Events
        lines.append("\n[cyan]Events:[/cyan]")
        for event in events[:15]:
            utc_time = event.get("utc_timestamp", "?")[:19]
            desc = event.get("description", "")[:50]
            importance = event.get("importance", "normal")

            # Importance marker
            marker = ""
            if importance == "critical":
                marker = "[red][!!!][/red] "
            elif importance == "high":
                marker = "[yellow][!][/yellow] "

            lines.append(f"  [{utc_time}] {marker}{desc}")

            # Show relative timecodes for cameras
            timecodes = event.get("relative_timecodes", {})
            if timecodes:
                tc_strs = []
                for ev_id, secs in list(timecodes.items())[:3]:
                    mins = int(secs // 60)
                    sec = int(secs % 60)
                    tc_strs.append(f"{mins}:{sec:02d}")
                if tc_strs:
                    lines.append(f"    [dim][{'] ['.join(tc_strs)}][/dim]")

        if len(events) > 15:
            lines.append(f"\n  ... and {len(events) - 15} more events")

        return "\n".join(lines)

    def _search_transcripts(self, query: str) -> str:
        """Search transcripts for a query."""
        if not self.case:
            return "[red]No case loaded.[/red]"

        query_lower = query.lower()
        results = []

        for evidence in self.case.evidence_items:
            if not evidence.transcript:
                continue

            for segment in evidence.transcript.segments:
                if query_lower in segment.text.lower():
                    results.append({
                        "filename": evidence.filename,
                        "time": segment.start_time,
                        "speaker": segment.speaker,
                        "text": segment.text,
                    })

        if not results:
            return f"[yellow]No results for '{query}'[/yellow]"

        lines = [f"[bold]Search Results for '{query}' ({len(results)} found)[/bold]"]

        for result in results[:15]:
            mins = int(result["time"] // 60)
            secs = int(result["time"] % 60)
            text = result["text"][:60] + "..." if len(result["text"]) > 60 else result["text"]
            lines.append(f"  {result['filename']} @ {mins}:{secs:02d}")
            lines.append(f"    [{result['speaker']}]: \"{text}\"")

        if len(results) > 15:
            lines.append(f"  ... and {len(results) - 15} more results")

        return "\n".join(lines)

    def _who_said(self, quote: str) -> str:
        """Find who said a quote."""
        if not self.case:
            return "[red]No case loaded.[/red]"

        quote_lower = quote.lower()

        for evidence in self.case.evidence_items:
            if not evidence.transcript:
                continue

            for segment in evidence.transcript.segments:
                if quote_lower in segment.text.lower():
                    mins = int(segment.start_time // 60)
                    secs = int(segment.start_time % 60)
                    role = segment.speaker_role if segment.speaker_role else "Unknown"
                    return (
                        f"[bold]Found:[/bold]\n"
                        f"  Speaker: {segment.speaker} ({role})\n"
                        f"  File: {evidence.filename} @ {mins}:{secs:02d}\n"
                        f"  Text: \"{segment.text}\""
                    )

        return f"[yellow]No match found for '{quote}'[/yellow]"

    def _open_file(self, filename: str) -> str:
        """Open a file from the case directory.

        Args:
            filename: Full or partial filename to open.

        Returns:
            Response text (empty if file opens in viewer).
        """
        if not self.case:
            return "[red]No case loaded.[/red]"

        # Search for file in case directory
        case_dir = Path(self.case.case_dir)
        matches = list(case_dir.rglob(f"*{filename}*"))

        if not matches:
            return f"[yellow]File not found: {filename}[/yellow]"

        # Filter to viewable files
        viewable = [m for m in matches if m.suffix.lower() in (".md", ".txt")]

        if len(viewable) == 1:
            self.push_screen(FileViewerScreen(viewable[0]))
            return ""  # Screen handles display

        if len(viewable) > 1:
            # Multiple matches - list them
            lines = [f"[yellow]Multiple matches for '{filename}':[/yellow]"]
            for m in viewable[:10]:
                lines.append(f"  {m.name}")
            if len(viewable) > 10:
                lines.append(f"  ... and {len(viewable) - 10} more")
            lines.append("\n[dim]Be more specific with the filename.[/dim]")
            return "\n".join(lines)

        # No viewable files found, but other matches exist
        if matches:
            return f"[yellow]Cannot view {matches[0].suffix} files in TUI. Only .md and .txt supported.[/yellow]"

        return f"[yellow]File not found: {filename}[/yellow]"

    def _try_nlp_intent(self, cmd: str) -> str:
        """Try to extract intent using NLP.

        Starts a background worker for Ollama call to keep UI responsive.

        Args:
            cmd: The user's natural language query.

        Returns:
            Empty string (result handled async via worker).
        """
        if not self.registry:
            return f"[yellow]Unknown command: {cmd}[/yellow]\nType 'help' for available commands."

        # Show loading indicator
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.show_loading("Thinking...")

        # Start background worker for intent extraction
        self._run_intent_extraction(cmd)

        # Return empty - result will be handled by worker callback
        return ""

    @work(exclusive=True, thread=True)
    def _run_intent_extraction(self, cmd: str) -> None:
        """Run intent extraction in background thread.

        Args:
            cmd: The user's natural language query.
        """
        # Lazy import for faster startup
        from ..chat.intent_extractor import extract_intent

        # Get tool schemas from registry
        tool_schemas = self.registry.get_json_schemas()

        # Build case context for better intent extraction
        case_context = None
        if self.case:
            case_context = (
                f"Case with {self.case.evidence_count} evidence items, "
                f"{len(self.case.witnesses.witnesses)} witnesses"
            )

        # Extract intent (blocking call, but in background thread)
        result = extract_intent(cmd, tool_schemas, case_context)

        # Process result on main thread via call_from_thread
        self.call_from_thread(self._handle_intent_result, result, cmd)

    def _handle_intent_result(self, result, original_cmd: str) -> None:
        """Handle intent extraction result on main thread.

        Args:
            result: The intent extraction result (IntentResult).
            original_cmd: The original command for error messages.
        """
        # Lazy import for faster startup
        from ..chat.intent_extractor import format_confirmation_prompt

        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.hide_loading()

        if not result.success:
            chat_panel.add_response(
                f"[yellow]Could not understand: {original_cmd}[/yellow]\n"
                f"[dim]{result.error}[/dim]\n"
                "Type 'help' for available commands."
            )
            return

        intent = result.intent

        # No matching tool
        if intent.tool_name == "none" or intent.confidence < 0.3:
            chat_panel.add_response(
                f"[yellow]I'm not sure what you mean.[/yellow]\n"
                f"{intent.interpretation}\n"
                "Type 'help' for available commands."
            )
            return

        # High confidence (>0.8): Execute immediately with brief note
        if intent.confidence >= 0.8:
            response = self._execute_intent(intent)
            chat_panel.add_response(response)
            return

        # Medium/low confidence: Show confirmation prompt
        chat_panel.set_pending_intent(intent)
        chat_panel.add_response(format_confirmation_prompt(intent))

    def _execute_intent(self, intent) -> str:
        """Execute an extracted intent via the tool registry.

        Args:
            intent: The intent to execute (ExtractedIntent).

        Returns:
            Result of the tool execution.
        """
        if not self.registry:
            return "[red]No registry available.[/red]"

        # Invoke the tool
        result = self.registry.invoke(intent.tool_name, **intent.parameters)

        if not result.success:
            return f"[red]Error: {result.error}[/red]"

        # Format the result
        if result.data:
            return self._format_tool_result(intent.tool_name, result.data)

        return result.text or "[dim]No results.[/dim]"

    def _format_tool_result(self, tool_name: str, data: any) -> str:
        """Format tool result data for display.

        Args:
            tool_name: Name of the tool that produced the result.
            data: The result data.

        Returns:
            Formatted string for display.
        """
        if isinstance(data, str):
            return data

        if isinstance(data, list):
            if not data:
                return "[yellow]No results found.[/yellow]"

            lines = [f"[bold]Results ({len(data)} found)[/bold]"]
            for item in data[:15]:
                if isinstance(item, dict):
                    # Try common fields
                    text = item.get("text", item.get("description", str(item)))[:60]
                    lines.append(f"  - {text}")
                else:
                    lines.append(f"  - {str(item)[:60]}")

            if len(data) > 15:
                lines.append(f"  ... and {len(data) - 15} more")

            return "\n".join(lines)

        if isinstance(data, dict):
            lines = [f"[bold]{tool_name.replace('_', ' ').title()}[/bold]"]
            for key, value in list(data.items())[:10]:
                lines.append(f"  {key}: {value}")
            return "\n".join(lines)

        return str(data)

    def on_chat_panel_confirmation_response(
        self, event: ChatPanel.ConfirmationResponse
    ) -> None:
        """Handle confirmation response from chat panel."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        response = event.response.lower().strip()
        intent = event.intent

        # Clear the pending intent first
        chat_panel.clear_pending_intent()

        # Handle response
        if response in ("y", "yes", "1"):
            # Execute the intent
            result = self._execute_intent(intent)
            chat_panel.add_response(result)

        elif response in ("n", "no", "cancel"):
            chat_panel.add_response("[dim]Cancelled.[/dim]")

        elif response in ("?", "alternatives", "other"):
            # Show alternatives
            if intent.alternatives:
                lines = ["[bold]Other possibilities:[/bold]"]
                for i, alt in enumerate(intent.alternatives[:5], 1):
                    lines.append(f"  {i}. {alt}")
                lines.append("\nType your query again to try a different approach.")
                chat_panel.add_response("\n".join(lines))
            else:
                chat_panel.add_response(
                    "[dim]No alternatives available. Try rephrasing your query.[/dim]"
                )

        elif response.isdigit():
            # User selected a numbered alternative
            num = int(response)
            if 1 <= num <= len(intent.alternatives):
                chat_panel.add_response(
                    f"[dim]Selected: {intent.alternatives[num-1]}[/dim]\n"
                    "Please rephrase your query more specifically."
                )
            else:
                chat_panel.add_response("[yellow]Invalid selection.[/yellow]")

        else:
            # Treat as a new query
            response_text = self._process_chat_command(event.response)
            chat_panel.add_response(response_text)

    def action_switch_panel(self) -> None:
        """Switch focus between panels."""
        if self._active_panel == "chat":
            # Switch to tree
            tree = self.query_one("#directory-tree", CaseDirectoryTree)
            tree.focus()
            self._active_panel = "tree"
        else:
            # Switch to chat
            chat_panel = self.query_one("#chat-panel", ChatPanel)
            chat_panel.focus_input()
            self._active_panel = "chat"

    def action_clear_chat(self) -> None:
        """Clear the chat history."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.clear_history()

    def action_show_help(self) -> None:
        """Show help in chat."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.add_response(self._get_help_text())

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    def on_directory_tree_file_selected(
        self, event: CaseDirectoryTree.FileSelected
    ) -> None:
        """Handle file selection in the directory tree.

        Opens markdown and text files in a modal viewer.

        Args:
            event: The file selected event.
        """
        path = event.path
        if path.suffix.lower() in (".md", ".txt"):
            self.push_screen(FileViewerScreen(path))


def run_tui(
    case_path: Optional[Path] = None,
    search_paths: Optional[list[Path]] = None,
) -> None:
    """Run the Third Chair TUI.

    Args:
        case_path: Path to case directory (skips selection if provided).
        search_paths: Paths to search for cases.
    """
    app = ThirdChairApp(case_path=case_path, search_paths=search_paths)
    app.run()
