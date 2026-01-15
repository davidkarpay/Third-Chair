"""Tests for work item models."""

from datetime import datetime, timedelta

import pytest

from third_chair.work.models import (
    WorkItem,
    WorkItemType,
    WorkItemStatus,
    WorkItemNote,
    WorkIndex,
    WorkIndexStats,
    Priority,
    TYPE_PREFIX,
    generate_item_id,
)


class TestWorkItemNote:
    """Tests for WorkItemNote serialization."""

    def test_to_dict_round_trip(self):
        """WorkItemNote -> dict -> WorkItemNote preserves all fields."""
        note = WorkItemNote(
            date=datetime(2025, 1, 15, 10, 30, 0),
            text="Interview scheduled for Monday",
            author="John Smith",
        )

        data = note.to_dict()
        restored = WorkItemNote.from_dict(data)

        assert restored.text == note.text
        assert restored.author == note.author
        assert restored.date == note.date

    def test_from_dict_with_date_string(self):
        """Create from dict with date as ISO string."""
        data = {
            "date": "2025-01-15T10:30:00",
            "text": "Note text",
        }

        note = WorkItemNote.from_dict(data)

        assert note.date == datetime(2025, 1, 15, 10, 30, 0)
        assert note.text == "Note text"
        assert note.author is None

    def test_from_dict_with_datetime_object(self):
        """Dates already as datetime pass through."""
        date_obj = datetime(2025, 1, 15, 10, 30, 0)
        data = {
            "date": date_obj,
            "text": "Note text",
        }

        note = WorkItemNote.from_dict(data)

        assert note.date == date_obj


class TestWorkItem:
    """Tests for WorkItem model."""

    def test_to_dict_round_trip(self):
        """WorkItem -> dict -> WorkItem preserves all fields."""
        item = WorkItem(
            id="INV-0001",
            item_type=WorkItemType.INVESTIGATION,
            title="Interview witness",
            description="Interview Maria Garcia",
            status=WorkItemStatus.PENDING,
            priority=Priority.HIGH,
            tags=["witness", "interview"],
            assigned_to="Investigator Bob",
        )

        data = item.to_dict()
        restored = WorkItem.from_dict(data)

        assert restored.id == item.id
        assert restored.item_type == item.item_type
        assert restored.title == item.title
        assert restored.description == item.description
        assert restored.status == item.status
        assert restored.priority == item.priority
        assert restored.tags == item.tags
        assert restored.assigned_to == item.assigned_to

    def test_from_dict_with_dates_as_strings(self):
        """Dates as ISO strings deserialize to datetime."""
        data = {
            "id": "INV-0001",
            "type": "investigation",
            "title": "Test item",
            "created": "2025-01-15T10:00:00",
            "updated": "2025-01-15T11:00:00",
            "due_date": "2025-01-20T17:00:00",
        }

        item = WorkItem.from_dict(data)

        assert isinstance(item.created, datetime)
        assert isinstance(item.updated, datetime)
        assert isinstance(item.due_date, datetime)
        assert item.created == datetime(2025, 1, 15, 10, 0, 0)

    def test_from_dict_with_minimal_fields(self):
        """Create from dict with only required fields."""
        data = {
            "id": "ACT-0001",
            "type": "action",
            "title": "File motion",
        }

        item = WorkItem.from_dict(data)

        assert item.id == "ACT-0001"
        assert item.item_type == WorkItemType.ACTION
        assert item.title == "File motion"
        assert item.status == WorkItemStatus.PENDING
        assert item.priority == Priority.MEDIUM
        assert item.description == ""
        assert item.tags == []

    def test_add_note(self):
        """add_note() appends note and updates 'updated' timestamp."""
        item = WorkItem(
            id="INV-0001",
            item_type=WorkItemType.INVESTIGATION,
            title="Test item",
        )
        original_updated = item.updated

        item.add_note("Interview completed successfully", author="John")

        assert len(item.notes) == 1
        assert item.notes[0].text == "Interview completed successfully"
        assert item.notes[0].author == "John"
        assert item.updated >= original_updated

    def test_mark_completed(self):
        """mark_completed() sets status and adds completion note."""
        item = WorkItem(
            id="INV-0001",
            item_type=WorkItemType.INVESTIGATION,
            title="Test item",
        )

        item.mark_completed("Interview revealed favorable testimony")

        assert item.status == WorkItemStatus.COMPLETED
        assert len(item.notes) == 1
        assert "Completed" in item.notes[0].text

    def test_mark_completed_without_note(self):
        """mark_completed() without note still sets status."""
        item = WorkItem(
            id="INV-0001",
            item_type=WorkItemType.INVESTIGATION,
            title="Test item",
        )

        item.mark_completed()

        assert item.status == WorkItemStatus.COMPLETED
        assert len(item.notes) == 0

    def test_is_overdue_with_past_due_date(self):
        """is_overdue returns True when due_date passed."""
        item = WorkItem(
            id="INV-0001",
            item_type=WorkItemType.INVESTIGATION,
            title="Test item",
            due_date=datetime.now() - timedelta(days=1),
            status=WorkItemStatus.PENDING,
        )

        assert item.is_overdue is True

    def test_is_overdue_with_future_due_date(self):
        """is_overdue returns False when due_date is in future."""
        item = WorkItem(
            id="INV-0001",
            item_type=WorkItemType.INVESTIGATION,
            title="Test item",
            due_date=datetime.now() + timedelta(days=1),
            status=WorkItemStatus.PENDING,
        )

        assert item.is_overdue is False

    def test_is_overdue_completed_not_overdue(self):
        """Completed items are never overdue."""
        item = WorkItem(
            id="INV-0001",
            item_type=WorkItemType.INVESTIGATION,
            title="Test item",
            due_date=datetime.now() - timedelta(days=1),
            status=WorkItemStatus.COMPLETED,
        )

        assert item.is_overdue is False

    def test_is_overdue_no_due_date(self):
        """Items without due date are never overdue."""
        item = WorkItem(
            id="INV-0001",
            item_type=WorkItemType.INVESTIGATION,
            title="Test item",
            due_date=None,
        )

        assert item.is_overdue is False

    def test_mark_blocked(self):
        """mark_blocked() sets status, blocked_by, and adds note."""
        item = WorkItem(
            id="INV-0002",
            item_type=WorkItemType.INVESTIGATION,
            title="Second interview",
        )

        item.mark_blocked(["INV-0001"], "Waiting for first interview")

        assert item.status == WorkItemStatus.BLOCKED
        assert item.blocked_by == ["INV-0001"]
        assert len(item.notes) == 1
        assert "Blocked" in item.notes[0].text

    def test_to_dict_with_notes(self):
        """Serialization includes notes."""
        item = WorkItem(
            id="INV-0001",
            item_type=WorkItemType.INVESTIGATION,
            title="Test item",
        )
        item.add_note("First note")
        item.add_note("Second note")

        data = item.to_dict()

        assert "notes" in data
        assert len(data["notes"]) == 2


class TestWorkIndexStats:
    """Tests for WorkIndexStats."""

    def test_to_dict_round_trip(self):
        """WorkIndexStats survives round-trip."""
        stats = WorkIndexStats(
            total=10,
            pending=5,
            in_progress=2,
            completed=2,
            blocked=1,
            overdue=0,
        )

        data = stats.to_dict()
        restored = WorkIndexStats.from_dict(data)

        assert restored.total == stats.total
        assert restored.pending == stats.pending
        assert restored.in_progress == stats.in_progress
        assert restored.completed == stats.completed
        assert restored.blocked == stats.blocked
        assert restored.overdue == stats.overdue

    def test_from_dict_with_empty_data(self):
        """Create from empty dict uses defaults."""
        stats = WorkIndexStats.from_dict({})

        assert stats.total == 0
        assert stats.pending == 0


class TestWorkIndex:
    """Tests for WorkIndex."""

    def test_to_dict_round_trip(self):
        """WorkIndex survives round-trip."""
        index = WorkIndex(
            case_id="TEST-001",
            attorney="Jane Smith",
            resolution_path="trial",
            item_ids=["INV-0001", "LEG-0001"],
        )

        data = index.to_dict()
        restored = WorkIndex.from_dict(data)

        assert restored.case_id == index.case_id
        assert restored.attorney == index.attorney
        assert restored.resolution_path == index.resolution_path
        assert restored.item_ids == index.item_ids

    def test_touch_updates_timestamp(self):
        """touch() updates last_touch and last_action."""
        index = WorkIndex(case_id="TEST-001")
        original_touch = index.last_touch

        index.touch("Created INV-0001")

        assert index.last_touch >= original_touch
        assert index.last_action == "Created INV-0001"

    def test_update_stats(self):
        """update_stats() correctly counts by status."""
        index = WorkIndex(case_id="TEST-001")

        items = [
            WorkItem(id="INV-0001", item_type=WorkItemType.INVESTIGATION, title="A", status=WorkItemStatus.PENDING),
            WorkItem(id="INV-0002", item_type=WorkItemType.INVESTIGATION, title="B", status=WorkItemStatus.PENDING),
            WorkItem(id="LEG-0001", item_type=WorkItemType.LEGAL_QUESTION, title="C", status=WorkItemStatus.IN_PROGRESS),
            WorkItem(id="ACT-0001", item_type=WorkItemType.ACTION, title="D", status=WorkItemStatus.COMPLETED),
            WorkItem(id="ACT-0002", item_type=WorkItemType.ACTION, title="E", status=WorkItemStatus.BLOCKED),
        ]

        index.update_stats(items)

        assert index.stats.total == 5
        assert index.stats.pending == 2
        assert index.stats.in_progress == 1
        assert index.stats.completed == 1
        assert index.stats.blocked == 1
        assert index.item_ids == ["INV-0001", "INV-0002", "LEG-0001", "ACT-0001", "ACT-0002"]

    def test_from_dict_with_last_touch_string(self):
        """last_touch as ISO string deserializes correctly."""
        data = {
            "case_id": "TEST-001",
            "last_touch": "2025-01-15T14:30:00",
            "last_action": "Created item",
        }

        index = WorkIndex.from_dict(data)

        assert index.last_touch == datetime(2025, 1, 15, 14, 30, 0)


class TestGenerateItemId:
    """Tests for generate_item_id function."""

    def test_increments_from_existing(self):
        """New ID is one higher than existing max."""
        existing = ["INV-0001", "INV-0002", "INV-0003"]

        new_id = generate_item_id(WorkItemType.INVESTIGATION, existing)

        assert new_id == "INV-0004"

    def test_handles_empty_list(self):
        """Returns -0001 suffix when no existing IDs."""
        new_id = generate_item_id(WorkItemType.INVESTIGATION, [])

        assert new_id == "INV-0001"

    def test_respects_type_prefix(self):
        """Different types get different prefixes."""
        existing = ["INV-0001", "LEG-0001"]

        inv_id = generate_item_id(WorkItemType.INVESTIGATION, existing)
        leg_id = generate_item_id(WorkItemType.LEGAL_QUESTION, existing)
        act_id = generate_item_id(WorkItemType.ACTION, existing)

        assert inv_id == "INV-0002"
        assert leg_id == "LEG-0002"
        assert act_id == "ACT-0001"

    def test_ignores_other_type_ids(self):
        """Only counts IDs matching the requested type."""
        existing = ["INV-0001", "INV-0002", "LEG-0001", "ACT-0003"]

        new_id = generate_item_id(WorkItemType.INVESTIGATION, existing)

        assert new_id == "INV-0003"

    def test_handles_malformed_ids(self):
        """Skips malformed IDs gracefully."""
        existing = ["INV-0001", "INV-bad", "INV-", "LEG-0001"]

        new_id = generate_item_id(WorkItemType.INVESTIGATION, existing)

        assert new_id == "INV-0002"

    def test_all_type_prefixes(self):
        """All work item types have correct prefixes."""
        assert TYPE_PREFIX[WorkItemType.INVESTIGATION] == "INV"
        assert TYPE_PREFIX[WorkItemType.LEGAL_QUESTION] == "LEG"
        assert TYPE_PREFIX[WorkItemType.OBJECTIVE] == "OBJ"
        assert TYPE_PREFIX[WorkItemType.ACTION] == "ACT"
        assert TYPE_PREFIX[WorkItemType.FACT] == "FACT"
