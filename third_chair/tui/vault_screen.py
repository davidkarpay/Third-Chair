"""Vault-related TUI screens and dialogs."""

from pathlib import Path
from typing import Callable, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class PasswordDialog(ModalScreen[Optional[str]]):
    """Modal dialog for entering vault password.

    Returns the password if submitted, None if cancelled.

    Usage:
        self.push_screen(PasswordDialog(case_name), callback=self._on_password)

        def _on_password(self, password: Optional[str]):
            if password:
                # Use password
            else:
                # Cancelled
    """

    CSS = """
    PasswordDialog {
        align: center middle;
    }

    PasswordDialog > Container {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    PasswordDialog .dialog-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
    }

    PasswordDialog .dialog-subtitle {
        text-align: center;
        color: $text-muted;
        width: 100%;
        margin-bottom: 1;
    }

    PasswordDialog .error-message {
        text-align: center;
        color: $error;
        width: 100%;
        height: 1;
        margin-bottom: 1;
    }

    PasswordDialog Input {
        width: 100%;
        margin-bottom: 1;
    }

    PasswordDialog .button-row {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    PasswordDialog Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        case_name: str,
        error_message: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        """Initialize the password dialog.

        Args:
            case_name: Name of the case being unlocked.
            error_message: Optional error message to display (e.g., "Invalid password").
            name: Widget name.
        """
        super().__init__(name=name)
        self.case_name = case_name
        self.error_message = error_message

    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        with Container():
            yield Static("[bold]Vault Locked[/bold]", classes="dialog-title")
            yield Static(f"Case: {self.case_name}", classes="dialog-subtitle")

            # Error message (if any)
            error_text = self.error_message or ""
            yield Static(error_text, id="error-label", classes="error-message")

            yield Input(
                placeholder="Enter password...",
                password=True,
                id="password-input",
            )

            with Center(classes="button-row"):
                yield Button("Unlock", id="unlock-button", variant="primary")
                yield Button("Cancel", id="cancel-button")

    def on_mount(self) -> None:
        """Focus the password input on mount."""
        self.query_one("#password-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in password input."""
        self._submit_password()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "unlock-button":
            self._submit_password()
        elif event.button.id == "cancel-button":
            self.dismiss(None)

    def _submit_password(self) -> None:
        """Submit the password."""
        password_input = self.query_one("#password-input", Input)
        password = password_input.value.strip()

        if not password:
            self._show_error("Password required")
            return

        self.dismiss(password)

    def _show_error(self, message: str) -> None:
        """Show an error message.

        Args:
            message: Error message to display.
        """
        error_label = self.query_one("#error-label", Static)
        error_label.update(f"[red]{message}[/red]")

    def action_cancel(self) -> None:
        """Cancel the dialog."""
        self.dismiss(None)


class VaultStatusWidget(Static):
    """Widget showing vault status in the UI.

    Displays lock/unlock status and remaining session time.
    """

    CSS = """
    VaultStatusWidget {
        width: auto;
        height: 1;
        padding: 0 1;
    }

    VaultStatusWidget.locked {
        color: $error;
    }

    VaultStatusWidget.unlocked {
        color: $success;
    }

    VaultStatusWidget.unencrypted {
        color: $text-muted;
    }
    """

    def __init__(
        self,
        case_dir: Optional[Path] = None,
        name: Optional[str] = None,
    ) -> None:
        """Initialize the vault status widget.

        Args:
            case_dir: Path to case directory.
            name: Widget name.
        """
        super().__init__(name=name)
        self.case_dir = case_dir

    def on_mount(self) -> None:
        """Update status on mount."""
        self.update_status()

    def update_status(self) -> None:
        """Update the vault status display."""
        if self.case_dir is None:
            self.update("")
            self.remove_class("locked", "unlocked", "unencrypted")
            return

        try:
            from ..vault import is_vault_encrypted, get_vault_session

            if not is_vault_encrypted(self.case_dir):
                self.update("[dim]Unencrypted[/dim]")
                self.remove_class("locked", "unlocked")
                self.add_class("unencrypted")
                return

            session = get_vault_session(self.case_dir)
            if session:
                remaining = session.time_remaining()
                if remaining:
                    minutes = int(remaining.total_seconds() / 60)
                    self.update(f"[green]Unlocked[/green] ({minutes}m)")
                else:
                    self.update("[green]Unlocked[/green]")
                self.remove_class("locked", "unencrypted")
                self.add_class("unlocked")
            else:
                self.update("[red]Locked[/red]")
                self.remove_class("unlocked", "unencrypted")
                self.add_class("locked")

        except ImportError:
            # Vault module not available
            self.update("")
            self.remove_class("locked", "unlocked", "unencrypted")
