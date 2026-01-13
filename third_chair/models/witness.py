"""Witness data models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class WitnessRole(str, Enum):
    """Witness role classification."""

    VICTIM = "victim"
    WITNESS = "witness"
    SUSPECT = "suspect"
    OFFICER = "officer"
    INTERPRETER = "interpreter"
    OTHER = "other"


class WitnessSource(str, Enum):
    """Source of witness information."""

    DIARIZATION = "diarization"
    STATE_ATTORNEY_LIST = "state_attorney_list"
    DOCUMENT_EXTRACTION = "document_extraction"
    MANUAL = "manual"


@dataclass
class Witness:
    """Represents a witness or party in the case."""

    id: str = field(default_factory=lambda: str(uuid4())[:8])
    name: Optional[str] = None
    role: WitnessRole = WitnessRole.OTHER
    source: WitnessSource = WitnessSource.DIARIZATION
    speaker_ids: list[str] = field(default_factory=list)  # SPEAKER_1, SPEAKER_2, etc.
    evidence_appearances: list[str] = field(default_factory=list)  # Evidence IDs
    verified: bool = False
    notes: Optional[str] = None
    contact_info: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        """Get display name, falling back to speaker ID or 'Unknown'."""
        if self.name:
            return self.name
        if self.speaker_ids:
            return self.speaker_ids[0]
        return f"Unknown ({self.id})"

    @property
    def is_named(self) -> bool:
        """Check if witness has been named."""
        return self.name is not None

    def add_speaker_id(self, speaker_id: str) -> None:
        """Associate a speaker ID with this witness."""
        if speaker_id not in self.speaker_ids:
            self.speaker_ids.append(speaker_id)

    def add_evidence_appearance(self, evidence_id: str) -> None:
        """Record that this witness appears in an evidence item."""
        if evidence_id not in self.evidence_appearances:
            self.evidence_appearances.append(evidence_id)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "source": self.source.value,
            "speaker_ids": self.speaker_ids,
            "evidence_appearances": self.evidence_appearances,
            "verified": self.verified,
            "notes": self.notes,
            "contact_info": self.contact_info,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Witness":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid4())[:8]),
            name=data.get("name"),
            role=WitnessRole(data.get("role", "other")),
            source=WitnessSource(data.get("source", "manual")),
            speaker_ids=data.get("speaker_ids", []),
            evidence_appearances=data.get("evidence_appearances", []),
            verified=data.get("verified", False),
            notes=data.get("notes"),
            contact_info=data.get("contact_info"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WitnessList:
    """Collection of witnesses for a case."""

    witnesses: list[Witness] = field(default_factory=list)

    def add(self, witness: Witness) -> None:
        """Add a witness to the list."""
        self.witnesses.append(witness)

    def __len__(self) -> int:
        """Return number of witnesses."""
        return len(self.witnesses)

    def __iter__(self):
        """Iterate over witnesses."""
        return iter(self.witnesses)

    def get_by_id(self, witness_id: str) -> Optional[Witness]:
        """Get witness by ID."""
        for w in self.witnesses:
            if w.id == witness_id:
                return w
        return None

    def get_by_speaker_id(self, speaker_id: str) -> Optional[Witness]:
        """Get witness by speaker ID."""
        for w in self.witnesses:
            if speaker_id in w.speaker_ids:
                return w
        return None

    def get_by_role(self, role: WitnessRole) -> list[Witness]:
        """Get all witnesses with a specific role."""
        return [w for w in self.witnesses if w.role == role]

    def get_unverified(self) -> list[Witness]:
        """Get all unverified witnesses."""
        return [w for w in self.witnesses if not w.verified]

    def get_unnamed(self) -> list[Witness]:
        """Get all witnesses without names."""
        return [w for w in self.witnesses if not w.is_named]

    def merge(self, witness1_id: str, witness2_id: str) -> Optional[Witness]:
        """Merge two witnesses (when determined to be the same person)."""
        w1 = self.get_by_id(witness1_id)
        w2 = self.get_by_id(witness2_id)

        if not w1 or not w2:
            return None

        # Merge into w1
        for speaker_id in w2.speaker_ids:
            w1.add_speaker_id(speaker_id)

        for evidence_id in w2.evidence_appearances:
            w1.add_evidence_appearance(evidence_id)

        # Use w2's name if w1 doesn't have one
        if not w1.name and w2.name:
            w1.name = w2.name

        # Combine notes
        if w2.notes:
            if w1.notes:
                w1.notes = f"{w1.notes}\n{w2.notes}"
            else:
                w1.notes = w2.notes

        # Remove w2
        self.witnesses = [w for w in self.witnesses if w.id != witness2_id]

        return w1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "witnesses": [w.to_dict() for w in self.witnesses]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WitnessList":
        """Create from dictionary."""
        return cls(
            witnesses=[Witness.from_dict(w) for w in data.get("witnesses", [])]
        )
