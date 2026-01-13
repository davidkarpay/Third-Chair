"""Timeline construction from case evidence.

Builds a chronological timeline of events from:
- Transcript timestamps
- Document dates
- Evidence metadata
"""

import re
from dataclasses import dataclass
from datetime import datetime, date, time
from typing import Optional

from ..models import Case, EvidenceItem, TimelineEvent, Transcript


@dataclass
class TimelineEntry:
    """An entry in the timeline."""

    timestamp: datetime
    description: str
    evidence_id: str
    source_type: str  # transcript, document, metadata
    speaker: Optional[str] = None
    importance: str = "normal"  # normal, high, critical

    def to_timeline_event(self) -> TimelineEvent:
        """Convert to TimelineEvent model."""
        return TimelineEvent(
            timestamp=self.timestamp,
            description=self.description,
            evidence_id=self.evidence_id,
            source=self.source_type,
            metadata={
                "speaker": self.speaker,
                "importance": self.importance,
            },
        )


def build_timeline(case: Case) -> list[TimelineEntry]:
    """
    Build a chronological timeline from all case evidence.

    Args:
        case: Case to analyze

    Returns:
        Sorted list of timeline entries
    """
    entries: list[TimelineEntry] = []

    for evidence in case.evidence_items:
        # Extract from transcripts
        if evidence.transcript:
            transcript_entries = _extract_from_transcript(
                evidence.transcript,
                evidence,
            )
            entries.extend(transcript_entries)

        # Extract from metadata
        metadata_entries = _extract_from_metadata(evidence)
        entries.extend(metadata_entries)

    # Sort by timestamp
    entries.sort(key=lambda e: e.timestamp)

    return entries


def _extract_from_transcript(
    transcript: Transcript,
    evidence: EvidenceItem,
) -> list[TimelineEntry]:
    """Extract timeline entries from a transcript."""
    entries = []

    # Get base timestamp from evidence metadata
    base_time = _get_evidence_base_time(evidence)

    if not base_time:
        # Use a default if no base time available
        base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Add entry for start of recording
    entries.append(TimelineEntry(
        timestamp=base_time,
        description=f"Recording started: {evidence.filename}",
        evidence_id=evidence.id,
        source_type="transcript",
        importance="normal",
    ))

    # Extract significant events from transcript
    for segment in transcript.segments:
        event = _analyze_segment_for_timeline(segment, transcript)

        if event:
            # Calculate absolute timestamp
            segment_time = base_time.replace(
                second=0, microsecond=0
            )
            # Add segment offset
            total_seconds = int(segment.start_time)
            minutes = total_seconds // 60
            seconds = total_seconds % 60

            try:
                segment_time = segment_time.replace(
                    minute=(segment_time.minute + minutes) % 60,
                    second=seconds,
                )
                # Handle hour overflow
                if segment_time.minute + minutes >= 60:
                    segment_time = segment_time.replace(
                        hour=segment_time.hour + (segment_time.minute + minutes) // 60
                    )
            except ValueError:
                pass  # Keep base time if calculation fails

            entries.append(TimelineEntry(
                timestamp=segment_time,
                description=event["description"],
                evidence_id=evidence.id,
                source_type="transcript",
                speaker=segment.speaker,
                importance=event["importance"],
            ))

    # Add key statements
    for statement in transcript.key_statements:
        entries.append(TimelineEntry(
            timestamp=base_time,
            description=f"Key statement: {statement.text[:100]}",
            evidence_id=evidence.id,
            source_type="transcript",
            speaker=statement.speaker,
            importance="high",
        ))

    return entries


def _analyze_segment_for_timeline(
    segment,
    transcript: Transcript,
) -> Optional[dict]:
    """
    Analyze a segment for timeline-worthy events.

    Returns dict with description and importance, or None.
    """
    text_lower = segment.text.lower()

    # Look for action indicators
    action_patterns = [
        (r"\b(arrived|llegó|got here|llegamos)\b", "Arrival", "normal"),
        (r"\b(left|departed|se fue|salió)\b", "Departure", "normal"),
        (r"\b(called|llamó|call 911|llamar)\b", "Call made", "normal"),
        (r"\b(arrested|arresto|cuffed|esposado)\b", "Arrest", "high"),
        (r"\b(shot|disparo|fired|disparó)\b", "Shooting", "critical"),
        (r"\b(ambulance|paramedic|emt|ambulancia)\b", "Medical response", "high"),
        (r"\b(backup|refuerzo|additional units)\b", "Backup called", "normal"),
        (r"\b(victim|víctima) (identified|encontr)", "Victim identified", "high"),
        (r"\b(suspect|sospechoso) (fled|huyó|ran|corrió)\b", "Suspect fled", "high"),
        (r"\b(weapon|arma) (found|recovered|encontr)", "Weapon recovered", "high"),
    ]

    for pattern, event_type, importance in action_patterns:
        if re.search(pattern, text_lower):
            speaker_name = transcript.get_speaker_name(segment.speaker)
            return {
                "description": f"{event_type} ({speaker_name})",
                "importance": importance,
            }

    return None


def _extract_from_metadata(evidence: EvidenceItem) -> list[TimelineEntry]:
    """Extract timeline entries from evidence metadata."""
    entries = []

    # Check for date in metadata
    date_fields = ["date", "toc_date", "created", "incident_date"]

    for field in date_fields:
        if field in evidence.metadata:
            date_str = str(evidence.metadata[field])
            parsed_date = _parse_date(date_str)

            if parsed_date:
                entries.append(TimelineEntry(
                    timestamp=datetime.combine(parsed_date, time(0, 0)),
                    description=f"Evidence created: {evidence.filename}",
                    evidence_id=evidence.id,
                    source_type="metadata",
                ))
                break

    return entries


def _get_evidence_base_time(evidence: EvidenceItem) -> Optional[datetime]:
    """Get the base timestamp for an evidence item."""
    # Check metadata for date/time
    date_value = None
    time_value = None

    if "date" in evidence.metadata:
        date_value = _parse_date(str(evidence.metadata["date"]))

    if "time" in evidence.metadata:
        time_value = _parse_time(str(evidence.metadata["time"]))

    if "toc_date" in evidence.metadata:
        date_value = date_value or _parse_date(str(evidence.metadata["toc_date"]))

    if date_value:
        if time_value:
            return datetime.combine(date_value, time_value)
        return datetime.combine(date_value, time(0, 0))

    # Try to parse from filename
    filename = evidence.filename

    # Pattern: YYYYMMDD
    match = re.search(r"(\d{4})(\d{2})(\d{2})", filename)
    if match:
        try:
            d = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            return datetime.combine(d, time(0, 0))
        except ValueError:
            pass

    return None


def _parse_date(date_str: str) -> Optional[date]:
    """Parse a date string."""
    formats = [
        "%Y-%m-%d",
        "%m-%d-%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d-%m-%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    return None


def _parse_time(time_str: str) -> Optional[time]:
    """Parse a time string."""
    formats = [
        "%H:%M:%S",
        "%H:%M",
        "%I:%M:%S %p",
        "%I:%M %p",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue

    return None


def add_timeline_to_case(case: Case) -> Case:
    """
    Build and add timeline to a case.

    Args:
        case: Case to update

    Returns:
        Updated case with timeline
    """
    entries = build_timeline(case)

    # Convert to TimelineEvent objects
    case.timeline = [entry.to_timeline_event() for entry in entries]

    return case


def format_timeline(entries: list[TimelineEntry]) -> str:
    """
    Format timeline entries as readable text.

    Args:
        entries: Timeline entries to format

    Returns:
        Formatted timeline string
    """
    lines = []
    current_date = None

    for entry in entries:
        # Add date header when date changes
        entry_date = entry.timestamp.date()
        if entry_date != current_date:
            current_date = entry_date
            lines.append(f"\n=== {entry_date.strftime('%B %d, %Y')} ===\n")

        # Format time
        time_str = entry.timestamp.strftime("%H:%M:%S")

        # Add importance indicator
        prefix = ""
        if entry.importance == "critical":
            prefix = "[!!!] "
        elif entry.importance == "high":
            prefix = "[!] "

        # Format entry
        lines.append(f"{time_str}  {prefix}{entry.description}")

        if entry.speaker:
            lines.append(f"          Speaker: {entry.speaker}")

    return "\n".join(lines)
