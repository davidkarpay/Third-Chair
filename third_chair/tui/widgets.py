"""Custom widgets for Third Chair TUI."""

from pathlib import Path
from typing import Optional, TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import (
    DirectoryTree,
    Input,
    Static,
    RichLog,
)
from textual.message import Message

if TYPE_CHECKING:
    from ..chat.intent_extractor import ExtractedIntent


class CaseDirectoryTree(DirectoryTree):
    """Directory tree widget for case file navigation."""

    BINDINGS = [
        ("enter", "select_cursor", "Open"),
    ]

    def __init__(
        self,
        path: Path,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        """Initialize the case directory tree.

        Args:
            path: Root path of the case directory.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(path, name=name, id=id, classes=classes)
        self.case_path = path

    def filter_paths(self, paths: list[Path]) -> list[Path]:
        """Filter paths to show relevant case files.

        Excludes:
        - Hidden files and directories
        - Python cache directories
        - Temporary files
        """
        filtered = []
        for path in paths:
            name = path.name
            # Skip hidden files and directories
            if name.startswith("."):
                continue
            # Skip Python cache
            if name == "__pycache__":
                continue
            # Skip temporary files
            if name.endswith(".tmp") or name.endswith(".temp"):
                continue
            # Skip common non-relevant files
            if name in ("Thumbs.db", ".DS_Store"):
                continue
            filtered.append(path)
        return sorted(filtered, key=lambda p: (not p.is_dir(), p.name.lower()))


class ChatMessage(Static):
    """A single chat message display."""

    def __init__(
        self,
        content: str,
        is_user: bool = False,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        """Initialize a chat message.

        Args:
            content: Message content.
            is_user: Whether this is a user message.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.content = content
        self.is_user = is_user

    def compose(self) -> ComposeResult:
        """Compose the message display."""
        prefix = "You: " if self.is_user else ""
        yield Static(f"{prefix}{self.content}")


class ChatPanel(Container):
    """Chat panel widget with input and message history."""

    DEFAULT_CSS = """
    ChatPanel {
        height: 100%;
        width: 100%;
    }

    ChatPanel > VerticalScroll {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }

    ChatPanel > Input {
        dock: bottom;
        margin-top: 1;
    }

    ChatPanel .user-message {
        color: $text;
        margin-bottom: 1;
    }

    ChatPanel .assistant-message {
        color: $success;
        margin-bottom: 1;
    }
    """

    class ChatSubmitted(Message):
        """Message sent when user submits a chat query."""

        def __init__(self, query: str) -> None:
            """Initialize the message.

            Args:
                query: The user's query.
            """
            self.query = query
            super().__init__()

    class ConfirmationResponse(Message):
        """Message sent when user responds to a confirmation prompt."""

        def __init__(self, response: str, intent: "ExtractedIntent") -> None:
            """Initialize the message.

            Args:
                response: User's response (y/n/?/number).
                intent: The pending intent being confirmed.
            """
            self.response = response
            self.intent = intent
            super().__init__()

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        """Initialize the chat panel.

        Args:
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._history: list[tuple[str, bool]] = []  # (message, is_user)
        self._pending_intent: Optional["ExtractedIntent"] = None
        self._is_loading: bool = False

    def compose(self) -> ComposeResult:
        """Compose the chat panel."""
        yield VerticalScroll(
            RichLog(highlight=True, markup=True, id="chat-log"),
            id="chat-scroll",
        )
        yield Input(placeholder="Enter command (help for commands)", id="chat-input")

    def on_mount(self) -> None:
        """Handle mount event."""
        # Show welcome message
        log = self.query_one("#chat-log", RichLog)
        log.write("[bold]Research Assistant[/bold]")
        log.write("Type 'help' for available commands.")
        log.write("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        query = event.value.strip()
        if not query:
            return

        # Clear input
        event.input.value = ""

        # Check if we're waiting for a confirmation response
        if self._pending_intent is not None:
            log = self.query_one("#chat-log", RichLog)
            log.write(f"[bold cyan]You:[/bold cyan] {query}")

            # Post confirmation response
            self.post_message(self.ConfirmationResponse(query, self._pending_intent))
            return

        # Add to history and display
        self._history.append((query, True))
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold cyan]You:[/bold cyan] {query}")

        # Emit message for parent to handle
        self.post_message(self.ChatSubmitted(query))

    def set_pending_intent(self, intent: "ExtractedIntent") -> None:
        """Set a pending intent awaiting confirmation.

        Args:
            intent: The intent to confirm.
        """
        self._pending_intent = intent
        # Update input placeholder to indicate confirmation mode
        input_widget = self.query_one("#chat-input", Input)
        input_widget.placeholder = "[Y]es / [N]o / [?] alternatives"

    def clear_pending_intent(self) -> None:
        """Clear any pending intent."""
        self._pending_intent = None
        # Restore normal placeholder
        input_widget = self.query_one("#chat-input", Input)
        input_widget.placeholder = "Enter command (help for commands)"

    @property
    def has_pending_intent(self) -> bool:
        """Check if there's a pending intent."""
        return self._pending_intent is not None

    def add_response(self, response: str) -> None:
        """Add an assistant response to the chat.

        Args:
            response: The response text.
        """
        self._history.append((response, False))
        log = self.query_one("#chat-log", RichLog)
        log.write(response)
        log.write("")

    def clear_history(self) -> None:
        """Clear the chat history."""
        self._history.clear()
        log = self.query_one("#chat-log", RichLog)
        log.clear()
        log.write("[bold]Research Assistant[/bold]")
        log.write("Chat history cleared. Type 'help' for commands.")
        log.write("")

    def focus_input(self) -> None:
        """Focus the input field."""
        self.query_one("#chat-input", Input).focus()

    def show_loading(self, message: str = "Thinking...") -> None:
        """Show loading indicator.

        Args:
            message: Loading message to display.
        """
        self._is_loading = True
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[dim italic]{message}[/dim italic]")
        # Disable input while loading
        input_widget = self.query_one("#chat-input", Input)
        input_widget.placeholder = message
        input_widget.disabled = True

    def hide_loading(self) -> None:
        """Hide loading indicator and re-enable input."""
        self._is_loading = False
        input_widget = self.query_one("#chat-input", Input)
        input_widget.disabled = False
        input_widget.placeholder = "Enter command (help for commands)"

    @property
    def is_loading(self) -> bool:
        """Check if currently loading."""
        return self._is_loading


class CaseInfoPanel(Static):
    """Panel displaying case information."""

    def __init__(
        self,
        case_id: str,
        evidence_count: int,
        witness_count: int,
        proposition_count: int,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        """Initialize case info panel.

        Args:
            case_id: Case identifier.
            evidence_count: Number of evidence items.
            witness_count: Number of witnesses.
            proposition_count: Number of propositions.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.case_id = case_id
        self.evidence_count = evidence_count
        self.witness_count = witness_count
        self.proposition_count = proposition_count

    def render(self) -> Text:
        """Render the case info."""
        text = Text()
        text.append("Case: ", style="bold")
        text.append(self.case_id, style="cyan")
        text.append(" | Evidence: ", style="dim")
        text.append(str(self.evidence_count))
        text.append(" | Witnesses: ", style="dim")
        text.append(str(self.witness_count))
        if self.proposition_count > 0:
            text.append(" | Propositions: ", style="dim")
            text.append(str(self.proposition_count))
        return text
