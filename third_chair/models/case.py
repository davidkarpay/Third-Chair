"""Case data models."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from .evidence import EvidenceItem, ProcessingStatus
from .proposition import MaterialIssue, Proposition
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
    propositions: list[Proposition] = field(default_factory=list)
    material_issues: list[MaterialIssue] = field(default_factory=list)
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

    def add_proposition(self, proposition: Proposition) -> None:
        """Add a proposition to the case."""
        self.propositions.append(proposition)

    def get_proposition(self, proposition_id: str) -> Optional[Proposition]:
        """Get a proposition by ID."""
        for prop in self.propositions:
            if prop.id == proposition_id:
                return prop
        return None

    def get_propositions_by_issue(self, issue_id: str) -> list[Proposition]:
        """Get all propositions for a material issue."""
        return [
            p for p in self.propositions
            if p.material_issue.issue_id == issue_id
        ]

    def get_propositions_by_proponent(self, party: str) -> list[Proposition]:
        """Get all propositions by proponent party."""
        return [
            p for p in self.propositions
            if p.proponent.party.lower() == party.lower()
        ]

    def add_material_issue(self, issue: MaterialIssue) -> None:
        """Add a material issue to the case."""
        self.material_issues.append(issue)

    def get_material_issue(self, issue_id: str) -> Optional[MaterialIssue]:
        """Get a material issue by ID."""
        for issue in self.material_issues:
            if issue.id == issue_id:
                return issue
        return None

    @property
    def proposition_count(self) -> int:
        """Get total number of propositions."""
        return len(self.propositions)

    @property
    def propositions_needing_evaluation(self) -> list[Proposition]:
        """Get propositions that need (re)evaluation."""
        return [p for p in self.propositions if p.needs_evaluation]

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
            "propositions": [p.to_dict() for p in self.propositions],
            "material_issues": [i.to_dict() for i in self.material_issues],
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
            propositions=[Proposition.from_dict(p) for p in data.get("propositions", [])],
            material_issues=[MaterialIssue.from_dict(i) for i in data.get("material_issues", [])],
            summary=data.get("summary"),
            metadata=data.get("metadata", {}),
        )

    def save(self, path: Optional[Path] = None) -> Path:
        """
        Save case to JSON file.

        If the case directory has an encrypted vault and session is active,
        saves to case.json.enc. Otherwise saves to case.json.
        """
        if path is None:
            if self.output_dir is None:
                raise ValueError("No output directory specified")
            path = self.output_dir / "case.json"

        path.parent.mkdir(parents=True, exist_ok=True)
        case_dir = path.parent

        # Check if vault is encrypted and unlocked
        try:
            from ..vault import is_vault_encrypted, get_vault_session, VaultManager

            if is_vault_encrypted(case_dir):
                session = get_vault_session(case_dir)
                if session:
                    # Save encrypted
                    vm = VaultManager(case_dir)
                    encrypted_path = vm.get_encrypted_path(path)
                    vm.encrypt_json(self.to_dict(), encrypted_path, session)

                    # Remove unencrypted version if it exists
                    if path.exists() and path != encrypted_path:
                        path.unlink()

                    return encrypted_path
                else:
                    # Vault is locked - can't save
                    from ..vault import VaultLockedError
                    raise VaultLockedError(f"Vault is locked. Unlock with 'vault-unlock' to save: {case_dir}")
        except ImportError:
            pass  # Vault module not available, save unencrypted

        # Save unencrypted
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

        return path

    @classmethod
    def load(cls, path: Path) -> "Case":
        """
        Load case from JSON file.

        Automatically handles encrypted vaults if session is active.
        Looks for case.json.enc first, then falls back to case.json.
        """
        case_dir = path.parent

        # Check for encrypted vault
        try:
            from ..vault import is_vault_encrypted, get_vault_session, VaultManager

            if is_vault_encrypted(case_dir):
                session = get_vault_session(case_dir)
                if session:
                    vm = VaultManager(case_dir)

                    # Check for encrypted version
                    encrypted_path = vm.get_encrypted_path(path)
                    if encrypted_path.exists():
                        data = vm.decrypt_json(encrypted_path, session)
                        return cls.from_dict(data)

                    # Fall back to unencrypted if exists
                    if path.exists():
                        with open(path, encoding="utf-8") as f:
                            data = json.load(f)
                        return cls.from_dict(data)

                    raise FileNotFoundError(f"Case file not found: {path} or {encrypted_path}")
                else:
                    # Vault is locked
                    from ..vault import VaultLockedError
                    raise VaultLockedError(f"Vault is locked. Unlock with 'vault-unlock' to load: {case_dir}")
        except ImportError:
            pass  # Vault module not available, load unencrypted

        # Load unencrypted
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
