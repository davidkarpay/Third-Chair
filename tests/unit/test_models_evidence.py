"""Tests for EvidenceItem model serialization."""

from datetime import datetime
from pathlib import Path

import pytest

from third_chair.models import EvidenceItem, FileType, ContentType, ProcessingStatus


class TestEvidenceItem:
    """Tests for EvidenceItem model."""

    def test_to_dict_round_trip(self, sample_evidence_item: EvidenceItem):
        """EvidenceItem survives serialization round-trip."""
        data = sample_evidence_item.to_dict()
        restored = EvidenceItem.from_dict(data)

        assert restored.id == sample_evidence_item.id
        assert restored.filename == sample_evidence_item.filename
        assert restored.file_type == sample_evidence_item.file_type
        assert restored.content_type == sample_evidence_item.content_type
        assert restored.size_bytes == sample_evidence_item.size_bytes
        assert restored.duration_seconds == sample_evidence_item.duration_seconds

    def test_from_dict_with_enum_values(self):
        """FileType and ContentType enums deserialize correctly."""
        data = {
            "id": "EVD-001",
            "filename": "bodycam.mp4",
            "file_path": "/path/to/file.mp4",
            "file_type": "video",
            "content_type": "bwc_footage",
            "processing_status": "completed",
            "created_at": "2025-01-15T10:00:00",
        }

        item = EvidenceItem.from_dict(data)

        assert item.file_type == FileType.VIDEO
        assert item.content_type == ContentType.BWC_FOOTAGE
        assert item.processing_status == ProcessingStatus.COMPLETED

    def test_from_dict_with_defaults(self):
        """from_dict uses defaults for missing optional fields."""
        data = {
            "id": "EVD-001",
            "filename": "file.mp4",
            "file_path": "/path/to/file.mp4",
        }

        item = EvidenceItem.from_dict(data)

        assert item.file_type == FileType.OTHER
        assert item.content_type == ContentType.OTHER
        assert item.processing_status == ProcessingStatus.PENDING
        assert item.size_bytes == 0
        assert item.duration_seconds is None
        assert item.metadata == {}

    def test_from_file_creates_valid_item(self, tmp_path: Path):
        """from_file() creates item with correct file_type and size."""
        # Create test files
        video_file = tmp_path / "test_video.mp4"
        video_file.write_bytes(b"video content here")

        audio_file = tmp_path / "test_audio.mp3"
        audio_file.write_bytes(b"audio content")

        pdf_file = tmp_path / "document.pdf"
        pdf_file.write_bytes(b"pdf content")

        video_item = EvidenceItem.from_file(video_file)
        audio_item = EvidenceItem.from_file(audio_file)
        pdf_item = EvidenceItem.from_file(pdf_file)

        assert video_item.file_type == FileType.VIDEO
        assert video_item.size_bytes == len(b"video content here")

        assert audio_item.file_type == FileType.AUDIO

        assert pdf_item.file_type == FileType.DOCUMENT

    def test_from_file_missing_file_raises(self, tmp_path: Path):
        """from_file() with non-existent path raises FileNotFoundError."""
        nonexistent = tmp_path / "nonexistent.mp4"

        with pytest.raises(FileNotFoundError, match="File not found"):
            EvidenceItem.from_file(nonexistent)

    def test_from_file_with_custom_id(self, tmp_path: Path):
        """from_file() uses provided evidence_id."""
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"content")

        item = EvidenceItem.from_file(test_file, evidence_id="CUSTOM-001")

        assert item.id == "CUSTOM-001"

    def test_from_file_generates_id_from_filename(self, tmp_path: Path):
        """from_file() generates ID from filename if not provided."""
        test_file = tmp_path / "bodycam_officer_smith.mp4"
        test_file.write_bytes(b"content")

        item = EvidenceItem.from_file(test_file)

        assert item.id == "bodycam_officer_smit"  # Truncated to 20 chars

    def test_from_file_unknown_extension(self, tmp_path: Path):
        """from_file() handles unknown extension as OTHER."""
        test_file = tmp_path / "unknown.xyz"
        test_file.write_bytes(b"content")

        item = EvidenceItem.from_file(test_file)

        assert item.file_type == FileType.OTHER

    def test_is_media_property(self):
        """is_media returns True for VIDEO/AUDIO, False otherwise."""
        video_item = EvidenceItem(
            id="EVD-001",
            filename="video.mp4",
            file_path=Path("/path"),
            file_type=FileType.VIDEO,
        )
        audio_item = EvidenceItem(
            id="EVD-002",
            filename="audio.mp3",
            file_path=Path("/path"),
            file_type=FileType.AUDIO,
        )
        doc_item = EvidenceItem(
            id="EVD-003",
            filename="doc.pdf",
            file_path=Path("/path"),
            file_type=FileType.DOCUMENT,
        )

        assert video_item.is_media is True
        assert audio_item.is_media is True
        assert doc_item.is_media is False

    def test_is_transcribable_property(self):
        """is_transcribable returns True for media items."""
        video_item = EvidenceItem(
            id="EVD-001",
            filename="video.mp4",
            file_path=Path("/path"),
            file_type=FileType.VIDEO,
        )
        doc_item = EvidenceItem(
            id="EVD-002",
            filename="doc.pdf",
            file_path=Path("/path"),
            file_type=FileType.DOCUMENT,
        )

        assert video_item.is_transcribable is True
        assert doc_item.is_transcribable is False

    def test_duration_formatted(self):
        """duration_formatted returns correct HH:MM:SS format."""
        short_item = EvidenceItem(
            id="EVD-001",
            filename="short.mp4",
            file_path=Path("/path"),
            duration_seconds=65.0,
        )
        long_item = EvidenceItem(
            id="EVD-002",
            filename="long.mp4",
            file_path=Path("/path"),
            duration_seconds=3725.0,  # 1 hour, 2 minutes, 5 seconds
        )
        no_duration = EvidenceItem(
            id="EVD-003",
            filename="unknown.mp4",
            file_path=Path("/path"),
            duration_seconds=None,
        )

        assert short_item.duration_formatted == "1:05"
        assert long_item.duration_formatted == "1:02:05"
        assert no_duration.duration_formatted == "N/A"

    def test_size_mb_property(self):
        """size_mb returns correct megabytes."""
        item = EvidenceItem(
            id="EVD-001",
            filename="large.mp4",
            file_path=Path("/path"),
            size_bytes=10 * 1024 * 1024,  # 10 MB
        )

        assert item.size_mb == 10.0

    def test_set_error(self):
        """set_error() marks item as errored with message."""
        item = EvidenceItem(
            id="EVD-001",
            filename="file.mp4",
            file_path=Path("/path"),
        )

        item.set_error("Transcription failed: corrupted audio")

        assert item.processing_status == ProcessingStatus.ERROR
        assert item.error_message == "Transcription failed: corrupted audio"
        assert item.has_error is True

    def test_set_completed(self):
        """set_completed() marks item as completed and clears error."""
        item = EvidenceItem(
            id="EVD-001",
            filename="file.mp4",
            file_path=Path("/path"),
        )
        item.set_error("Previous error")

        item.set_completed()

        assert item.processing_status == ProcessingStatus.COMPLETED
        assert item.error_message is None
        assert item.is_processed is True

    def test_is_processed_property(self):
        """is_processed returns True only for COMPLETED status."""
        item = EvidenceItem(
            id="EVD-001",
            filename="file.mp4",
            file_path=Path("/path"),
        )

        assert item.is_processed is False

        item.processing_status = ProcessingStatus.PROCESSING
        assert item.is_processed is False

        item.processing_status = ProcessingStatus.COMPLETED
        assert item.is_processed is True


class TestFileTypeMapping:
    """Tests for file type extension mapping."""

    def test_video_extensions(self, tmp_path: Path):
        """Video extensions are mapped correctly."""
        extensions = [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".webm"]

        for ext in extensions:
            test_file = tmp_path / f"video{ext}"
            test_file.write_bytes(b"content")
            item = EvidenceItem.from_file(test_file)
            assert item.file_type == FileType.VIDEO, f"Failed for {ext}"

    def test_audio_extensions(self, tmp_path: Path):
        """Audio extensions are mapped correctly."""
        extensions = [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"]

        for ext in extensions:
            test_file = tmp_path / f"audio{ext}"
            test_file.write_bytes(b"content")
            item = EvidenceItem.from_file(test_file)
            assert item.file_type == FileType.AUDIO, f"Failed for {ext}"

    def test_document_extensions(self, tmp_path: Path):
        """Document extensions are mapped correctly."""
        extensions = [".pdf", ".doc", ".docx", ".txt", ".rtf"]

        for ext in extensions:
            test_file = tmp_path / f"doc{ext}"
            test_file.write_bytes(b"content")
            item = EvidenceItem.from_file(test_file)
            assert item.file_type == FileType.DOCUMENT, f"Failed for {ext}"

    def test_image_extensions(self, tmp_path: Path):
        """Image extensions are mapped correctly."""
        extensions = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]

        for ext in extensions:
            test_file = tmp_path / f"image{ext}"
            test_file.write_bytes(b"content")
            item = EvidenceItem.from_file(test_file)
            assert item.file_type == FileType.IMAGE, f"Failed for {ext}"

    def test_spreadsheet_extensions(self, tmp_path: Path):
        """Spreadsheet extensions are mapped correctly."""
        extensions = [".xlsx", ".xls", ".csv"]

        for ext in extensions:
            test_file = tmp_path / f"sheet{ext}"
            test_file.write_bytes(b"content")
            item = EvidenceItem.from_file(test_file)
            assert item.file_type == FileType.SPREADSHEET, f"Failed for {ext}"
