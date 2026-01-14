"""Main TUI application for Third Chair."""

import json
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Footer, Header, Static

from .screens import CaseSelectionScreen, discover_cases
from .widgets import CaseDirectoryTree, CaseInfoPanel, ChatPanel


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

    async def _load_case(self, case_path: Path) -> None:
        """Load a case and update the UI.

        Args:
            case_path: Path to case directory.
        """
        from ..models import Case
        from ..chat import ToolRegistry

        case_file = case_path / "case.json"
        if not case_file.exists():
            self.notify(f"Case not found: {case_path}", severity="error")
            self.exit()
            return

        # Load case
        self.case = Case.load(case_file)
        self.case_path = case_path
        self.registry = ToolRegistry(self.case)

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

    def on_chat_panel_chat_submitted(self, event: ChatPanel.ChatSubmitted) -> None:
        """Handle chat submission."""
        query = event.query
        chat_panel = self.query_one("#chat-panel", ChatPanel)

        # Process the command
        response = self._process_chat_command(query)
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

        # Search command
        if cmd_lower.startswith("search "):
            query = cmd[7:].strip()
            return self._search_transcripts(query)

        # Who said command
        if cmd_lower.startswith("who said "):
            quote = cmd[9:].strip()
            return self._who_said(quote)

        return f"[yellow]Unknown command: {cmd}[/yellow]\nType 'help' for available commands."

    def _get_help_text(self) -> str:
        """Get help text."""
        return """[bold]Available Commands:[/bold]
  [cyan]search <query>[/cyan]    Search transcripts for keywords
  [cyan]threats[/cyan]           Show threat statements
  [cyan]violence[/cyan]          Show violence statements
  [cyan]witnesses[/cyan]         List all witnesses
  [cyan]case[/cyan]              Show case information
  [cyan]timeline[/cyan]          Show timeline (first 20 events)
  [cyan]propositions[/cyan]      List propositions
  [cyan]tools[/cyan]             List all available tools
  [cyan]who said <quote>[/cyan]  Find who said a quote
  [cyan]help[/cyan]              Show this help"""

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
            lines.append(f"  {tool['name']}: {tool['description'][:50]}...")

        if len(tools) > 20:
            lines.append(f"  ... and {len(tools) - 20} more")

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
