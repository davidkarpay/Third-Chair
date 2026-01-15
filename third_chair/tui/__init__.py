"""TUI module for Third Chair.

Provides a terminal-based graphical interface with:
- Case selection screen
- Split-panel layout with directory tree and chat
- Keyboard navigation
- Vault password dialog for encrypted cases
"""

from .app import ThirdChairApp, run_tui
from .screens import CaseSelectionScreen
from .vault_screen import PasswordDialog, VaultStatusWidget
from .widgets import CaseDirectoryTree, ChatPanel

__all__ = [
    "ThirdChairApp",
    "run_tui",
    "CaseSelectionScreen",
    "CaseDirectoryTree",
    "ChatPanel",
    "PasswordDialog",
    "VaultStatusWidget",
]
