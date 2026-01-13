"""Logging configuration for Third Chair.

Provides consistent logging across all modules with:
- Console output with colors (via Rich)
- File logging for debugging
- Configurable log levels
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


# Global console for rich output
console = Console()

# Default log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
SIMPLE_FORMAT = "%(message)s"


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    rich_output: bool = True,
) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file to write logs to
        rich_output: Whether to use Rich for console output

    Returns:
        Configured root logger
    """
    # Convert level string to logging constant
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Get root logger
    logger = logging.getLogger("third_chair")
    logger.setLevel(log_level)

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    if rich_output:
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
        )
        console_handler.setFormatter(logging.Formatter(SIMPLE_FORMAT))
    else:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        file_handler.setLevel(logging.DEBUG)  # File gets all messages
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Args:
        name: Module name (e.g., "third_chair.transcription")

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class ProgressLogger:
    """Logger that shows progress for batch operations."""

    def __init__(self, total: int, description: str = "Processing"):
        """
        Initialize progress logger.

        Args:
            total: Total number of items
            description: Description of the operation
        """
        self.total = total
        self.description = description
        self.current = 0
        self.logger = get_logger("third_chair.progress")

    def update(self, message: str = "") -> None:
        """Update progress by one."""
        self.current += 1
        pct = (self.current / self.total) * 100 if self.total > 0 else 100

        if message:
            console.print(f"  [{self.current}/{self.total}] {message}")
        else:
            console.print(f"  [{self.current}/{self.total}] ({pct:.0f}%)")

    def complete(self) -> None:
        """Mark as complete."""
        console.print(f"[green]✓ {self.description} complete ({self.total} items)[/green]")

    def error(self, message: str) -> None:
        """Log an error."""
        console.print(f"[red]✗ Error: {message}[/red]")
        self.logger.error(message)
