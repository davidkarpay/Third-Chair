"""Speaker role detection for transcripts.

Detects whether a speaker is likely an Officer, Victim, Witness, Suspect,
or Interpreter based on transcript content patterns.
"""

import re
from collections import defaultdict
from typing import Optional

from ..models import Language, SpeakerRole, Transcript, TranscriptSegment


# Officer indicators - commands, directives, law enforcement language
OFFICER_INDICATORS = {
    # Commands
    "show me your", "let me see", "put your hands", "hands up", "hands behind",
    "step out", "turn around", "don't move", "stay right there", "stop right there",
    "get on the ground", "on your knees", "spread your legs",
    # Questions officers ask
    "what's your name", "what is your name", "do you have id", "do you have any id",
    "where do you live", "what's your address", "date of birth", "can i see",
    "do you have any weapons", "anything on you", "been drinking",
    "do you understand", "is that correct", "am i clear",
    # Law enforcement terminology
    "you're under arrest", "under arrest", "miranda rights", "right to remain silent",
    "you have the right", "step over here", "wait right here",
    "dispatch", "10-4", "copy that", "backup", "officer on scene",
    "license and registration", "step out of the vehicle",
    # First person as officer
    "i'm going to", "i need you to", "i'm officer", "i'm deputy",
}

# Victim/Witness indicators - reporting harm, first-person incident description
VICTIM_INDICATORS = {
    # Violence/harm received
    "hit me", "struck me", "punched me", "kicked me", "slapped me",
    "pushed me", "grabbed me", "choked me", "attacked me", "assaulted me",
    "hurt me", "injured me", "beat me", "threw me",
    # Threats received
    "threatened me", "said he would", "said she would", "going to kill",
    "scared for my life", "feared for", "afraid of",
    # Property crimes
    "stole my", "took my", "broke into", "robbed me",
    # Reporting
    "i saw him", "i saw her", "i witnessed", "i was there when",
    "he did", "she did", "they did",
    # Spanish victim language
    "me golpeó", "me pegó", "me amenazó", "me robó", "me atacó",
    "tengo miedo", "me dijo que", "me hizo",
}

# Suspect indicators - denials, defensive language
SUSPECT_INDICATORS = {
    "i didn't do", "wasn't me", "i don't know what you're talking about",
    "i didn't touch", "she's lying", "he's lying", "they're lying",
    "i want a lawyer", "i want my lawyer", "i'm not saying anything",
    "i plead the fifth", "fifth amendment",
}

# Interpreter indicators - translation phrases
INTERPRETER_INDICATORS = {
    "he says", "she says", "they say", "he is saying", "she is saying",
    "he wants to know", "she wants to know", "he is asking", "she is asking",
    "can you translate", "translation:", "interpreting:",
    "él dice", "ella dice", "pregunta si", "quiere saber",
}


def detect_speaker_role(
    segments: list[TranscriptSegment],
    speaker_id: str,
) -> SpeakerRole:
    """
    Detect the role of a speaker based on their transcript segments.

    Args:
        segments: All segments from the speaker
        speaker_id: The speaker ID to analyze

    Returns:
        Detected SpeakerRole
    """
    # Filter to just this speaker's segments
    speaker_segments = [s for s in segments if s.speaker == speaker_id]

    if not speaker_segments:
        return SpeakerRole.UNKNOWN

    # Combine all text for analysis
    all_text = " ".join(s.text.lower() for s in speaker_segments)

    # Score each role
    scores = {
        SpeakerRole.OFFICER: 0.0,
        SpeakerRole.VICTIM: 0.0,
        SpeakerRole.WITNESS: 0.0,
        SpeakerRole.SUSPECT: 0.0,
        SpeakerRole.INTERPRETER: 0.0,
    }

    # Check officer indicators
    for indicator in OFFICER_INDICATORS:
        if indicator in all_text:
            scores[SpeakerRole.OFFICER] += 2.0

    # Check victim indicators
    for indicator in VICTIM_INDICATORS:
        if indicator in all_text:
            scores[SpeakerRole.VICTIM] += 2.0

    # Check suspect indicators
    for indicator in SUSPECT_INDICATORS:
        if indicator in all_text:
            scores[SpeakerRole.SUSPECT] += 2.0

    # Check interpreter indicators
    for indicator in INTERPRETER_INDICATORS:
        if indicator in all_text:
            scores[SpeakerRole.INTERPRETER] += 3.0  # Higher weight

    # Position-based heuristics
    first_segment_idx = min(
        i for i, s in enumerate(segments) if s.speaker == speaker_id
    )

    # Officers typically speak first
    if first_segment_idx == 0:
        scores[SpeakerRole.OFFICER] += 1.0

    # Language-based heuristics
    spanish_count = sum(
        1 for s in speaker_segments
        if s.language in (Language.SPANISH, Language.MIXED)
    )
    english_count = len(speaker_segments) - spanish_count

    # Spanish-dominant speakers are more likely victims/witnesses in LEO contexts
    if spanish_count > english_count:
        scores[SpeakerRole.VICTIM] += 0.5
        scores[SpeakerRole.WITNESS] += 0.5

    # Segment count heuristic - officers often have more segments (asking questions)
    if len(speaker_segments) > len(segments) * 0.4:
        scores[SpeakerRole.OFFICER] += 0.5

    # Question patterns - officers ask more questions
    question_count = sum(1 for s in speaker_segments if "?" in s.text)
    statement_count = len(speaker_segments) - question_count

    if question_count > statement_count:
        scores[SpeakerRole.OFFICER] += 1.0
    elif statement_count > question_count * 2:
        # More statements than questions suggests witness/victim
        scores[SpeakerRole.VICTIM] += 0.5
        scores[SpeakerRole.WITNESS] += 0.5

    # Determine winner
    best_role = max(scores, key=lambda r: scores[r])
    best_score = scores[best_role]

    # Require minimum score for assignment
    if best_score < 1.0:
        return SpeakerRole.UNKNOWN

    # Distinguish victim from witness
    if best_role in (SpeakerRole.VICTIM, SpeakerRole.WITNESS):
        # Check for first-person harm language
        harm_patterns = [
            r"\bme\b.*\b(hit|struck|punch|kick|attack|hurt|threaten)",
            r"\b(golpe|peg|atac|amenaz).*\bme\b",
        ]
        is_victim = any(
            re.search(pattern, all_text)
            for pattern in harm_patterns
        )
        if is_victim:
            return SpeakerRole.VICTIM
        return SpeakerRole.WITNESS

    return best_role


def assign_roles_to_transcript(transcript: Transcript) -> Transcript:
    """
    Assign speaker roles to all speakers in a transcript.

    Args:
        transcript: Transcript to process

    Returns:
        Updated transcript with speaker roles assigned
    """
    # Find unique speakers
    speakers = set(s.speaker for s in transcript.segments)

    # Detect role for each speaker
    speaker_roles: dict[str, SpeakerRole] = {}
    for speaker_id in speakers:
        role = detect_speaker_role(transcript.segments, speaker_id)
        speaker_roles[speaker_id] = role

    # Apply roles to segments
    for segment in transcript.segments:
        segment.speaker_role = speaker_roles.get(segment.speaker, SpeakerRole.UNKNOWN)

    # Store in metadata
    transcript.metadata["speaker_roles"] = {
        speaker: role.value for speaker, role in speaker_roles.items()
    }

    return transcript


def get_speakers_by_role(
    transcript: Transcript,
    role: SpeakerRole,
) -> list[str]:
    """
    Get all speaker IDs with a specific role.

    Args:
        transcript: Transcript to search
        role: Role to filter by

    Returns:
        List of speaker IDs
    """
    speakers = set()
    for segment in transcript.segments:
        if segment.speaker_role == role:
            speakers.add(segment.speaker)
    return list(speakers)


def summarize_speaker_roles(transcript: Transcript) -> dict:
    """
    Generate a summary of speaker roles in the transcript.

    Args:
        transcript: Transcript to analyze

    Returns:
        Dict with role summary
    """
    role_counts: dict[SpeakerRole, int] = defaultdict(int)
    role_speakers: dict[SpeakerRole, list[str]] = defaultdict(list)

    seen_speakers: set[str] = set()

    for segment in transcript.segments:
        if segment.speaker not in seen_speakers:
            role = segment.speaker_role or SpeakerRole.UNKNOWN
            role_counts[role] += 1
            role_speakers[role].append(segment.speaker)
            seen_speakers.add(segment.speaker)

    return {
        "counts": {role.value: count for role, count in role_counts.items()},
        "speakers": {role.value: speakers for role, speakers in role_speakers.items()},
    }
