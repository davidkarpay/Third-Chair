"""Match imported witnesses to diarized speakers.

This module correlates:
1. Witnesses from State Attorney lists
2. Speakers identified through diarization
3. Names mentioned in transcripts
"""

import re
from collections import defaultdict
from typing import Optional

from ..models import (
    Case,
    SpeakerRole,
    Transcript,
    Witness,
    WitnessList,
    WitnessRole,
    WitnessSource,
)
from .speaker_roles import detect_speaker_role


def extract_speakers_from_case(case: Case) -> WitnessList:
    """
    Extract all unique speakers from case transcripts.

    Creates Witness objects for each diarized speaker.

    Args:
        case: Case with transcripts

    Returns:
        WitnessList with speakers as witnesses
    """
    witnesses = WitnessList()
    speaker_evidence: dict[str, list[str]] = defaultdict(list)
    speaker_roles: dict[str, SpeakerRole] = {}

    # Collect speakers from all transcripts
    for evidence in case.evidence_items:
        if not evidence.transcript:
            continue

        transcript = evidence.transcript

        for segment in transcript.segments:
            speaker_id = segment.speaker
            speaker_evidence[speaker_id].append(evidence.id)

            # Track detected role
            if segment.speaker_role:
                # Keep the most specific role detected
                current = speaker_roles.get(speaker_id)
                if current is None or current == SpeakerRole.UNKNOWN:
                    speaker_roles[speaker_id] = segment.speaker_role

    # Create witness for each unique speaker
    for speaker_id, evidence_ids in speaker_evidence.items():
        role = speaker_roles.get(speaker_id, SpeakerRole.UNKNOWN)

        witness = Witness(
            name=None,  # Not yet named
            role=_speaker_role_to_witness_role(role),
            source=WitnessSource.DIARIZATION,
            speaker_ids=[speaker_id],
            evidence_appearances=list(set(evidence_ids)),
        )

        witnesses.add(witness)

    return witnesses


def _speaker_role_to_witness_role(speaker_role: SpeakerRole) -> WitnessRole:
    """Convert SpeakerRole to WitnessRole."""
    mapping = {
        SpeakerRole.OFFICER: WitnessRole.OFFICER,
        SpeakerRole.VICTIM: WitnessRole.VICTIM,
        SpeakerRole.WITNESS: WitnessRole.WITNESS,
        SpeakerRole.SUSPECT: WitnessRole.SUSPECT,
        SpeakerRole.INTERPRETER: WitnessRole.INTERPRETER,
        SpeakerRole.UNKNOWN: WitnessRole.OTHER,
    }
    return mapping.get(speaker_role, WitnessRole.OTHER)


def match_witnesses_to_speakers(
    imported_witnesses: WitnessList,
    speaker_witnesses: WitnessList,
    transcripts: list[Transcript],
) -> WitnessList:
    """
    Match imported witnesses to diarized speakers.

    Uses multiple signals:
    1. Role matching (victim matches victim speaker)
    2. Name mentions in transcript
    3. Order of appearance
    4. Speaking time distribution

    Args:
        imported_witnesses: Witnesses from State Attorney list
        speaker_witnesses: Witnesses from diarization
        transcripts: Transcripts to search for name mentions

    Returns:
        Merged WitnessList with matches
    """
    merged = WitnessList()

    # Track which speakers have been matched
    matched_speakers: set[str] = set()

    # First pass: Match by role and evidence
    for imported in imported_witnesses.witnesses:
        best_match: Optional[Witness] = None
        best_score = 0.0

        for speaker in speaker_witnesses.witnesses:
            # Skip already matched
            speaker_id = speaker.speaker_ids[0] if speaker.speaker_ids else None
            if speaker_id in matched_speakers:
                continue

            score = _calculate_match_score(
                imported, speaker, transcripts
            )

            if score > best_score:
                best_score = score
                best_match = speaker

        if best_match and best_score >= 0.5:
            # Merge the witnesses
            merged_witness = _merge_witnesses(imported, best_match)
            merged.add(merged_witness)

            # Mark speaker as matched
            for sid in best_match.speaker_ids:
                matched_speakers.add(sid)
        else:
            # No match found, add imported witness as-is
            merged.add(imported)

    # Add unmatched speakers
    for speaker in speaker_witnesses.witnesses:
        speaker_id = speaker.speaker_ids[0] if speaker.speaker_ids else None
        if speaker_id not in matched_speakers:
            merged.add(speaker)

    return merged


def _calculate_match_score(
    imported: Witness,
    speaker: Witness,
    transcripts: list[Transcript],
) -> float:
    """
    Calculate match score between imported witness and speaker.

    Returns score from 0.0 to 1.0.
    """
    score = 0.0

    # Role match (0.3 points)
    if imported.role == speaker.role:
        score += 0.3
    elif (imported.role == WitnessRole.VICTIM and
          speaker.role == WitnessRole.WITNESS):
        # Close match
        score += 0.15
    elif (imported.role == WitnessRole.WITNESS and
          speaker.role == WitnessRole.VICTIM):
        score += 0.15

    # Name mention in transcript (0.5 points)
    if imported.name:
        name_mentioned = _check_name_in_transcripts(
            imported.name,
            speaker.speaker_ids,
            transcripts,
        )
        if name_mentioned:
            score += 0.5

    # Evidence overlap (0.2 points)
    if imported.evidence_appearances and speaker.evidence_appearances:
        overlap = set(imported.evidence_appearances) & set(speaker.evidence_appearances)
        if overlap:
            score += 0.2 * len(overlap) / max(
                len(imported.evidence_appearances),
                len(speaker.evidence_appearances)
            )

    return min(score, 1.0)


def _check_name_in_transcripts(
    name: str,
    speaker_ids: list[str],
    transcripts: list[Transcript],
) -> bool:
    """
    Check if a name is mentioned near a speaker's segments.

    Looks for patterns like:
    - Speaker addressing someone by name
    - Name mentioned in same timestamp range
    """
    # Extract name parts for matching
    name_parts = name.lower().split()
    if not name_parts:
        return False

    first_name = name_parts[0]
    last_name = name_parts[-1] if len(name_parts) > 1 else None

    for transcript in transcripts:
        for i, segment in enumerate(transcript.segments):
            # Check if segment is from one of the speaker IDs
            if segment.speaker in speaker_ids:
                # Look at surrounding segments for name mention
                context_start = max(0, i - 2)
                context_end = min(len(transcript.segments), i + 3)

                for j in range(context_start, context_end):
                    if j == i:
                        continue

                    context_seg = transcript.segments[j]
                    text_lower = context_seg.text.lower()

                    # Check for name mention
                    if first_name in text_lower:
                        return True
                    if last_name and last_name in text_lower:
                        return True

                    # Check for addressing patterns
                    patterns = [
                        rf"\b{first_name}\b",
                        rf"mr\.?\s*{last_name}" if last_name else None,
                        rf"ms\.?\s*{last_name}" if last_name else None,
                        rf"mrs\.?\s*{last_name}" if last_name else None,
                    ]

                    for pattern in patterns:
                        if pattern and re.search(pattern, text_lower):
                            return True

    return False


def _merge_witnesses(imported: Witness, speaker: Witness) -> Witness:
    """
    Merge an imported witness with a diarized speaker.

    The imported witness provides the name and metadata.
    The speaker provides the speaker IDs and evidence appearances.
    """
    return Witness(
        id=imported.id,  # Keep imported ID
        name=imported.name,
        role=imported.role if imported.role != WitnessRole.OTHER else speaker.role,
        source=WitnessSource.STATE_ATTORNEY_LIST,  # Primary source
        speaker_ids=speaker.speaker_ids,
        evidence_appearances=list(set(
            imported.evidence_appearances + speaker.evidence_appearances
        )),
        verified=True,  # Matched = verified
        notes=imported.notes,
        contact_info=imported.contact_info,
        metadata={
            "matched_from_diarization": True,
            "original_speaker_id": speaker.speaker_ids[0] if speaker.speaker_ids else None,
        },
    )


def find_name_mentions(
    transcript: Transcript,
    names: list[str],
) -> dict[str, list[dict]]:
    """
    Find mentions of names in a transcript.

    Args:
        transcript: Transcript to search
        names: List of names to search for

    Returns:
        Dict mapping names to list of mention locations
    """
    mentions: dict[str, list[dict]] = {name: [] for name in names}

    for i, segment in enumerate(transcript.segments):
        text_lower = segment.text.lower()

        for name in names:
            name_parts = name.lower().split()

            # Check for any part of the name
            for part in name_parts:
                if len(part) >= 3 and part in text_lower:
                    mentions[name].append({
                        "segment_index": i,
                        "timestamp": segment.start_time,
                        "speaker": segment.speaker,
                        "text": segment.text,
                        "matched_part": part,
                    })
                    break  # One match per segment per name

    return mentions


def suggest_speaker_names(
    transcript: Transcript,
) -> dict[str, list[str]]:
    """
    Suggest possible names for speakers based on transcript content.

    Looks for:
    - Names mentioned when addressing a speaker
    - Self-introductions
    - Name patterns in dialogue

    Args:
        transcript: Transcript to analyze

    Returns:
        Dict mapping speaker IDs to list of suggested names
    """
    suggestions: dict[str, list[str]] = defaultdict(list)

    # Patterns for name detection
    name_patterns = [
        # "My name is X"
        r"my name is ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        # "I'm X"
        r"i'm ([A-Z][a-z]+)",
        # "This is X speaking"
        r"this is ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+speaking",
        # "Call me X"
        r"call me ([A-Z][a-z]+)",
    ]

    # Patterns for being addressed
    address_patterns = [
        # "X, can you..."
        r"^([A-Z][a-z]+),\s+",
        # "Hey X"
        r"hey ([A-Z][a-z]+)",
        # "Mr./Ms./Mrs. X"
        r"(?:mr|ms|mrs|miss)\.?\s+([A-Z][a-z]+)",
    ]

    for i, segment in enumerate(transcript.segments):
        text = segment.text

        # Check for self-introduction
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).title()
                if name not in suggestions[segment.speaker]:
                    suggestions[segment.speaker].append(name)

        # Check for being addressed (look at next speaker)
        if i < len(transcript.segments) - 1:
            next_seg = transcript.segments[i + 1]
            if next_seg.speaker != segment.speaker:
                for pattern in address_patterns:
                    match = re.search(pattern, text)
                    if match:
                        name = match.group(1).title()
                        if name not in suggestions[next_seg.speaker]:
                            suggestions[next_seg.speaker].append(name)

    return dict(suggestions)
