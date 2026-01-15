"""Work item management for attorney case tracking.

This module provides a file-based system for attorneys to track:
- Investigations (witness interviews, document requests)
- Legal questions (case law research, statutory interpretation)
- Objectives (case goals, trial strategy)
- Actions (motions, exhibits)
- Facts (established via Skanda framework)

Work items are stored as YAML files in case_dir/work/ for easy
human editing and git tracking.
"""

from .models import (
    WorkItem,
    WorkIndex,
    WorkIndexStats,
    WorkItemNote,
    WorkItemType,
    WorkItemStatus,
    Priority,
    TYPE_PREFIX,
    generate_item_id,
)
from .storage import (
    WorkStorage,
    init_work_storage,
)
from .ai_assistant import (
    create_work_item_from_text,
    suggest_work_items,
    create_suggested_items,
    DEFAULT_MODEL,
)

__all__ = [
    # Models
    "WorkItem",
    "WorkIndex",
    "WorkIndexStats",
    "WorkItemNote",
    "WorkItemType",
    "WorkItemStatus",
    "Priority",
    "TYPE_PREFIX",
    "generate_item_id",
    # Storage
    "WorkStorage",
    "init_work_storage",
    # AI Assistant
    "create_work_item_from_text",
    "suggest_work_items",
    "create_suggested_items",
    "DEFAULT_MODEL",
]
