"""Staging screen for managing ZIP file imports."""

from pathlib import Path
from typing import Optional

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static

from ..staging import StagingManager, ZipPreview


class StagingScreen(Screen):
    """Screen for managing staged ZIP files and imports."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("p", "process_selected", "Process", show=True),
        Binding("d", "delete_selected", "Delete", show=True),
        Binding("enter", "process_selected", "Process", show=False),
    ]

    DEFAULT_CSS = """
    StagingScreen {
        layout: grid;
        grid-size: 2 1;
        grid-columns: 1fr 1fr;
    }

    StagingScreen > .left-panel {
        height: 100%;
        border-right: solid $primary;
    }

    StagingScreen > .right-panel {
        height: 100%;
    }

    StagingScreen .panel-title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $primary;
        color: $text;
    }

    StagingScreen .status-bar {
        dock: bottom;
        height: 3;
        padding: 1;
        background: $surface;
        border-top: solid $primary-lighten-1;
    }

    StagingScreen DataTable {
        height: 1fr;
    }

    StagingScreen .preview-content {
        height: 1fr;
        padding: 1;
    }

    StagingScreen .preview-section {
        margin-bottom: 1;
    }

    StagingScreen .preview-label {
        color: $text-muted;
    }

    StagingScreen .preview-value {
        color: $text;
    }

    StagingScreen .toc-table {
        height: auto;
        max-height: 50%;
        margin-top: 1;
        border: solid $primary-darken-1;
    }

    StagingScreen .no-selection {
        text-align: center;
        color: $text-muted;
        margin: 2;
    }

    StagingScreen .error-text {
        color: $error;
    }

    StagingScreen .success-text {
        color: $success;
    }
    """

    def __init__(
        self,
        manager: StagingManager,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        """Initialize the staging screen.

        Args:
            manager: StagingManager instance.
            name: Screen name.
            id: Screen ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.manager = manager
        self.previews: list[ZipPreview] = []
        self.selected_preview: Optional[ZipPreview] = None

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()

        # Left panel: ZIP list
        with Vertical(classes="left-panel"):
            yield Static("[bold]Staged ZIP Files[/bold]", classes="panel-title")
            yield DataTable(id="zip-table")
            with Container(classes="status-bar"):
                yield Static("", id="status-text")

        # Right panel: Preview
        with Vertical(classes="right-panel"):
            yield Static("[bold]Preview[/bold]", classes="panel-title")
            yield VerticalScroll(
                Static("Select a ZIP file to preview", classes="no-selection"),
                id="preview-scroll",
                classes="preview-content",
            )

        yield Footer()

    def on_mount(self) -> None:
        """Handle mount event."""
        self._setup_table()
        self.action_refresh()

    def _setup_table(self) -> None:
        """Set up the ZIP table."""
        table = self.query_one("#zip-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        table.add_column("Case ID", width=20)
        table.add_column("Size", width=10)
        table.add_column("Files", width=8)
        table.add_column("ToC", width=5)

    def action_refresh(self) -> None:
        """Refresh the ZIP list."""
        self.previews = self.manager.scan_incoming()

        table = self.query_one("#zip-table", DataTable)
        table.clear()

        for preview in self.previews:
            toc_status = "✓" if preview.has_toc else "✗"
            table.add_row(
                preview.case_id[:20],
                f"{preview.zip_size_mb:.1f} MB",
                str(preview.file_count),
                toc_status,
            )

        # Update status
        status = self.manager.get_status()
        status_text = self.query_one("#status-text", Static)
        status_text.update(
            f"Incoming: {status.incoming_count}  |  "
            f"Processing: {status.processing_count}  |  "
            f"Failed: {status.failed_count}"
        )

        # Clear preview if no files
        if not self.previews:
            self.selected_preview = None
            self._update_preview(None)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        if event.cursor_row is not None and 0 <= event.cursor_row < len(self.previews):
            self.selected_preview = self.previews[event.cursor_row]
            self._update_preview(self.selected_preview)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight (cursor movement)."""
        if event.cursor_row is not None and 0 <= event.cursor_row < len(self.previews):
            self.selected_preview = self.previews[event.cursor_row]
            self._update_preview(self.selected_preview)

    def _update_preview(self, preview: Optional[ZipPreview]) -> None:
        """Update the preview panel."""
        scroll = self.query_one("#preview-scroll", VerticalScroll)

        # Remove existing content
        scroll.remove_children()

        if preview is None:
            scroll.mount(Static("Select a ZIP file to preview", classes="no-selection"))
            return

        # Build preview content
        content = self._build_preview_content(preview)
        scroll.mount(content)

    def _build_preview_content(self, preview: ZipPreview) -> Static:
        """Build preview content widget."""
        lines = []

        # Header
        lines.append(f"[bold]{preview.zip_path.name}[/bold]")
        lines.append("")

        # Basic info
        lines.append(f"[dim]Case ID:[/dim] {preview.case_id}")
        lines.append(f"[dim]Size:[/dim] {preview.zip_size_mb:.2f} MB")

        if preview.court_case:
            lines.append(f"[dim]Court Case:[/dim] {preview.court_case}")

        if preview.agency:
            lines.append(f"[dim]Agency:[/dim] {preview.agency}")

        lines.append("")

        # File counts
        lines.append("[bold]Files[/bold]")
        lines.append(f"  Total: {preview.file_count}")
        if preview.video_count:
            lines.append(f"  Video: {preview.video_count}")
        if preview.audio_count:
            lines.append(f"  Audio: {preview.audio_count}")
        if preview.document_count:
            lines.append(f"  Document: {preview.document_count}")
        if preview.image_count:
            lines.append(f"  Image: {preview.image_count}")
        if preview.file_types.get("other", 0):
            lines.append(f"  Other: {preview.file_types['other']}")

        lines.append("")

        # ToC status
        if preview.has_toc:
            lines.append(f"[bold]Table of Contents[/bold] [green]✓[/green] ({len(preview.toc_entries)} entries)")
            lines.append("")

            # Show ToC entries
            if preview.toc_entries:
                lines.append("[dim]" + "-" * 50 + "[/dim]")
                lines.append("[dim]Filename                      Type       Officer[/dim]")
                lines.append("[dim]" + "-" * 50 + "[/dim]")

                for entry in preview.toc_entries[:15]:  # Show first 15
                    filename = str(entry.get("filename", ""))[:28]
                    file_type = str(entry.get("file_type", entry.get("category", "")))[:10]
                    officer = str(entry.get("officer", ""))[:10]
                    lines.append(f"{filename:<30} {file_type:<10} {officer}")

                if len(preview.toc_entries) > 15:
                    lines.append(f"[dim]... and {len(preview.toc_entries) - 15} more entries[/dim]")
        else:
            lines.append("[bold]Table of Contents[/bold] [red]✗ Not found[/red]")

        # Validation errors
        if preview.validation_errors:
            lines.append("")
            lines.append("[bold red]Validation Errors[/bold red]")
            for error in preview.validation_errors:
                lines.append(f"  [red]• {error}[/red]")

        return Static("\n".join(lines))

    def action_process_selected(self) -> None:
        """Process the selected ZIP file."""
        if not self.selected_preview:
            self.notify("No ZIP file selected", severity="warning")
            return

        zip_path = self.selected_preview.zip_path

        if not zip_path.exists():
            self.notify(f"File not found: {zip_path.name}", severity="error")
            self.action_refresh()
            return

        # Show processing notification
        self.notify(f"Processing {zip_path.name}...", severity="information")

        # Process in background
        def on_complete(case_id: str, success: bool) -> None:
            if success:
                self.call_from_thread(
                    self.notify,
                    f"Successfully imported {case_id}",
                    severity="information",
                )
            else:
                self.call_from_thread(
                    self.notify,
                    f"Failed to import {case_id}",
                    severity="error",
                )
            self.call_from_thread(self.action_refresh)

        import threading
        def do_process():
            result = self.manager.process_zip(zip_path)
            on_complete(
                result.case.case_id if result.case else zip_path.stem,
                result.success
            )

        thread = threading.Thread(target=do_process, daemon=True)
        thread.start()

    def action_delete_selected(self) -> None:
        """Delete the selected ZIP file."""
        if not self.selected_preview:
            self.notify("No ZIP file selected", severity="warning")
            return

        zip_path = self.selected_preview.zip_path

        if self.manager.delete_from_incoming(zip_path):
            self.notify(f"Deleted {zip_path.name}", severity="information")
            self.action_refresh()
        else:
            self.notify(f"Failed to delete {zip_path.name}", severity="error")
