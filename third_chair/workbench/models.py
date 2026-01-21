"""Data models for the Evidence Workbench."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ExtractionType(str, Enum):
    """Types of extractions from transcripts."""

    STATEMENT = "statement"
    EVENT = "event"
    ENTITY_MENTION = "entity_mention"
    ACTION = "action"
    DIALOGUE = "dialogue"


class ConnectionType(str, Enum):
    """Types of connections between extractions."""

    INCONSISTENT_STATEMENT = "inconsistent_statement"
    TEMPORAL_CONFLICT = "temporal_conflict"
    CORROBORATES = "corroborates"
    CONTRADICTS = "contradicts"


class Severity(str, Enum):
    """Severity levels for detected issues."""

    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class ConnectionStatus(str, Enum):
    """Status of a suggested connection."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


@dataclass
class Extraction:
    """A granular fact extracted from evidence.

    Represents a single statement, event, entity mention, or action
    extracted from a transcript segment.
    """

    id: str
    evidence_id: str
    extraction_type: ExtractionType
    content: str
    segment_index: Optional[int] = None
    speaker: Optional[str] = None
    speaker_role: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        evidence_id: str,
        extraction_type: ExtractionType,
        content: str,
        **kwargs: Any,
    ) -> "Extraction":
        """Create a new extraction with a generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            evidence_id=evidence_id,
            extraction_type=extraction_type,
            content=content,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "evidence_id": self.evidence_id,
            "extraction_type": self.extraction_type.value,
            "content": self.content,
            "segment_index": self.segment_index,
            "speaker": self.speaker,
            "speaker_role": self.speaker_role,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Extraction":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            evidence_id=data["evidence_id"],
            extraction_type=ExtractionType(data["extraction_type"]),
            content=data["content"],
            segment_index=data.get("segment_index"),
            speaker=data.get("speaker"),
            speaker_role=data.get("speaker_role"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            confidence=data.get("confidence", 1.0),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else datetime.now(),
        )


@dataclass
class SuggestedConnection:
    """A detected relationship between two extractions.

    Represents potential inconsistencies, corroborations, or temporal
    conflicts between facts from different evidence items.
    """

    id: str
    extraction_a_id: str
    extraction_b_id: str
    connection_type: ConnectionType
    confidence: float
    reasoning: str
    evidence_snippets: list[str] = field(default_factory=list)
    severity: Optional[Severity] = None
    status: ConnectionStatus = ConnectionStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        extraction_a_id: str,
        extraction_b_id: str,
        connection_type: ConnectionType,
        confidence: float,
        reasoning: str,
        **kwargs: Any,
    ) -> "SuggestedConnection":
        """Create a new connection with a generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            extraction_a_id=extraction_a_id,
            extraction_b_id=extraction_b_id,
            connection_type=connection_type,
            confidence=confidence,
            reasoning=reasoning,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "extraction_a_id": self.extraction_a_id,
            "extraction_b_id": self.extraction_b_id,
            "connection_type": self.connection_type.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "evidence_snippets": self.evidence_snippets,
            "severity": self.severity.value if self.severity else None,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SuggestedConnection":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            extraction_a_id=data["extraction_a_id"],
            extraction_b_id=data["extraction_b_id"],
            connection_type=ConnectionType(data["connection_type"]),
            confidence=data["confidence"],
            reasoning=data["reasoning"],
            evidence_snippets=data.get("evidence_snippets", []),
            severity=Severity(data["severity"]) if data.get("severity") else None,
            status=ConnectionStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else datetime.now(),
        )
