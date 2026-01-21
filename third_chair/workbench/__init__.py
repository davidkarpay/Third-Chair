"""Evidence Workbench - Extraction, embedding, and connection detection for legal evidence.

This module provides tools for:
- Extracting granular facts from transcripts using LLM
- Generating embeddings for semantic similarity search
- Detecting inconsistencies and connections between evidence items
"""

from .config import WorkbenchConfig, get_workbench_config, set_workbench_config
from .database import WorkbenchDB, get_workbench_db, init_workbench
from .models import (
    ConnectionStatus,
    ConnectionType,
    Extraction,
    ExtractionType,
    Severity,
    SuggestedConnection,
)

__all__ = [
    # Config
    "WorkbenchConfig",
    "get_workbench_config",
    "set_workbench_config",
    # Database
    "WorkbenchDB",
    "get_workbench_db",
    "init_workbench",
    # Models
    "ConnectionStatus",
    "ConnectionType",
    "Extraction",
    "ExtractionType",
    "Severity",
    "SuggestedConnection",
]
