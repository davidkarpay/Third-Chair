"""Transcript data models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Language(str, Enum):
    """Supported languages."""

    ENGLISH = "en"
    SPANISH = "es"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ReviewFlag(str, Enum):
    """Flags for segments requiring human review."""

    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    CODE_SWITCHED = "CODE_SWITCHED"
    SHORT_PHRASE = "SHORT_PHRASE"
    SPEAKER_OVERLAP = "SPEAKER_OVERLAP"
    TRANSLATION_UNCERTAIN = "TRANSLATION_UNCERTAIN"
    THREAT_KEYWORD = "THREAT_KEYWORD"
    VIOLENCE_KEYWORD = "VIOLENCE_KEYWORD"


class SpeakerRole(str, Enum):
    """Detected speaker roles."""

    OFFICER = "Officer"
    VICTIM = "Victim"
    WITNESS = "Witness"
    SUSPECT = "Suspect"
    INTERPRETER = "Interpreter"
    UNKNOWN = "Unknown"


@dataclass
class TranscriptSegment:
    """A single segment of a transcript."""

    start_time: float
    end_time: float
    speaker: str  # SPEAKER_1, SPEAKER_2, or named
    text: str
    speaker_role: Optional[SpeakerRole] = None
    language: Language = Language.ENGLISH
    translation: Optional[str] = None
    confidence: float = 1.0
    review_flags: list[ReviewFlag] = field(default_factory=list)
    extracted_phrases: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """Get segment duration in seconds."""
        return self.end_time - self.start_time

    @property
    def needs_review(self) -> bool:
        """Check if segment needs human review."""
        return len(self.review_flags) > 0

    @property
    def is_translated(self) -> bool:
        """Check if segment has been translated."""
        return self.translation is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "speaker": self.speaker,
            "speaker_role": self.speaker_role.value if self.speaker_role else None,
            "text": self.text,
            "language": self.language.value,
            "translation": self.translation,
            "confidence": self.confidence,
            "review_flags": [f.value for f in self.review_flags],
            "extracted_phrases": self.extracted_phrases,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranscriptSegment":
        """Create from dictionary."""
        return cls(
            start_time=data["start_time"],
            end_time=data["end_time"],
            speaker=data["speaker"],
            text=data["text"],
            speaker_role=SpeakerRole(data["speaker_role"]) if data.get("speaker_role") else None,
            language=Language(data.get("language", "en")),
            translation=data.get("translation"),
            confidence=data.get("confidence", 1.0),
            review_flags=[ReviewFlag(f) for f in data.get("review_flags", [])],
            extracted_phrases=data.get("extracted_phrases", []),
        )


@dataclass
class Transcript:
    """Complete transcript for an evidence item."""

    evidence_id: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    speakers: dict[str, str] = field(default_factory=dict)  # SPEAKER_1 -> "John Doe"
    language_distribution: dict[str, int] = field(default_factory=dict)
    key_statements: list[TranscriptSegment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        """Get total transcript duration."""
        if not self.segments:
            return 0.0
        return self.segments[-1].end_time - self.segments[0].start_time

    @property
    def segment_count(self) -> int:
        """Get number of segments."""
        return len(self.segments)

    @property
    def speaker_count(self) -> int:
        """Get number of unique speakers."""
        return len(set(s.speaker for s in self.segments))

    def get_speaker_name(self, speaker_id: str) -> str:
        """Get the name for a speaker ID, or return the ID if not named."""
        return self.speakers.get(speaker_id, speaker_id)

    def rename_speaker(self, speaker_id: str, name: str) -> None:
        """Rename a speaker."""
        self.speakers[speaker_id] = name

    def get_segments_for_speaker(self, speaker: str) -> list[TranscriptSegment]:
        """Get all segments for a specific speaker."""
        return [s for s in self.segments if s.speaker == speaker]

    def get_segments_needing_review(self) -> list[TranscriptSegment]:
        """Get all segments that need human review."""
        return [s for s in self.segments if s.needs_review]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "evidence_id": self.evidence_id,
            "segments": [s.to_dict() for s in self.segments],
            "speakers": self.speakers,
            "language_distribution": self.language_distribution,
            "key_statements": [s.to_dict() for s in self.key_statements],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Transcript":
        """Create from dictionary."""
        return cls(
            evidence_id=data["evidence_id"],
            segments=[TranscriptSegment.from_dict(s) for s in data.get("segments", [])],
            speakers=data.get("speakers", {}),
            language_distribution=data.get("language_distribution", {}),
            key_statements=[
                TranscriptSegment.from_dict(s) for s in data.get("key_statements", [])
            ],
            metadata=data.get("metadata", {}),
        )

    def to_plain_text(self, include_timestamps: bool = True) -> str:
        """Convert transcript to plain text format."""
        lines = []
        for segment in self.segments:
            speaker_name = self.get_speaker_name(segment.speaker)
            if include_timestamps:
                timestamp = f"[{segment.start_time:.1f}s]"
                lines.append(f"{timestamp} [{speaker_name}]: {segment.text}")
            else:
                lines.append(f"[{speaker_name}]: {segment.text}")

            if segment.translation:
                lines.append(f"    [Translation]: {segment.translation}")

        return "\n".join(lines)

    def to_srt(self) -> str:
        """Convert transcript to SRT subtitle format."""
        lines = []
        for i, segment in enumerate(self.segments, 1):
            start = _format_srt_time(segment.start_time)
            end = _format_srt_time(segment.end_time)
            speaker_name = self.get_speaker_name(segment.speaker)

            lines.append(str(i))
            lines.append(f"{start} --> {end}")
            lines.append(f"[{speaker_name}] {segment.text}")
            lines.append("")

        return "\n".join(lines)


def _format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
