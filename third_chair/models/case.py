"""Case data models."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from .evidence import EvidenceItem, ProcessingStatus
from .witness import WitnessList


@dataclass
class TimelineEvent:
    """An event in the case timeline."""

    timestamp: datetime
    description: str
    evidence_id: Optional[str] = None
    source: str = "transcript"  # transcript, document, manual
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "description": self.description,
            "evidence_id": self.evidence_id,
            "source": self.source,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimelineEvent":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            description=data["description"],
            evidence_id=data.get("evidence_id"),
            source=data.get("source", "transcript"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Case:
    """Represents a legal case with all associated evidence and data."""

    case_id: str
    court_case: Optional[str] = None
    agency: Optional[str] = None
    incident_date: Optional[date] = None
    created_at: datetime = field(default_factory=datetime.now)
    source_zip: Optional[str] = None
    source_hash: Optional[str] = None
    output_dir: Optional[Path] = None
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    witnesses: WitnessList = field(default_factory=WitnessList)
    timeline: list[TimelineEvent] = field(default_factory=list)
    summary: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def evidence_count(self) -> int:
        """Get total number of evidence items."""
        return len(self.evidence_items)

    @property
    def media_count(self) -> int:
        """Get number of audio/video items."""
        return sum(1 for e in self.evidence_items if e.is_media)

    @property
    def processed_count(self) -> int:
        """Get number of processed items."""
        return sum(1 for e in self.evidence_items if e.is_processed)

    @property
    def pending_count(self) -> int:
        """Get number of pending items."""
        return sum(
            1 for e in self.evidence_items
            if e.processing_status == ProcessingStatus.PENDING
        )

    @property
    def error_count(self) -> int:
        """Get number of items with errors."""
        return sum(1 for e in self.evidence_items if e.has_error)

    @property
    def processing_complete(self) -> bool:
        """Check if all items have been processed."""
        return all(
            e.processing_status in (ProcessingStatus.COMPLETED, ProcessingStatus.SKIPPED, ProcessingStatus.ERROR)
            for e in self.evidence_items
        )

    @property
    def total_duration_seconds(self) -> float:
        """Get total duration of all media items."""
        return sum(
            e.duration_seconds or 0
            for e in self.evidence_items
            if e.is_media
        )

    @property
    def total_duration_formatted(self) -> str:
        """Get total duration as HH:MM:SS string."""
        total_seconds = int(self.total_duration_seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours}:{minutes:02d}:{seconds:02d}"

    def add_evidence(self, item: EvidenceItem) -> None:
        """Add an evidence item to the case."""
        self.evidence_items.append(item)

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceItem]:
        """Get an evidence item by ID."""
        for item in self.evidence_items:
            if item.id == evidence_id:
                return item
        return None

    def get_media_items(self) -> list[EvidenceItem]:
        """Get all audio/video items."""
        return [e for e in self.evidence_items if e.is_media]

    def get_pending_items(self) -> list[EvidenceItem]:
        """Get all items pending processing."""
        return [
            e for e in self.evidence_items
            if e.processing_status == ProcessingStatus.PENDING
        ]

    def add_timeline_event(self, event: TimelineEvent) -> None:
        """Add an event to the timeline."""
        self.timeline.append(event)
        # Keep timeline sorted by timestamp
        self.timeline.sort(key=lambda e: e.timestamp)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "case_id": self.case_id,
            "court_case": self.court_case,
            "agency": self.agency,
            "incident_date": self.incident_date.isoformat() if self.incident_date else None,
            "created_at": self.created_at.isoformat(),
            "source_zip": self.source_zip,
            "source_hash": self.source_hash,
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "evidence_items": [e.to_dict() for e in self.evidence_items],
            "witnesses": self.witnesses.to_dict(),
            "timeline": [e.to_dict() for e in self.timeline],
            "summary": self.summary,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Case":
        """Create from dictionary."""
        return cls(
            case_id=data["case_id"],
            court_case=data.get("court_case"),
            agency=data.get("agency"),
            incident_date=date.fromisoformat(data["incident_date"]) if data.get("incident_date") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            source_zip=data.get("source_zip"),
            source_hash=data.get("source_hash"),
            output_dir=Path(data["output_dir"]) if data.get("output_dir") else None,
            evidence_items=[EvidenceItem.from_dict(e) for e in data.get("evidence_items", [])],
            witnesses=WitnessList.from_dict(data.get("witnesses", {})),
            timeline=[TimelineEvent.from_dict(e) for e in data.get("timeline", [])],
            summary=data.get("summary"),
            metadata=data.get("metadata", {}),
        )

    def save(self, path: Optional[Path] = None) -> Path:
        """Save case to JSON file."""
        if path is None:
            if self.output_dir is None:
                raise ValueError("No output directory specified")
            path = self.output_dir / "case.json"

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

        return path

    @classmethod
    def load(cls, path: Path) -> "Case":
        """Load case from JSON file."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
