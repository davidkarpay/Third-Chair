"""Proposition and Skanda data models for legal evidence evaluation.

The Skanda Framework treats "fact" as an earned output label, not a stored boolean.
Propositions contain proposits (atomic evidence-backed claims) that are evaluated
deterministically to compute holds_under_scrutiny, weight, probative_value, and
burden_contribution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class PropositionKind(str, Enum):
    """Type of proposit claim."""
    DIRECT_OBSERVATION = "direct_observation"
    ADMISSION = "admission"
    INFERENCE = "inference"
    DOCUMENT_CONTENT = "document_content"
    EXPERT_OPINION = "expert_opinion"


class Polarity(str, Enum):
    """Whether a proposit supports or undermines the proposition."""
    SUPPORTS = "supports"
    UNDERMINES = "undermines"


class HoldsStatus(str, Enum):
    """Tri-state evaluation of whether proposition holds under scrutiny."""
    HOLDS = "holds"
    FAILS = "fails"
    UNCERTAIN = "uncertain"


class TestResult(str, Enum):
    """Result of a proposit test."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class BurdenStandard(str, Enum):
    """Legal standards for burden of persuasion."""
    BEYOND_REASONABLE_DOUBT = "beyond_reasonable_doubt"
    CLEAR_AND_CONVINCING = "clear_and_convincing"
    PREPONDERANCE = "preponderance"


@dataclass
class EvidenceRef:
    """Anchor to actual evidence in the case."""
    evidence_id: str
    filename: str
    source_type: str  # transcript_segment, document_span, image
    speaker: Optional[str] = None
    speaker_role: Optional[str] = None
    start_time_seconds: Optional[float] = None
    end_time_seconds: Optional[float] = None
    page: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    transcript_segment_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "evidence_id": self.evidence_id,
            "filename": self.filename,
            "source_type": self.source_type,
            "speaker": self.speaker,
            "speaker_role": self.speaker_role,
            "start_time_seconds": self.start_time_seconds,
            "end_time_seconds": self.end_time_seconds,
            "page": self.page,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "transcript_segment_id": self.transcript_segment_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvidenceRef":
        """Create from dictionary."""
        return cls(
            evidence_id=data["evidence_id"],
            filename=data["filename"],
            source_type=data["source_type"],
            speaker=data.get("speaker"),
            speaker_role=data.get("speaker_role"),
            start_time_seconds=data.get("start_time_seconds"),
            end_time_seconds=data.get("end_time_seconds"),
            page=data.get("page"),
            char_start=data.get("char_start"),
            char_end=data.get("char_end"),
            transcript_segment_id=data.get("transcript_segment_id"),
        )


@dataclass
class PropositionTest:
    """A test applied to a proposit to evaluate reliability."""
    test_id: str
    name: str
    method: str
    result: TestResult
    reason: str
    parameters: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "test_id": self.test_id,
            "name": self.name,
            "method": self.method,
            "result": self.result.value,
            "reason": self.reason,
            "parameters": self.parameters,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PropositionTest":
        """Create from dictionary."""
        return cls(
            test_id=data["test_id"],
            name=data["name"],
            method=data["method"],
            result=TestResult(data["result"]),
            reason=data["reason"],
            parameters=data.get("parameters", {}),
        )


@dataclass
class Proposit:
    """
    Atomic, testable mini-proposition backed by evidence.

    Each proposit must have at least one EvidenceRef. This is enforced
    at creation time to ensure traceability.
    """
    id: str
    claim: str
    kind: PropositionKind
    polarity: Polarity
    evidence_refs: list[EvidenceRef]
    tests: list[PropositionTest] = field(default_factory=list)
    weight: float = 0.5  # Computed from tests and source reliability
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    excluded: bool = False  # Human override: do not use in evaluation
    exclusion_reason: Optional[str] = None

    def __post_init__(self):
        """Validate that proposit has at least one evidence reference."""
        if not self.evidence_refs:
            raise ValueError(
                f"Proposit '{self.id}' must have at least one EvidenceRef. "
                "Every claim must be anchored to evidence."
            )

    @property
    def is_valid_for_evaluation(self) -> bool:
        """Check if proposit should be included in evaluation."""
        if self.excluded:
            return False
        # Check for critical test failures
        for test in self.tests:
            if test.result == TestResult.FAIL:
                return False
        return True

    @property
    def has_warnings(self) -> bool:
        """Check if any tests have warnings."""
        return any(t.result == TestResult.WARN for t in self.tests)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "claim": self.claim,
            "kind": self.kind.value,
            "polarity": self.polarity.value,
            "evidence_refs": [ref.to_dict() for ref in self.evidence_refs],
            "tests": [t.to_dict() for t in self.tests],
            "weight": self.weight,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "excluded": self.excluded,
            "exclusion_reason": self.exclusion_reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Proposit":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            claim=data["claim"],
            kind=PropositionKind(data["kind"]),
            polarity=Polarity(data["polarity"]),
            evidence_refs=[EvidenceRef.from_dict(r) for r in data["evidence_refs"]],
            tests=[PropositionTest.from_dict(t) for t in data.get("tests", [])],
            weight=data.get("weight", 0.5),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            modified_at=datetime.fromisoformat(data["modified_at"]) if "modified_at" in data else datetime.now(),
            excluded=data.get("excluded", False),
            exclusion_reason=data.get("exclusion_reason"),
        )


@dataclass
class SkandaDependency:
    """Dependency relationship between proposits."""
    if_fails: str  # Proposit ID that if it fails...
    then_weaken: list[str]  # ...these proposits become weaker

    def to_dict(self) -> dict:
        return {"if_fails": self.if_fails, "then_weaken": self.then_weaken}

    @classmethod
    def from_dict(cls, data: dict) -> "SkandaDependency":
        return cls(if_fails=data["if_fails"], then_weaken=data["then_weaken"])


@dataclass
class SkandaCluster:
    """Cluster of related proposits."""
    label: str
    members: list[str]  # Proposit IDs

    def to_dict(self) -> dict:
        return {"label": self.label, "members": self.members}

    @classmethod
    def from_dict(cls, data: dict) -> "SkandaCluster":
        return cls(label=data["label"], members=data["members"])


@dataclass
class SkandaStructure:
    """Structure of dependencies and clusters within a skanda."""
    dependencies: list[SkandaDependency] = field(default_factory=list)
    clusters: list[SkandaCluster] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "dependencies": [d.to_dict() for d in self.dependencies],
            "clusters": [c.to_dict() for c in self.clusters],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SkandaStructure":
        return cls(
            dependencies=[SkandaDependency.from_dict(d) for d in data.get("dependencies", [])],
            clusters=[SkandaCluster.from_dict(c) for c in data.get("clusters", [])],
        )


@dataclass
class Skanda:
    """
    Basket of proposits for a proposition.

    Contains supporting and undermining evidence with structural
    relationships (dependencies, clusters).
    """
    proposits: list[Proposit] = field(default_factory=list)
    structure: SkandaStructure = field(default_factory=SkandaStructure)
    version: int = 1
    last_modified: datetime = field(default_factory=datetime.now)

    @property
    def supporting(self) -> list[Proposit]:
        """Get proposits that support the proposition."""
        return [p for p in self.proposits if p.polarity == Polarity.SUPPORTS and p.is_valid_for_evaluation]

    @property
    def undermining(self) -> list[Proposit]:
        """Get proposits that undermine the proposition."""
        return [p for p in self.proposits if p.polarity == Polarity.UNDERMINES and p.is_valid_for_evaluation]

    @property
    def support_score(self) -> float:
        """Calculate total support weight."""
        return sum(p.weight for p in self.supporting)

    @property
    def undermine_score(self) -> float:
        """Calculate total undermine weight."""
        return sum(p.weight for p in self.undermining)

    def get_proposit(self, proposit_id: str) -> Optional[Proposit]:
        """Get proposit by ID."""
        for p in self.proposits:
            if p.id == proposit_id:
                return p
        return None

    def add_proposit(self, proposit: Proposit) -> None:
        """Add a proposit to the skanda."""
        self.proposits.append(proposit)
        self.version += 1
        self.last_modified = datetime.now()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "proposits": [p.to_dict() for p in self.proposits],
            "structure": self.structure.to_dict(),
            "version": self.version,
            "last_modified": self.last_modified.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Skanda":
        """Create from dictionary."""
        return cls(
            proposits=[Proposit.from_dict(p) for p in data.get("proposits", [])],
            structure=SkandaStructure.from_dict(data.get("structure", {})),
            version=data.get("version", 1),
            last_modified=datetime.fromisoformat(data["last_modified"]) if "last_modified" in data else datetime.now(),
        )


@dataclass
class EvaluationDrivers:
    """Top supporting and undermining proposits that drive evaluation."""
    top_supporting: list[str] = field(default_factory=list)  # Proposit IDs
    top_undermining: list[str] = field(default_factory=list)  # Proposit IDs

    def to_dict(self) -> dict:
        return {
            "top_supporting": self.top_supporting,
            "top_undermining": self.top_undermining,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationDrivers":
        return cls(
            top_supporting=data.get("top_supporting", []),
            top_undermining=data.get("top_undermining", []),
        )


@dataclass
class BurdenContribution:
    """How much the proposition contributes to meeting the burden."""
    toward_proponent: float  # 0.0-1.0
    explanation: str
    sufficiency_category: str = "uncertain"  # unlikely_sufficient, borderline, likely_sufficient

    def to_dict(self) -> dict:
        return {
            "toward_proponent": self.toward_proponent,
            "explanation": self.explanation,
            "sufficiency_category": self.sufficiency_category,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BurdenContribution":
        return cls(
            toward_proponent=data.get("toward_proponent", 0.0),
            explanation=data.get("explanation", ""),
            sufficiency_category=data.get("sufficiency_category", "uncertain"),
        )


@dataclass
class EvaluationSnapshot:
    """
    Computed evaluation of a proposition.

    This is replaceable and should never be treated as "truth".
    It is derived from the skanda and can be recomputed at any time.
    """
    as_of: datetime
    holds_under_scrutiny: HoldsStatus
    weight: float  # 0.0-1.0 for attention priority
    probative_value: float  # 0.0-1.0 relative to material issue
    burden_contribution: BurdenContribution
    drivers: EvaluationDrivers
    human_review_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "as_of": self.as_of.isoformat(),
            "holds_under_scrutiny": self.holds_under_scrutiny.value,
            "weight": self.weight,
            "probative_value": self.probative_value,
            "burden_contribution": self.burden_contribution.to_dict(),
            "drivers": self.drivers.to_dict(),
            "human_review_flags": self.human_review_flags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationSnapshot":
        """Create from dictionary."""
        return cls(
            as_of=datetime.fromisoformat(data["as_of"]),
            holds_under_scrutiny=HoldsStatus(data["holds_under_scrutiny"]),
            weight=data["weight"],
            probative_value=data["probative_value"],
            burden_contribution=BurdenContribution.from_dict(data["burden_contribution"]),
            drivers=EvaluationDrivers.from_dict(data["drivers"]),
            human_review_flags=data.get("human_review_flags", []),
        )


@dataclass
class ProponentInfo:
    """Information about who is advancing the proposition."""
    party: str  # Defense, State, Plaintiff, etc.
    attorney_note: Optional[str] = None

    def to_dict(self) -> dict:
        return {"party": self.party, "attorney_note": self.attorney_note}

    @classmethod
    def from_dict(cls, data: dict) -> "ProponentInfo":
        return cls(party=data["party"], attorney_note=data.get("attorney_note"))


@dataclass
class MaterialIssueRef:
    """Reference to a material issue the proposition addresses."""
    issue_id: str
    label: str
    elements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"issue_id": self.issue_id, "label": self.label, "elements": self.elements}

    @classmethod
    def from_dict(cls, data: dict) -> "MaterialIssueRef":
        return cls(
            issue_id=data["issue_id"],
            label=data["label"],
            elements=data.get("elements", []),
        )


@dataclass
class BurdenInfo:
    """Information about burden of persuasion and production."""
    persuasion_party: str  # Who bears burden of persuasion
    persuasion_standard: BurdenStandard
    production_party: Optional[str] = None
    production_met: bool = False

    def to_dict(self) -> dict:
        return {
            "persuasion_party": self.persuasion_party,
            "persuasion_standard": self.persuasion_standard.value,
            "production_party": self.production_party,
            "production_met": self.production_met,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BurdenInfo":
        return cls(
            persuasion_party=data["persuasion_party"],
            persuasion_standard=BurdenStandard(data["persuasion_standard"]),
            production_party=data.get("production_party"),
            production_met=data.get("production_met", False),
        )


@dataclass
class Proposition:
    """
    The main assertion you might make at trial.

    A proposition is not "true" or "false" - it has a skanda (basket of evidence)
    and an evaluation snapshot that is computed deterministically.
    """
    id: str
    statement: str
    proponent: ProponentInfo
    material_issue: MaterialIssueRef
    burden: BurdenInfo
    skanda: Skanda
    evaluation: Optional[EvaluationSnapshot] = None
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)

    @property
    def needs_evaluation(self) -> bool:
        """Check if proposition needs (re)evaluation."""
        if self.evaluation is None:
            return True
        # Re-evaluate if skanda was modified after last evaluation
        return self.skanda.last_modified > self.evaluation.as_of

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "statement": self.statement,
            "proponent": self.proponent.to_dict(),
            "material_issue": self.material_issue.to_dict(),
            "burden": self.burden.to_dict(),
            "skanda": self.skanda.to_dict(),
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Proposition":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            statement=data["statement"],
            proponent=ProponentInfo.from_dict(data["proponent"]),
            material_issue=MaterialIssueRef.from_dict(data["material_issue"]),
            burden=BurdenInfo.from_dict(data["burden"]),
            skanda=Skanda.from_dict(data["skanda"]),
            evaluation=EvaluationSnapshot.from_dict(data["evaluation"]) if data.get("evaluation") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            modified_at=datetime.fromisoformat(data["modified_at"]) if "modified_at" in data else datetime.now(),
        )


@dataclass
class MaterialIssue:
    """
    A material issue in the case (e.g., self-defense, assault).

    Material issues have elements that must be established.
    """
    id: str
    label: str
    description: str
    elements: list[str]
    default_burden_party: str
    default_burden_standard: BurdenStandard

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "elements": self.elements,
            "default_burden_party": self.default_burden_party,
            "default_burden_standard": self.default_burden_standard.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MaterialIssue":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            label=data["label"],
            description=data["description"],
            elements=data["elements"],
            default_burden_party=data["default_burden_party"],
            default_burden_standard=BurdenStandard(data["default_burden_standard"]),
        )


# Common material issue templates
MATERIAL_ISSUE_TEMPLATES = {
    "self_defense": MaterialIssue(
        id="issue_self_defense",
        label="Self-Defense / Justifiable Use of Force",
        description="Whether defendant was justified in using force",
        elements=[
            "who_used_force_first",
            "imminence_of_threat",
            "proportionality_of_response",
            "duty_to_retreat",
            "no_provocation_by_defendant",
        ],
        default_burden_party="State",
        default_burden_standard=BurdenStandard.BEYOND_REASONABLE_DOUBT,
    ),
    "assault": MaterialIssue(
        id="issue_assault",
        label="Assault",
        description="Whether defendant committed assault",
        elements=[
            "intentional_act",
            "contact_or_threat",
            "without_consent",
            "resulting_harm_or_fear",
        ],
        default_burden_party="State",
        default_burden_standard=BurdenStandard.BEYOND_REASONABLE_DOUBT,
    ),
    "battery": MaterialIssue(
        id="issue_battery",
        label="Battery",
        description="Whether defendant committed battery",
        elements=[
            "intentional_act",
            "actual_physical_contact",
            "offensive_or_harmful",
            "without_consent",
        ],
        default_burden_party="State",
        default_burden_standard=BurdenStandard.BEYOND_REASONABLE_DOUBT,
    ),
}
