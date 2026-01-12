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
]
