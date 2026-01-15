"""Tests for work item storage."""

from pathlib import Path

import pytest
import yaml

from third_chair.work.models import WorkItemType, WorkItemStatus, Priority
from third_chair.work.storage import WorkStorage, init_work_storage, INDEX_FILE


class TestWorkStorage:
    """Tests for WorkStorage class."""

    def test_ensure_work_dir_creates_directory(self, sample_case_dir: Path):
        """ensure_work_dir() creates the work directory."""
        storage = WorkStorage(sample_case_dir)

        storage.ensure_work_dir()

        assert (sample_case_dir / "work").exists()
        assert (sample_case_dir / "work").is_dir()

    def test_create_item(self, work_storage: WorkStorage):
        """create_item() saves item and updates index."""
        item = work_storage.create_item(
            item_type=WorkItemType.INVESTIGATION,
            title="Interview witness",
            description="Interview Maria Garcia about the incident",
            priority="high",
        )

        assert item.id == "INV-0001"
        assert item.title == "Interview witness"
        assert item.priority == Priority.HIGH

        # Verify file was created
        item_path = work_storage.item_path(item.id)
        assert item_path.exists()

        # Verify index was updated
        index = work_storage.load_index()
        assert item.id in index.item_ids
        assert index.stats.total == 1
        assert index.stats.pending == 1

    def test_create_item_increments_id(self, work_storage: WorkStorage):
        """Subsequent items get incrementing IDs."""
        item1 = work_storage.create_item(
            item_type=WorkItemType.INVESTIGATION,
            title="First item",
        )
        item2 = work_storage.create_item(
            item_type=WorkItemType.INVESTIGATION,
            title="Second item",
        )
        item3 = work_storage.create_item(
            item_type=WorkItemType.LEGAL_QUESTION,
            title="Legal question",
        )

        assert item1.id == "INV-0001"
        assert item2.id == "INV-0002"
        assert item3.id == "LEG-0001"

    def test_load_item(self, work_storage: WorkStorage):
        """load_item() retrieves saved item."""
        created = work_storage.create_item(
            item_type=WorkItemType.ACTION,
            title="Test action",
            description="Test description",
            priority="critical",
            tags=["test", "important"],
        )

        # Clear cache to force reload from disk
        work_storage._items.clear()

        loaded = work_storage.load_item(created.id)

        assert loaded is not None
        assert loaded.id == created.id
        assert loaded.title == created.title
        assert loaded.description == created.description
        assert loaded.priority == Priority.CRITICAL
        assert loaded.tags == ["test", "important"]

    def test_load_item_not_found(self, work_storage: WorkStorage):
        """load_item() returns None for missing ID."""
        loaded = work_storage.load_item("NONEXISTENT-0001")

        assert loaded is None

    def test_load_item_caches(self, work_storage: WorkStorage):
        """load_item() caches loaded items."""
        created = work_storage.create_item(
            item_type=WorkItemType.ACTION,
            title="Test action",
        )

        loaded1 = work_storage.load_item(created.id)
        loaded2 = work_storage.load_item(created.id)

        assert loaded1 is loaded2  # Same object from cache

    def test_update_item(self, work_storage: WorkStorage):
        """update_item() modifies and persists changes."""
        item = work_storage.create_item(
            item_type=WorkItemType.INVESTIGATION,
            title="Test item",
        )

        updated = work_storage.update_item(
            item.id,
            status="in_progress",
            priority="critical",
            note="Started working on this",
        )

        assert updated is not None
        assert updated.status == WorkItemStatus.IN_PROGRESS
        assert updated.priority == Priority.CRITICAL
        assert len(updated.notes) == 1
        assert "Started working on this" in updated.notes[0].text

        # Verify persisted
        work_storage._items.clear()
        reloaded = work_storage.load_item(item.id)
        assert reloaded.status == WorkItemStatus.IN_PROGRESS

    def test_update_item_not_found(self, work_storage: WorkStorage):
        """update_item() returns None for missing ID."""
        result = work_storage.update_item("NONEXISTENT-0001", status="completed")

        assert result is None

    def test_list_items_filter_by_status(self, work_storage_with_items: WorkStorage):
        """list_items() respects status filter."""
        # Update one item to in_progress
        items = work_storage_with_items.list_items()
        work_storage_with_items.update_item(items[0].id, status="in_progress")

        pending = work_storage_with_items.list_items(status=WorkItemStatus.PENDING)
        in_progress = work_storage_with_items.list_items(status=WorkItemStatus.IN_PROGRESS)

        assert len(pending) == 2
        assert len(in_progress) == 1

    def test_list_items_filter_by_type(self, work_storage_with_items: WorkStorage):
        """list_items() respects type filter."""
        investigations = work_storage_with_items.list_items(item_type=WorkItemType.INVESTIGATION)
        legal_questions = work_storage_with_items.list_items(item_type=WorkItemType.LEGAL_QUESTION)
        actions = work_storage_with_items.list_items(item_type=WorkItemType.ACTION)

        assert len(investigations) == 1
        assert len(legal_questions) == 1
        assert len(actions) == 1

    def test_list_items_sorted_by_priority(self, work_storage_with_items: WorkStorage):
        """list_items() sorts by priority (critical first)."""
        items = work_storage_with_items.list_items()

        # Items are sorted by priority: critical > high > medium > low
        priorities = [item.priority.value for item in items]
        assert priorities[0] == "critical"
        assert priorities[1] == "high"
        assert priorities[2] == "medium"

    def test_delete_item(self, work_storage: WorkStorage):
        """delete_item() removes file and returns True."""
        item = work_storage.create_item(
            item_type=WorkItemType.ACTION,
            title="To be deleted",
        )
        item_path = work_storage.item_path(item.id)
        assert item_path.exists()

        result = work_storage.delete_item(item.id)

        assert result is True
        assert not item_path.exists()

    def test_delete_item_not_found(self, work_storage: WorkStorage):
        """delete_item() returns False for missing ID."""
        result = work_storage.delete_item("NONEXISTENT-0001")

        assert result is False

    def test_get_summary(self, work_storage_with_items: WorkStorage):
        """get_summary() returns correct stats."""
        summary = work_storage_with_items.get_summary()

        assert summary["case_id"] == "TEST-001"
        assert summary["stats"]["total"] == 3
        assert summary["stats"]["pending"] == 3
        assert len(summary["recent_pending"]) <= 5

    def test_load_all_items_skips_incomplete(self, work_storage: WorkStorage):
        """load_all_items() skips YAML files missing required fields."""
        work_storage.ensure_work_dir()

        # Create a valid item
        work_storage.create_item(
            item_type=WorkItemType.ACTION,
            title="Valid item",
        )

        # Create a YAML file missing required fields (valid YAML but missing id/type)
        incomplete_path = work_storage.work_dir / "INCOMPLETE-0001.yaml"
        incomplete_path.write_text("title: Missing id and type\n")

        items = work_storage.load_all_items()

        # Should only get the valid item (incomplete one is skipped)
        assert len(items) == 1
        assert items[0].title == "Valid item"

    def test_load_all_items_skips_malformed_yaml(self, work_storage: WorkStorage):
        """load_all_items() skips files with invalid YAML syntax."""
        work_storage.ensure_work_dir()

        # Create a valid item
        work_storage.create_item(
            item_type=WorkItemType.ACTION,
            title="Valid item",
        )

        # Create a malformed YAML file (invalid syntax)
        malformed_path = work_storage.work_dir / "BAD-0001.yaml"
        malformed_path.write_text("this is not valid: yaml: content: [")

        items = work_storage.load_all_items()

        # Should not crash, should only get the valid item
        assert len(items) == 1
        assert items[0].title == "Valid item"


class TestInitWorkStorage:
    """Tests for init_work_storage function."""

    def test_creates_work_directory(self, sample_case_dir: Path):
        """init_work_storage creates work/ directory."""
        storage = init_work_storage(sample_case_dir, case_id="TEST-001")

        assert (sample_case_dir / "work").exists()
        assert storage.work_dir == sample_case_dir / "work"

    def test_creates_index_file(self, sample_case_dir: Path):
        """init_work_storage creates _index.yaml."""
        storage = init_work_storage(sample_case_dir, case_id="TEST-001")

        index_path = sample_case_dir / "work" / INDEX_FILE
        assert index_path.exists()

        with open(index_path) as f:
            data = yaml.safe_load(f)

        assert data["case_id"] == "TEST-001"

    def test_preserves_existing_index(self, sample_case_dir: Path):
        """init_work_storage preserves existing index data."""
        # First init
        storage1 = init_work_storage(sample_case_dir, case_id="TEST-001")
        storage1.create_item(WorkItemType.ACTION, "Test item")

        # Second init should preserve items
        storage2 = init_work_storage(sample_case_dir, case_id="TEST-001")
        items = storage2.list_items()

        assert len(items) == 1
        assert items[0].title == "Test item"


class TestYAMLPersistence:
    """Tests for YAML file persistence."""

    def test_item_yaml_is_human_readable(self, work_storage: WorkStorage):
        """Work item YAML files are human-readable."""
        item = work_storage.create_item(
            item_type=WorkItemType.INVESTIGATION,
            title="Interview witness",
            description="Multi-line\ndescription\nhere",
            tags=["witness", "interview"],
        )

        yaml_content = work_storage.item_path(item.id).read_text()

        # YAML should contain readable content
        assert "title: Interview witness" in yaml_content
        assert "type: investigation" in yaml_content
        assert "witness" in yaml_content

    def test_index_yaml_is_human_readable(self, work_storage: WorkStorage):
        """Index YAML file is human-readable."""
        work_storage.create_item(WorkItemType.ACTION, "Test item")

        yaml_content = work_storage.index_path.read_text()

        assert "case_id:" in yaml_content
        assert "stats:" in yaml_content
        assert "item_ids:" in yaml_content

    def test_unicode_preserved(self, work_storage: WorkStorage):
        """Unicode characters are preserved in YAML."""
        item = work_storage.create_item(
            item_type=WorkItemType.INVESTIGATION,
            title="Entrevista con María García",
            description="Testigo presencial del incidente",
        )

        # Reload from disk
        work_storage._items.clear()
        loaded = work_storage.load_item(item.id)

        assert loaded.title == "Entrevista con María García"
        assert loaded.description == "Testigo presencial del incidente"
