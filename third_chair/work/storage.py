"""Storage layer for work items using YAML files.

Work items are stored as individual YAML files in a case's work/ directory,
with an _index.yaml file tracking the overall state.
"""

from pathlib import Path
from typing import Optional

import yaml

from .models import (
    WorkItem,
    WorkIndex,
    WorkItemType,
    WorkItemStatus,
    generate_item_id,
)


# YAML file names
INDEX_FILE = "_index.yaml"


class WorkStorage:
    """Manages work item storage for a case.

    Work items are stored in:
        case_dir/work/_index.yaml  - Index with stats and last touch
        case_dir/work/INV-0001.yaml - Individual work items
    """

    def __init__(self, case_dir: Path):
        """Initialize storage for a case directory.

        Args:
            case_dir: Path to the case directory
        """
        self.case_dir = Path(case_dir)
        self.work_dir = self.case_dir / "work"
        self._index: Optional[WorkIndex] = None
        self._items: dict[str, WorkItem] = {}

    def ensure_work_dir(self) -> None:
        """Create work directory if it doesn't exist."""
        self.work_dir.mkdir(parents=True, exist_ok=True)

    @property
    def index_path(self) -> Path:
        """Path to the index file."""
        return self.work_dir / INDEX_FILE

    def item_path(self, item_id: str) -> Path:
        """Get path to a work item file."""
        return self.work_dir / f"{item_id}.yaml"

    def load_index(self, case_id: str = "") -> WorkIndex:
        """Load or create the work index.

        Args:
            case_id: Case ID for new index creation

        Returns:
            WorkIndex object
        """
        if self._index is not None:
            return self._index

        if self.index_path.exists():
            with open(self.index_path) as f:
                data = yaml.safe_load(f) or {}
            self._index = WorkIndex.from_dict(data)
        else:
            # Create new index
            self._index = WorkIndex(case_id=case_id or self.case_dir.name)

        return self._index

    def save_index(self) -> None:
        """Save the work index to disk."""
        if self._index is None:
            return

        self.ensure_work_dir()

        with open(self.index_path, "w") as f:
            yaml.dump(
                self._index.to_dict(),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    def load_item(self, item_id: str) -> Optional[WorkItem]:
        """Load a single work item.

        Args:
            item_id: ID of the item to load

        Returns:
            WorkItem or None if not found
        """
        if item_id in self._items:
            return self._items[item_id]

        item_path = self.item_path(item_id)
        if not item_path.exists():
            return None

        with open(item_path) as f:
            data = yaml.safe_load(f) or {}

        item = WorkItem.from_dict(data)
        self._items[item_id] = item
        return item

    def save_item(self, item: WorkItem) -> None:
        """Save a work item to disk.

        Args:
            item: WorkItem to save
        """
        self.ensure_work_dir()

        item_path = self.item_path(item.id)
        with open(item_path, "w") as f:
            yaml.dump(
                item.to_dict(),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

        self._items[item.id] = item

    def delete_item(self, item_id: str) -> bool:
        """Delete a work item.

        Args:
            item_id: ID of the item to delete

        Returns:
            True if deleted, False if not found
        """
        item_path = self.item_path(item_id)
        if not item_path.exists():
            return False

        item_path.unlink()
        self._items.pop(item_id, None)
        return True

    def load_all_items(self) -> list[WorkItem]:
        """Load all work items from the work directory.

        Returns:
            List of all WorkItem objects
        """
        items = []

        if not self.work_dir.exists():
            return items

        for yaml_file in self.work_dir.glob("*.yaml"):
            if yaml_file.name == INDEX_FILE:
                continue

            with open(yaml_file) as f:
                data = yaml.safe_load(f) or {}

            if "id" in data and "type" in data:
                try:
                    item = WorkItem.from_dict(data)
                    items.append(item)
                    self._items[item.id] = item
                except (ValueError, KeyError):
                    # Skip malformed files
                    pass

        return items

    def list_items(
        self,
        status: Optional[WorkItemStatus] = None,
        item_type: Optional[WorkItemType] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[str] = None,
    ) -> list[WorkItem]:
        """List work items with optional filtering.

        Args:
            status: Filter by status
            item_type: Filter by type
            priority: Filter by priority
            assigned_to: Filter by assignee

        Returns:
            List of matching WorkItem objects
        """
        items = self.load_all_items()

        if status:
            items = [i for i in items if i.status == status]
        if item_type:
            items = [i for i in items if i.item_type == item_type]
        if priority:
            from .models import Priority
            items = [i for i in items if i.priority == Priority(priority)]
        if assigned_to:
            items = [i for i in items if i.assigned_to == assigned_to]

        # Sort by priority (critical first), then by created date
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        items.sort(key=lambda i: (priority_order.get(i.priority.value, 2), i.created))

        return items

    def create_item(
        self,
        item_type: WorkItemType,
        title: str,
        description: str = "",
        priority: str = "medium",
        assigned_to: Optional[str] = None,
        tags: Optional[list[str]] = None,
        due_date: Optional[str] = None,
    ) -> WorkItem:
        """Create a new work item.

        Args:
            item_type: Type of work item
            title: Title of the item
            description: Detailed description
            priority: Priority level
            assigned_to: Person responsible
            tags: List of tags
            due_date: Due date (ISO format string)

        Returns:
            The created WorkItem
        """
        from datetime import datetime
        from .models import Priority

        # Load existing items to get IDs
        existing_items = self.load_all_items()
        existing_ids = [i.id for i in existing_items]

        # Generate ID
        item_id = generate_item_id(item_type, existing_ids)

        # Parse due date
        parsed_due = None
        if due_date:
            parsed_due = datetime.fromisoformat(due_date)

        # Create item
        item = WorkItem(
            id=item_id,
            item_type=item_type,
            title=title,
            description=description,
            priority=Priority(priority),
            assigned_to=assigned_to,
            tags=tags or [],
            due_date=parsed_due,
        )

        # Save item
        self.save_item(item)

        # Update index
        index = self.load_index()
        index.touch(f"Created {item_id}: {title}")
        all_items = self.load_all_items()
        index.update_stats(all_items)
        self.save_index()

        return item

    def update_item(
        self,
        item_id: str,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[str] = None,
        note: Optional[str] = None,
        due_date: Optional[str] = None,
    ) -> Optional[WorkItem]:
        """Update an existing work item.

        Args:
            item_id: ID of the item to update
            status: New status
            priority: New priority
            assigned_to: New assignee
            note: Note to add
            due_date: New due date

        Returns:
            Updated WorkItem or None if not found
        """
        from datetime import datetime
        from .models import Priority

        item = self.load_item(item_id)
        if not item:
            return None

        if status:
            item.status = WorkItemStatus(status)
        if priority:
            item.priority = Priority(priority)
        if assigned_to is not None:
            item.assigned_to = assigned_to if assigned_to else None
        if due_date:
            item.due_date = datetime.fromisoformat(due_date)
        if note:
            item.add_note(note)

        item.updated = datetime.now()
        self.save_item(item)

        # Update index
        index = self.load_index()
        index.touch(f"Updated {item_id}")
        all_items = self.load_all_items()
        index.update_stats(all_items)
        self.save_index()

        return item

    def get_summary(self) -> dict:
        """Get a summary of work items for display.

        Returns:
            Dictionary with summary information
        """
        index = self.load_index()
        items = self.load_all_items()
        index.update_stats(items)

        # Get recent items
        pending_items = [i for i in items if i.status == WorkItemStatus.PENDING]
        pending_items.sort(key=lambda i: i.created, reverse=True)

        overdue_items = [i for i in items if i.is_overdue]

        return {
            "case_id": index.case_id,
            "last_touch": index.last_touch,
            "last_action": index.last_action,
            "attorney": index.attorney,
            "resolution_path": index.resolution_path,
            "stats": index.stats.to_dict(),
            "recent_pending": pending_items[:5],
            "overdue": overdue_items,
        }


def init_work_storage(case_dir: Path, case_id: str = "") -> WorkStorage:
    """Initialize work storage for a case.

    Creates the work/ directory and _index.yaml if they don't exist.

    Args:
        case_dir: Path to case directory
        case_id: Case ID for the index

    Returns:
        Initialized WorkStorage
    """
    storage = WorkStorage(case_dir)
    storage.ensure_work_dir()

    # Initialize index if needed
    index = storage.load_index(case_id)
    storage.save_index()

    return storage
