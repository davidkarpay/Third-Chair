"""Tests for Case model serialization."""

from datetime import datetime, date
from pathlib import Path

import pytest

from third_chair.models import Case, EvidenceItem, FileType, ContentType
from third_chair.models.case import TimelineEvent


class TestTimelineEvent:
    """Tests for TimelineEvent serialization."""

    def test_to_dict_round_trip(self):
        """TimelineEvent -> dict -> TimelineEvent preserves all fields."""
        event = TimelineEvent(
            timestamp=datetime(2025, 1, 15, 14, 30, 0),
            description="Officer arrived on scene",
            evidence_id="EVD-001",
            source="transcript",
            metadata={"officer": "Smith"},
        )

        data = event.to_dict()
        restored = TimelineEvent.from_dict(data)

        assert restored.timestamp == event.timestamp
        assert restored.description == event.description
        assert restored.evidence_id == event.evidence_id
        assert restored.source == event.source
        assert restored.metadata == event.metadata

    def test_from_dict_with_minimal_fields(self):
        """Create from dict with only required fields."""
        data = {
            "timestamp": "2025-01-15T14:30:00",
            "description": "Event description",
        }

        event = TimelineEvent.from_dict(data)

        assert event.timestamp == datetime(2025, 1, 15, 14, 30, 0)
        assert event.description == "Event description"
        assert event.evidence_id is None
        assert event.source == "transcript"
        assert event.metadata == {}


class TestCase:
    """Tests for Case model."""

    def test_to_dict_round_trip(self, sample_case: Case):
        """Case -> dict -> Case preserves all fields."""
        data = sample_case.to_dict()
        restored = Case.from_dict(data)

        assert restored.case_id == sample_case.case_id
        assert restored.court_case == sample_case.court_case
        assert restored.output_dir == sample_case.output_dir

    def test_save_and_load(self, sample_case: Case, tmp_path: Path):
        """Save case to JSON and load it back, verify equality."""
        case_file = tmp_path / "case.json"

        sample_case.save(case_file)
        loaded = Case.load(case_file)

        assert loaded.case_id == sample_case.case_id
        assert loaded.court_case == sample_case.court_case

    def test_save_creates_parent_dirs(self, sample_case: Case, tmp_path: Path):
        """save() creates parent directories if needed."""
        case_file = tmp_path / "deep" / "nested" / "case.json"

        sample_case.save(case_file)

        assert case_file.exists()

    def test_save_without_path_uses_output_dir(self, sample_case: Case):
        """save() without path argument uses output_dir."""
        saved_path = sample_case.save()

        assert saved_path == sample_case.output_dir / "case.json"
        assert saved_path.exists()

    def test_save_without_output_dir_raises(self, tmp_path: Path):
        """save() without output_dir raises ValueError."""
        case = Case(case_id="TEST-001")

        with pytest.raises(ValueError, match="No output directory"):
            case.save()

    def test_load_missing_file_raises(self, tmp_path: Path):
        """Loading non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            Case.load(tmp_path / "nonexistent.json")

    def test_from_dict_with_missing_optional_fields(self):
        """Create case from dict missing optional fields uses defaults."""
        data = {
            "case_id": "TEST-001",
        }

        case = Case.from_dict(data)

        assert case.case_id == "TEST-001"
        assert case.court_case is None
        assert case.agency is None
        assert case.evidence_items == []
        assert case.timeline == []
        assert case.metadata == {}

    def test_from_dict_with_incident_date(self):
        """Incident date deserializes correctly."""
        data = {
            "case_id": "TEST-001",
            "incident_date": "2025-01-15",
        }

        case = Case.from_dict(data)

        assert case.incident_date == date(2025, 1, 15)

    def test_evidence_count_properties(self, sample_case_with_evidence: Case):
        """Verify evidence_count, media_count, etc. return correct values."""
        case = sample_case_with_evidence

        assert case.evidence_count == 2
        assert case.media_count == 1  # Only the video

    def test_add_evidence(self, sample_case: Case, tmp_path: Path):
        """Adding evidence updates evidence_items list."""
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"content")

        item = EvidenceItem(
            id="EVD-001",
            filename="test.mp4",
            file_path=test_file,
            file_type=FileType.VIDEO,
        )

        sample_case.add_evidence(item)

        assert len(sample_case.evidence_items) == 1
        assert sample_case.evidence_items[0].id == "EVD-001"

    def test_get_evidence_by_id(self, sample_case_with_evidence: Case):
        """Retrieve evidence by ID returns correct item or None."""
        case = sample_case_with_evidence

        found = case.get_evidence("EVD-001")
        not_found = case.get_evidence("NONEXISTENT")

        assert found is not None
        assert found.id == "EVD-001"
        assert not_found is None

    def test_get_media_items(self, sample_case_with_evidence: Case):
        """get_media_items() returns only audio/video items."""
        media = sample_case_with_evidence.get_media_items()

        assert len(media) == 1
        assert media[0].file_type == FileType.VIDEO

    def test_timeline_stays_sorted(self, sample_case: Case):
        """Timeline events remain sorted by timestamp after additions."""
        # Add events out of order
        sample_case.add_timeline_event(TimelineEvent(
            timestamp=datetime(2025, 1, 15, 15, 0, 0),
            description="Later event",
        ))
        sample_case.add_timeline_event(TimelineEvent(
            timestamp=datetime(2025, 1, 15, 14, 0, 0),
            description="Earlier event",
        ))
        sample_case.add_timeline_event(TimelineEvent(
            timestamp=datetime(2025, 1, 15, 14, 30, 0),
            description="Middle event",
        ))

        # Verify sorted
        assert sample_case.timeline[0].description == "Earlier event"
        assert sample_case.timeline[1].description == "Middle event"
        assert sample_case.timeline[2].description == "Later event"

    def test_total_duration(self, sample_case_with_evidence: Case):
        """total_duration_seconds sums media durations."""
        duration = sample_case_with_evidence.total_duration_seconds

        assert duration == 120.5  # From the video fixture

    def test_total_duration_formatted(self, sample_case_with_evidence: Case):
        """total_duration_formatted returns HH:MM:SS format."""
        formatted = sample_case_with_evidence.total_duration_formatted

        assert formatted == "0:02:00"  # 120.5 seconds

    def test_processing_complete_all_done(self, sample_case_with_evidence: Case):
        """processing_complete is True when all items processed."""
        for item in sample_case_with_evidence.evidence_items:
            item.set_completed()

        assert sample_case_with_evidence.processing_complete is True

    def test_processing_complete_with_pending(self, sample_case_with_evidence: Case):
        """processing_complete is False when items pending."""
        assert sample_case_with_evidence.processing_complete is False


class TestCaseWithEvidenceRoundTrip:
    """Tests for Case save/load with evidence items."""

    def test_case_with_evidence_round_trip(self, sample_case_with_evidence: Case, tmp_path: Path):
        """Case with evidence survives save/load round-trip."""
        case_file = tmp_path / "case.json"

        sample_case_with_evidence.save(case_file)
        loaded = Case.load(case_file)

        assert loaded.evidence_count == sample_case_with_evidence.evidence_count
        assert loaded.evidence_items[0].id == sample_case_with_evidence.evidence_items[0].id
        assert loaded.evidence_items[0].file_type == sample_case_with_evidence.evidence_items[0].file_type

    def test_case_preserves_evidence_metadata(self, sample_case_with_evidence: Case, tmp_path: Path):
        """Evidence metadata preserved through save/load."""
        sample_case_with_evidence.evidence_items[0].metadata["custom_field"] = "custom_value"

        case_file = tmp_path / "case.json"
        sample_case_with_evidence.save(case_file)
        loaded = Case.load(case_file)

        assert loaded.evidence_items[0].metadata["custom_field"] == "custom_value"


class TestCaseWithTimeline:
    """Tests for Case save/load with timeline events."""

    def test_case_with_timeline_round_trip(self, sample_case: Case, tmp_path: Path):
        """Case with timeline events survives round-trip."""
        sample_case.add_timeline_event(TimelineEvent(
            timestamp=datetime(2025, 1, 15, 14, 0, 0),
            description="First event",
            evidence_id="EVD-001",
        ))
        sample_case.add_timeline_event(TimelineEvent(
            timestamp=datetime(2025, 1, 15, 15, 0, 0),
            description="Second event",
        ))

        case_file = tmp_path / "case.json"
        sample_case.save(case_file)
        loaded = Case.load(case_file)

        assert len(loaded.timeline) == 2
        assert loaded.timeline[0].description == "First event"
        assert loaded.timeline[0].evidence_id == "EVD-001"
