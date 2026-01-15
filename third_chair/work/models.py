"""Data models for work items.

Work items represent actionable tasks for attorneys working on a case:
investigations, legal questions, objectives, actions, and established facts.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class WorkItemType(Enum):
    """Types of work items."""

    INVESTIGATION = "investigation"  # Facts to discover
    LEGAL_QUESTION = "legal_question"  # Legal research needed
    OBJECTIVE = "objective"  # Case goals
    ACTION = "action"  # General tasks
    FACT = "fact"  # Established facts (links to Skanda)


class WorkItemStatus(Enum):
    """Status of a work item."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class Priority(Enum):
    """Priority levels for work items."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Prefix mapping for IDs
TYPE_PREFIX = {
    WorkItemType.INVESTIGATION: "INV",
    WorkItemType.LEGAL_QUESTION: "LEG",
    WorkItemType.OBJECTIVE: "OBJ",
    WorkItemType.ACTION: "ACT",
    WorkItemType.FACT: "FACT",
}


@dataclass
class WorkItemNote:
    """A note or update on a work item."""

    date: datetime
    text: str
    author: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "date": self.date.isoformat() if isinstance(self.date, datetime) else self.date,
            "text": self.text,
        }
        if self.author:
            result["author"] = self.author
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkItemNote":
        """Create from dictionary."""
        date = data["date"]
        if isinstance(date, str):
            date = datetime.fromisoformat(date)
        return cls(
            date=date,
            text=data["text"],
            author=data.get("author"),
        )


@dataclass
class WorkItem:
    """A single work item for case management.

    Attributes:
        id: Unique identifier (e.g., "INV-0001")
        item_type: Type of work item
        title: Short descriptive title
        description: Detailed description of the work
        status: Current status
        priority: Priority level
        created: When the item was created
        updated: When the item was last updated
        due_date: Optional deadline
        assigned_to: Person responsible
        tags: List of tags for categorization
        blocked_by: IDs of items blocking this one
        supports_propositions: IDs of propositions this supports
        notes: History of notes/updates
        metadata: Additional flexible data
    """

    id: str
    item_type: WorkItemType
    title: str
    description: str = ""
    status: WorkItemStatus = WorkItemStatus.PENDING
    priority: Priority = Priority.MEDIUM
    created: datetime = field(default_factory=datetime.now)
    updated: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    supports_propositions: list[str] = field(default_factory=list)
    notes: list[WorkItemNote] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "id": self.id,
            "type": self.item_type.value,
            "title": self.title,
            "status": self.status.value,
            "priority": self.priority.value,
            "created": self.created.isoformat() if isinstance(self.created, datetime) else self.created,
            "updated": self.updated.isoformat() if isinstance(self.updated, datetime) else self.updated,
        }

        if self.description:
            result["description"] = self.description
        if self.due_date:
            result["due_date"] = self.due_date.isoformat() if isinstance(self.due_date, datetime) else self.due_date
        if self.assigned_to:
            result["assigned_to"] = self.assigned_to
        if self.tags:
            result["tags"] = self.tags
        if self.blocked_by:
            result["blocked_by"] = self.blocked_by
        if self.supports_propositions:
            result["supports_propositions"] = self.supports_propositions
        if self.notes:
            result["notes"] = [note.to_dict() for note in self.notes]
        if self.metadata:
            result["metadata"] = self.metadata

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkItem":
        """Create from dictionary."""
        # Parse dates
        created = data.get("created", datetime.now())
        if isinstance(created, str):
            created = datetime.fromisoformat(created)

        updated = data.get("updated", datetime.now())
        if isinstance(updated, str):
            updated = datetime.fromisoformat(updated)

        due_date = data.get("due_date")
        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date)

        # Parse notes
        notes = [
            WorkItemNote.from_dict(n) for n in data.get("notes", [])
        ]

        return cls(
            id=data["id"],
            item_type=WorkItemType(data["type"]),
            title=data["title"],
            description=data.get("description", ""),
            status=WorkItemStatus(data.get("status", "pending")),
            priority=Priority(data.get("priority", "medium")),
            created=created,
            updated=updated,
            due_date=due_date,
            assigned_to=data.get("assigned_to"),
            tags=data.get("tags", []),
            blocked_by=data.get("blocked_by", []),
            supports_propositions=data.get("supports_propositions", []),
            notes=notes,
            metadata=data.get("metadata", {}),
        )

    def add_note(self, text: str, author: Optional[str] = None) -> None:
        """Add a note to this work item."""
        self.notes.append(WorkItemNote(
            date=datetime.now(),
            text=text,
            author=author,
        ))
        self.updated = datetime.now()

    def mark_completed(self, note: Optional[str] = None) -> None:
        """Mark this work item as completed."""
        self.status = WorkItemStatus.COMPLETED
        self.updated = datetime.now()
        if note:
            self.add_note(f"Completed: {note}")

    def mark_blocked(self, blocked_by: list[str], reason: Optional[str] = None) -> None:
        """Mark this work item as blocked."""
        self.status = WorkItemStatus.BLOCKED
        self.blocked_by = blocked_by
        self.updated = datetime.now()
        if reason:
            self.add_note(f"Blocked: {reason}")

    @property
    def is_overdue(self) -> bool:
        """Check if this item is past its due date."""
        if not self.due_date:
            return False
        return datetime.now() > self.due_date and self.status != WorkItemStatus.COMPLETED


@dataclass
class WorkIndexStats:
    """Statistics about work items."""

    total: int = 0
    pending: int = 0
    in_progress: int = 0
    completed: int = 0
    blocked: int = 0
    overdue: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "total": self.total,
            "pending": self.pending,
            "in_progress": self.in_progress,
            "completed": self.completed,
            "blocked": self.blocked,
            "overdue": self.overdue,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkIndexStats":
        """Create from dictionary."""
        return cls(
            total=data.get("total", 0),
            pending=data.get("pending", 0),
            in_progress=data.get("in_progress", 0),
            completed=data.get("completed", 0),
            blocked=data.get("blocked", 0),
            overdue=data.get("overdue", 0),
        )


@dataclass
class WorkIndex:
    """Index tracking work items for a case.

    Stored in _index.yaml in the work/ directory.
    """

    case_id: str
    last_touch: datetime = field(default_factory=datetime.now)
    last_action: str = ""
    attorney: Optional[str] = None
    resolution_path: Optional[str] = None  # trial, plea, dismissal
    stats: WorkIndexStats = field(default_factory=WorkIndexStats)
    item_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "case_id": self.case_id,
            "last_touch": self.last_touch.isoformat() if isinstance(self.last_touch, datetime) else self.last_touch,
            "last_action": self.last_action,
            "stats": self.stats.to_dict(),
            "item_ids": self.item_ids,
        }

        if self.attorney:
            result["attorney"] = self.attorney
        if self.resolution_path:
            result["resolution_path"] = self.resolution_path
        if self.metadata:
            result["metadata"] = self.metadata

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkIndex":
        """Create from dictionary."""
        last_touch = data.get("last_touch", datetime.now())
        if isinstance(last_touch, str):
            last_touch = datetime.fromisoformat(last_touch)

        stats = WorkIndexStats.from_dict(data.get("stats", {}))

        return cls(
            case_id=data["case_id"],
            last_touch=last_touch,
            last_action=data.get("last_action", ""),
            attorney=data.get("attorney"),
            resolution_path=data.get("resolution_path"),
            stats=stats,
            item_ids=data.get("item_ids", []),
            metadata=data.get("metadata", {}),
        )

    def touch(self, action: str) -> None:
        """Update last touch time and action."""
        self.last_touch = datetime.now()
        self.last_action = action

    def update_stats(self, items: list[WorkItem]) -> None:
        """Recalculate stats from work items."""
        self.stats = WorkIndexStats(
            total=len(items),
            pending=sum(1 for i in items if i.status == WorkItemStatus.PENDING),
            in_progress=sum(1 for i in items if i.status == WorkItemStatus.IN_PROGRESS),
            completed=sum(1 for i in items if i.status == WorkItemStatus.COMPLETED),
            blocked=sum(1 for i in items if i.status == WorkItemStatus.BLOCKED),
            overdue=sum(1 for i in items if i.is_overdue),
        )
        self.item_ids = [i.id for i in items]


def generate_item_id(item_type: WorkItemType, existing_ids: list[str]) -> str:
    """Generate a new unique ID for a work item.

    Args:
        item_type: Type of work item
        existing_ids: List of existing IDs to avoid collisions

    Returns:
        New unique ID (e.g., "INV-0001")
    """
    prefix = TYPE_PREFIX[item_type]

    # Find highest existing number for this type
    max_num = 0
    for existing_id in existing_ids:
        if existing_id.startswith(f"{prefix}-"):
            try:
                num = int(existing_id.split("-")[1])
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                pass

    return f"{prefix}-{max_num + 1:04d}"
