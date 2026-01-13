"""Transcript summarization using Ollama.

Generates summaries for individual transcripts, including:
- Overall summary
- Key statements
- Speaker analysis
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from ..models import (
    EvidenceItem,
    ReviewFlag,
    Transcript,
    TranscriptSegment,
)
from .ollama_client import get_ollama_client, OllamaResponse


# Keywords that indicate important statements
THREAT_KEYWORDS = {
    "kill", "matar", "hurt", "harm", "gun", "pistola", "knife", "cuchillo",
    "shoot", "disparar", "stab", "die", "dead", "muerte", "threat", "amenaza",
}

VIOLENCE_KEYWORDS = {
    "hit", "golpe", "punch", "kick", "slap", "push", "grab", "choke",
    "beat", "attack", "assault", "fight", "blood", "sangre", "injury",
}

ADMISSION_KEYWORDS = {
    "i did", "yo hice", "i was there", "estuve ahí", "my fault", "mi culpa",
    "i'm sorry", "lo siento", "i admit", "admito",
}


@dataclass
class TranscriptSummary:
    """Summary of a transcript."""

    evidence_id: str
    summary: str
    key_points: list[str] = field(default_factory=list)
    key_statements: list[dict] = field(default_factory=list)
    speaker_roles: dict[str, str] = field(default_factory=dict)
    threat_count: int = 0
    violence_count: int = 0
    spanish_percentage: float = 0.0
    word_count: int = 0


def summarize_transcript(
    transcript: Transcript,
    max_summary_length: int = 200,
) -> TranscriptSummary:
    """
    Generate a comprehensive summary of a transcript.

    Args:
        transcript: Transcript to summarize
        max_summary_length: Maximum words in summary

    Returns:
        TranscriptSummary with all summary data
    """
    client = get_ollama_client()

    # Prepare transcript text
    transcript_text = _format_transcript_for_summary(transcript)

    result = TranscriptSummary(
        evidence_id=transcript.evidence_id,
        summary="",
        word_count=len(transcript_text.split()),
    )

    # Calculate language distribution
    total_segments = len(transcript.segments)
    if total_segments > 0:
        spanish_count = sum(
            1 for s in transcript.segments
            if s.language.value in ("es", "mixed")
        )
        result.spanish_percentage = (spanish_count / total_segments) * 100

    # Extract key statements locally (fast)
    result.key_statements = _extract_key_statements(transcript)
    result.threat_count = sum(
        1 for s in result.key_statements
        if s.get("type") == "threat"
    )
    result.violence_count = sum(
        1 for s in result.key_statements
        if s.get("type") == "violence"
    )

    # Generate AI summary
    response = client.summarize(
        text=transcript_text,
        max_length=max_summary_length,
        context=f"Body camera transcript with {len(transcript.segments)} segments",
    )

    if response.success:
        result.summary = response.text

    # Extract key points
    key_points_response = client.extract_key_points(
        text=transcript_text,
        num_points=5,
    )

    if key_points_response.success:
        result.key_points = _parse_key_points(key_points_response.text)

    # Get speaker roles from transcript metadata if available
    if transcript.metadata.get("speaker_roles"):
        result.speaker_roles = transcript.metadata["speaker_roles"]

    return result


def _format_transcript_for_summary(transcript: Transcript) -> str:
    """Format transcript segments for summarization."""
    lines = []

    for segment in transcript.segments:
        speaker = transcript.get_speaker_name(segment.speaker)
        text = segment.text

        # Include translation if available
        if segment.translation:
            text = f"{text} [{segment.translation}]"

        lines.append(f"{speaker}: {text}")

    return "\n".join(lines)


def _extract_key_statements(transcript: Transcript) -> list[dict]:
    """
    Extract key statements from transcript.

    Identifies:
    - Threats
    - Violence descriptions
    - Admissions
    - Flagged segments
    """
    key_statements = []

    for i, segment in enumerate(transcript.segments):
        text_lower = segment.text.lower()
        statement_type = None

        # Check for threats
        if any(kw in text_lower for kw in THREAT_KEYWORDS):
            statement_type = "threat"

        # Check for violence
        elif any(kw in text_lower for kw in VIOLENCE_KEYWORDS):
            statement_type = "violence"

        # Check for admissions
        elif any(kw in text_lower for kw in ADMISSION_KEYWORDS):
            statement_type = "admission"

        # Include flagged segments
        elif ReviewFlag.THREAT_KEYWORD in segment.review_flags:
            statement_type = "threat"
        elif ReviewFlag.VIOLENCE_KEYWORD in segment.review_flags:
            statement_type = "violence"

        if statement_type:
            key_statements.append({
                "type": statement_type,
                "speaker": segment.speaker,
                "timestamp": segment.start_time,
                "text": segment.text,
                "translation": segment.translation,
            })

    return key_statements


def _parse_key_points(text: str) -> list[str]:
    """Parse numbered key points from AI response."""
    points = []

    # Split by numbers
    parts = re.split(r"\d+[.)]\s*", text)

    for part in parts:
        part = part.strip()
        if part and len(part) > 10:  # Skip very short fragments
            points.append(part)

    return points[:5]  # Limit to 5 points


def summarize_evidence_transcript(
    evidence: EvidenceItem,
    save_summary: bool = True,
) -> Optional[TranscriptSummary]:
    """
    Summarize the transcript for an evidence item.

    Args:
        evidence: Evidence item with transcript
        save_summary: Whether to save summary to evidence

    Returns:
        TranscriptSummary or None if no transcript
    """
    if not evidence.transcript:
        return None

    summary = summarize_transcript(evidence.transcript)

    if save_summary:
        # Store summary text on evidence
        evidence.summary = summary.summary

        # Store additional data in metadata
        evidence.metadata["key_points"] = summary.key_points
        evidence.metadata["key_statements_count"] = len(summary.key_statements)
        evidence.metadata["threat_count"] = summary.threat_count
        evidence.metadata["violence_count"] = summary.violence_count

    return summary


def flag_key_statements(transcript: Transcript) -> Transcript:
    """
    Add review flags for key statements in a transcript.

    Args:
        transcript: Transcript to process

    Returns:
        Updated transcript with flags
    """
    for segment in transcript.segments:
        text_lower = segment.text.lower()

        # Flag threats
        if any(kw in text_lower for kw in THREAT_KEYWORDS):
            if ReviewFlag.THREAT_KEYWORD not in segment.review_flags:
                segment.review_flags.append(ReviewFlag.THREAT_KEYWORD)

        # Flag violence
        if any(kw in text_lower for kw in VIOLENCE_KEYWORDS):
            if ReviewFlag.VIOLENCE_KEYWORD not in segment.review_flags:
                segment.review_flags.append(ReviewFlag.VIOLENCE_KEYWORD)

    # Update key_statements list
    transcript.key_statements = [
        s for s in transcript.segments
        if (ReviewFlag.THREAT_KEYWORD in s.review_flags or
            ReviewFlag.VIOLENCE_KEYWORD in s.review_flags)
    ]

    return transcript
