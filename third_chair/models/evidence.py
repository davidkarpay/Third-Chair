"""Evidence item data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .transcript import Transcript


class FileType(str, Enum):
    """Primary file type classification."""

    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    IMAGE = "image"
    SPREADSHEET = "spreadsheet"
    OTHER = "other"


class ContentType(str, Enum):
    """Content/purpose classification for evidence."""

    BWC_FOOTAGE = "bwc_footage"  # Body-worn camera
    INTERVIEW = "interview"
    VICTIM_STATEMENT = "victim_statement"
    WITNESS_STATEMENT = "witness_statement"
    SUSPECT_STATEMENT = "suspect_statement"
    CAD_LOG = "cad_log"  # Computer-aided dispatch
    POLICE_REPORT = "police_report"
    INCIDENT_REPORT = "incident_report"
    EVIDENCE_LOG = "evidence_log"
    PHOTO = "photo"
    SURVEILLANCE = "surveillance"
    AUDIO_RECORDING = "audio_recording"
    TRANSCRIPT = "transcript"
    OTHER = "other"


class ProcessingStatus(str, Enum):
    """Processing status for evidence items."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    SKIPPED = "skipped"


# File extension mappings
FILE_TYPE_MAP: dict[str, FileType] = {
    # Video
    ".mp4": FileType.VIDEO,
    ".avi": FileType.VIDEO,
    ".mov": FileType.VIDEO,
    ".mkv": FileType.VIDEO,
    ".wmv": FileType.VIDEO,
    ".webm": FileType.VIDEO,
    # Audio
    ".mp3": FileType.AUDIO,
    ".wav": FileType.AUDIO,
    ".m4a": FileType.AUDIO,
    ".flac": FileType.AUDIO,
    ".ogg": FileType.AUDIO,
    ".wma": FileType.AUDIO,
    # Documents
    ".pdf": FileType.DOCUMENT,
    ".doc": FileType.DOCUMENT,
    ".docx": FileType.DOCUMENT,
    ".txt": FileType.DOCUMENT,
    ".rtf": FileType.DOCUMENT,
    # Images
    ".jpg": FileType.IMAGE,
    ".jpeg": FileType.IMAGE,
    ".png": FileType.IMAGE,
    ".gif": FileType.IMAGE,
    ".bmp": FileType.IMAGE,
    ".tiff": FileType.IMAGE,
    # Spreadsheets
    ".xlsx": FileType.SPREADSHEET,
    ".xls": FileType.SPREADSHEET,
    ".csv": FileType.SPREADSHEET,
}


@dataclass
class EvidenceItem:
    """Represents a single piece of evidence."""

    id: str
    filename: str
    file_path: Path
    file_type: FileType = FileType.OTHER
    content_type: ContentType = ContentType.OTHER
    size_bytes: int = 0
    duration_seconds: Optional[float] = None
    transcript: Optional[Transcript] = None
    summary: Optional[str] = None
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def is_media(self) -> bool:
        """Check if this is audio or video."""
        return self.file_type in (FileType.VIDEO, FileType.AUDIO)

    @property
    def is_transcribable(self) -> bool:
        """Check if this item can be transcribed."""
        return self.is_media

    @property
    def is_processed(self) -> bool:
        """Check if processing is complete."""
        return self.processing_status == ProcessingStatus.COMPLETED

    @property
    def has_error(self) -> bool:
        """Check if there was a processing error."""
        return self.processing_status == ProcessingStatus.ERROR

    @property
    def size_mb(self) -> float:
        """Get file size in megabytes."""
        return self.size_bytes / (1024 * 1024)

    @property
    def duration_formatted(self) -> str:
        """Get duration as MM:SS or HH:MM:SS string."""
        if self.duration_seconds is None:
            return "N/A"

        total_seconds = int(self.duration_seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def set_error(self, message: str) -> None:
        """Mark item as errored with a message."""
        self.processing_status = ProcessingStatus.ERROR
        self.error_message = message

    def set_completed(self) -> None:
        """Mark item as completed."""
        self.processing_status = ProcessingStatus.COMPLETED
        self.error_message = None

    def get_decrypted_path(self, case_dir: Optional[Path] = None) -> Path:
        """
        Get path to the evidence file, handling encryption transparently.

        For encrypted vaults, returns an EncryptedPath that decrypts on access.
        For unencrypted cases, returns the original file_path.

        The returned path is compatible with subprocess calls (e.g., FFmpeg)
        via __fspath__() method.

        Args:
            case_dir: Case directory (uses file_path.parent.parent if not provided)

        Returns:
            Path or EncryptedPath for accessing the file
        """
        if case_dir is None:
            # Assume standard structure: case_dir/extracted/file.ext
            case_dir = self.file_path.parent.parent

        try:
            from ..vault import get_evidence_path

            return get_evidence_path(self.file_path, case_dir)
        except ImportError:
            # Vault module not available
            return self.file_path
        except Exception:
            # Vault not encrypted or not unlocked - return original
            return self.file_path

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "filename": self.filename,
            "file_path": str(self.file_path),
            "file_type": self.file_type.value,
            "content_type": self.content_type.value,
            "size_bytes": self.size_bytes,
            "duration_seconds": self.duration_seconds,
            "transcript": self.transcript.to_dict() if self.transcript else None,
            "summary": self.summary,
            "processing_status": self.processing_status.value,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidenceItem":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            filename=data["filename"],
            file_path=Path(data["file_path"]),
            file_type=FileType(data.get("file_type", "other")),
            content_type=ContentType(data.get("content_type", "other")),
            size_bytes=data.get("size_bytes", 0),
            duration_seconds=data.get("duration_seconds"),
            transcript=Transcript.from_dict(data["transcript"]) if data.get("transcript") else None,
            summary=data.get("summary"),
            processing_status=ProcessingStatus(data.get("processing_status", "pending")),
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
        )

    @classmethod
    def from_file(cls, file_path: Path, evidence_id: Optional[str] = None) -> "EvidenceItem":
        """Create an evidence item from a file path."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Determine file type from extension
        ext = file_path.suffix.lower()
        file_type = FILE_TYPE_MAP.get(ext, FileType.OTHER)

        # Generate ID if not provided
        if evidence_id is None:
            evidence_id = file_path.stem[:20]

        return cls(
            id=evidence_id,
            filename=file_path.name,
            file_path=file_path,
            file_type=file_type,
            size_bytes=file_path.stat().st_size,
        )
