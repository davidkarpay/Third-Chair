"""Screens for Third Chair TUI."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.table import Table
from textual.app import ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Footer, Header, Markdown, Static


def discover_cases(search_paths: list[Path]) -> list[dict]:
    """Scan directories for case.json files.

    Args:
        search_paths: List of paths to search for cases.

    Returns:
        List of case info dicts with path, case_id, evidence_count, last_modified.
    """
    cases = []
    seen_paths = set()

    for search_path in search_paths:
        if not search_path.exists():
            continue

        # Check if this path itself contains a case.json
        case_file = search_path / "case.json"
        if case_file.exists() and search_path not in seen_paths:
            case_info = _load_case_info(case_file)
            if case_info:
                seen_paths.add(search_path)
                cases.append(case_info)

        # Search subdirectories (one level deep)
        if search_path.is_dir():
            for subdir in search_path.iterdir():
                if not subdir.is_dir():
                    continue
                if subdir in seen_paths:
                    continue

                case_file = subdir / "case.json"
                if case_file.exists():
                    case_info = _load_case_info(case_file)
                    if case_info:
                        seen_paths.add(subdir)
                        cases.append(case_info)

    # Sort by last modified (most recent first)
    cases.sort(key=lambda c: c["last_modified"], reverse=True)
    return cases


def _load_case_info(case_file: Path) -> Optional[dict]:
    """Load case info from a case.json file.

    Args:
        case_file: Path to case.json.

    Returns:
        Case info dict or None if invalid.
    """
    try:
        with open(case_file) as f:
            data = json.load(f)

        case_id = data.get("case_id", case_file.parent.name)
        evidence_items = data.get("evidence_items", [])
        evidence_count = len(evidence_items)

        # Count media files
        media_count = sum(
            1 for e in evidence_items
            if e.get("file_type") in ("VIDEO", "AUDIO")
        )

        # Get witness count
        witnesses = data.get("witnesses", {})
        witness_list = witnesses.get("witnesses", [])
        witness_count = len(witness_list)

        # Get proposition count
        propositions = data.get("propositions", [])
        proposition_count = len(propositions)

        # Get modification time
        stat = case_file.stat()
        last_modified = datetime.fromtimestamp(stat.st_mtime)

        return {
            "path": case_file.parent,
            "case_id": case_id,
            "evidence_count": evidence_count,
            "media_count": media_count,
            "witness_count": witness_count,
            "proposition_count": proposition_count,
            "last_modified": last_modified,
        }
    except (json.JSONDecodeError, KeyError, OSError):
        return None


class CaseSelectionScreen(Screen):
    """Screen for selecting a case to open."""

    BINDINGS = [
        ("escape", "quit", "Quit"),
        ("q", "quit", "Quit"),
        ("enter", "select_case", "Open Case"),
    ]

    DEFAULT_CSS = """
    CaseSelectionScreen {
        align: center middle;
    }

    CaseSelectionScreen > Container {
        width: 90%;
        height: 80%;
        border: solid $primary;
        padding: 1 2;
    }

    CaseSelectionScreen > Container > Static {
        text-align: center;
        margin-bottom: 1;
    }

    CaseSelectionScreen DataTable {
        height: 1fr;
    }

    CaseSelectionScreen .no-cases {
        text-align: center;
        color: $warning;
        margin: 2;
    }
    """

    def __init__(
        self,
        search_paths: list[Path],
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        """Initialize the case selection screen.

        Args:
            search_paths: Paths to search for cases.
            name: Screen name.
            id: Screen ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.search_paths = search_paths
        self.cases: list[dict] = []
        self.selected_case: Optional[dict] = None

    def compose(self) -> ComposeResult:
        """Compose the screen."""
        yield Header()
        with Container():
            yield Static("[bold]Select a Case[/bold]", id="title")
            yield DataTable(id="case-table")
        yield Footer()

    def on_mount(self) -> None:
        """Handle mount event."""
        self.cases = discover_cases(self.search_paths)

        table = self.query_one("#case-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Add columns
        table.add_column("Case ID", width=25)
        table.add_column("Evidence", width=10)
        table.add_column("Media", width=8)
        table.add_column("Witnesses", width=10)
        table.add_column("Modified", width=20)
        table.add_column("Path", width=40)

        if not self.cases:
            # No cases found
            container = self.query_one(Container)
            container.mount(
                Static(
                    "No cases found. Process an Axon ZIP file first.",
                    classes="no-cases",
                )
            )
            return

        # Add rows
        for case in self.cases:
            table.add_row(
                case["case_id"],
                str(case["evidence_count"]),
                str(case["media_count"]),
                str(case["witness_count"]),
                case["last_modified"].strftime("%Y-%m-%d %H:%M"),
                str(case["path"]),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        if event.row_key is not None and self.cases:
            row_index = event.cursor_row
            if 0 <= row_index < len(self.cases):
                self.selected_case = self.cases[row_index]
                self.dismiss(self.selected_case)

    def action_select_case(self) -> None:
        """Select the currently highlighted case."""
        if not self.cases:
            return

        table = self.query_one("#case-table", DataTable)
        row_index = table.cursor_row
        if 0 <= row_index < len(self.cases):
            self.selected_case = self.cases[row_index]
            self.dismiss(self.selected_case)

    def action_quit(self) -> None:
        """Quit without selecting a case."""
        self.dismiss(None)


class FileViewerScreen(ModalScreen):
    """Modal screen for viewing file contents."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
        ("up", "scroll_up", "Scroll Up"),
        ("down", "scroll_down", "Scroll Down"),
        ("pageup", "page_up", "Page Up"),
        ("pagedown", "page_down", "Page Down"),
        ("home", "scroll_home", "Top"),
        ("end", "scroll_end", "Bottom"),
    ]

    DEFAULT_CSS = """
    FileViewerScreen {
        align: center middle;
    }

    FileViewerScreen > Container {
        width: 80%;
        height: 80%;
        border: solid $primary;
        background: $surface;
    }

    FileViewerScreen .file-title {
        dock: top;
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $primary;
        color: $text;
    }

    FileViewerScreen .file-content {
        height: 1fr;
        padding: 1;
    }

    FileViewerScreen .close-hint {
        dock: bottom;
        text-align: center;
        padding: 1;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        file_path: Path,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        """Initialize the file viewer screen.

        Args:
            file_path: Path to the file to display.
            name: Screen name.
            id: Screen ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.file_path = file_path

    def compose(self) -> ComposeResult:
        """Compose the screen."""
        with Container():
            yield Static(f"[bold]{self.file_path.name}[/bold]", classes="file-title")
            yield VerticalScroll(
                self._create_content_widget(),
                classes="file-content",
                id="file-scroll",
            )
            yield Static(
                "[dim]Press ESC/Q to close | ↑↓ PgUp/PgDn to scroll[/dim]",
                classes="close-hint",
            )

    def _create_content_widget(self) -> Static | Markdown:
        """Create the appropriate content widget based on file type."""
        try:
            content = self.file_path.read_text(encoding="utf-8")
        except Exception as e:
            return Static(f"[red]Error reading file: {e}[/red]")

        if self.file_path.suffix.lower() == ".md":
            return Markdown(content)
        else:
            return Static(content)

    def on_mount(self) -> None:
        """Focus the scroll container on mount for keyboard navigation."""
        self.query_one("#file-scroll").focus()

    def action_dismiss(self) -> None:
        """Dismiss the modal."""
        self.dismiss()

    def action_scroll_up(self) -> None:
        """Scroll up one line."""
        self.query_one("#file-scroll").scroll_up()

    def action_scroll_down(self) -> None:
        """Scroll down one line."""
        self.query_one("#file-scroll").scroll_down()

    def action_page_up(self) -> None:
        """Scroll up one page."""
        self.query_one("#file-scroll").scroll_page_up()

    def action_page_down(self) -> None:
        """Scroll down one page."""
        self.query_one("#file-scroll").scroll_page_down()

    def action_scroll_home(self) -> None:
        """Scroll to top."""
        self.query_one("#file-scroll").scroll_home()

    def action_scroll_end(self) -> None:
        """Scroll to bottom."""
        self.query_one("#file-scroll").scroll_end()
