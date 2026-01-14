"""Data models for Third Chair."""

from .case import Case, TimelineEvent
from .evidence import (
    ContentType,
    EvidenceItem,
    FileType,
    ProcessingStatus,
    FILE_TYPE_MAP,
)
from .transcript import (
    Language,
    ReviewFlag,
    SpeakerRole,
    Transcript,
    TranscriptSegment,
)
from .witness import (
    Witness,
    WitnessList,
    WitnessRole,
    WitnessSource,
)
from .proposition import (
    BurdenContribution,
    BurdenInfo,
    BurdenStandard,
    EvaluationDrivers,
    EvaluationSnapshot,
    EvidenceRef,
    HoldsStatus,
    MaterialIssue,
    MaterialIssueRef,
    Polarity,
    ProponentInfo,
    Proposition,
    PropositionKind,
    PropositionTest,
    Proposit,
    Skanda,
    SkandaCluster,
    SkandaDependency,
    SkandaStructure,
    TestResult,
    MATERIAL_ISSUE_TEMPLATES,
)

__all__ = [
    # Case
    "Case",
    "TimelineEvent",
    # Evidence
    "ContentType",
    "EvidenceItem",
    "FileType",
    "ProcessingStatus",
    "FILE_TYPE_MAP",
    # Transcript
    "Language",
    "ReviewFlag",
    "SpeakerRole",
    "Transcript",
    "TranscriptSegment",
    # Witness
    "Witness",
    "WitnessList",
    "WitnessRole",
    "WitnessSource",
    # Proposition (Skanda Framework)
    "BurdenContribution",
    "BurdenInfo",
    "BurdenStandard",
    "EvaluationDrivers",
    "EvaluationSnapshot",
    "EvidenceRef",
    "HoldsStatus",
    "MaterialIssue",
    "MaterialIssueRef",
    "Polarity",
    "ProponentInfo",
    "Proposition",
    "PropositionKind",
    "PropositionTest",
    "Proposit",
    "Skanda",
    "SkandaCluster",
    "SkandaDependency",
    "SkandaStructure",
    "TestResult",
    "MATERIAL_ISSUE_TEMPLATES",
]
