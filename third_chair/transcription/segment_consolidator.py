"""Segment consolidation for cleaner transcripts."""

from ..config.settings import get_settings
from ..models import Transcript, TranscriptSegment


def consolidate_segments(
    transcript: Transcript,
    max_gap: float | None = None,
    max_length: int | None = None,
) -> Transcript:
    """
    Consolidate consecutive same-speaker segments.

    Axon transcripts often have fragmented segments (2-3 second chunks).
    This merges consecutive segments from the same speaker if:
    - The gap between them is less than max_gap seconds
    - The combined text length is less than max_length characters

    Args:
        transcript: Transcript to consolidate
        max_gap: Maximum gap in seconds to merge (default from settings)
        max_length: Maximum combined text length (default from settings)

    Returns:
        New Transcript with consolidated segments
    """
    settings = get_settings()
    config = settings.output

    max_gap = max_gap if max_gap is not None else config.max_segment_gap
    max_length = max_length if max_length is not None else config.max_segment_length

    if not transcript.segments:
        return transcript

    consolidated: list[TranscriptSegment] = []
    current: TranscriptSegment | None = None

    for segment in transcript.segments:
        if current is None:
            # Start a new segment
            current = _copy_segment(segment)
            continue

        # Check if we can merge
        gap = segment.start_time - current.end_time
        combined_length = len(current.text) + len(segment.text) + 1

        can_merge = (
            segment.speaker == current.speaker
            and gap <= max_gap
            and combined_length <= max_length
        )

        if can_merge:
            # Merge segments
            current = _merge_segments(current, segment)
        else:
            # Save current and start new
            consolidated.append(current)
            current = _copy_segment(segment)

    # Don't forget the last segment
    if current is not None:
        consolidated.append(current)

    # Create new transcript with consolidated segments
    return Transcript(
        evidence_id=transcript.evidence_id,
        segments=consolidated,
        speakers=transcript.speakers.copy(),
        language_distribution=transcript.language_distribution.copy(),
        key_statements=transcript.key_statements.copy(),
        metadata=transcript.metadata.copy(),
    )


def _copy_segment(segment: TranscriptSegment) -> TranscriptSegment:
    """Create a copy of a segment."""
    return TranscriptSegment(
        start_time=segment.start_time,
        end_time=segment.end_time,
        speaker=segment.speaker,
        text=segment.text,
        speaker_role=segment.speaker_role,
        language=segment.language,
        translation=segment.translation,
        confidence=segment.confidence,
        review_flags=segment.review_flags.copy(),
        extracted_phrases=segment.extracted_phrases.copy(),
    )


def _merge_segments(seg1: TranscriptSegment, seg2: TranscriptSegment) -> TranscriptSegment:
    """
    Merge two consecutive segments.

    The merged segment takes:
    - start_time from seg1
    - end_time from seg2
    - Combined text with space
    - Lower of the two confidence values
    - Union of review flags
    """
    merged_text = f"{seg1.text} {seg2.text}"

    # Merge translations if both present
    merged_translation = None
    if seg1.translation and seg2.translation:
        merged_translation = f"{seg1.translation} {seg2.translation}"
    elif seg1.translation:
        merged_translation = seg1.translation
    elif seg2.translation:
        merged_translation = seg2.translation

    # Merge review flags (union)
    merged_flags = list(set(seg1.review_flags + seg2.review_flags))

    # Merge extracted phrases
    merged_phrases = seg1.extracted_phrases + seg2.extracted_phrases

    return TranscriptSegment(
        start_time=seg1.start_time,
        end_time=seg2.end_time,
        speaker=seg1.speaker,
        text=merged_text,
        speaker_role=seg1.speaker_role,  # Keep first segment's role
        language=seg1.language if seg1.language == seg2.language else seg1.language,
        translation=merged_translation,
        confidence=min(seg1.confidence, seg2.confidence),
        review_flags=merged_flags,
        extracted_phrases=merged_phrases,
    )


def split_long_segments(
    transcript: Transcript,
    max_duration: float = 30.0,
) -> Transcript:
    """
    Split segments that are too long.

    Some transcription results may have very long segments.
    This splits them at natural boundaries (sentence endings).

    Args:
        transcript: Transcript to process
        max_duration: Maximum segment duration in seconds

    Returns:
        Transcript with split segments
    """
    import re

    split_segments: list[TranscriptSegment] = []

    for segment in transcript.segments:
        duration = segment.end_time - segment.start_time

        if duration <= max_duration:
            split_segments.append(segment)
            continue

        # Need to split - find sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", segment.text)

        if len(sentences) <= 1:
            # Can't split, keep as is
            split_segments.append(segment)
            continue

        # Distribute time proportionally by character count
        total_chars = sum(len(s) for s in sentences)
        current_time = segment.start_time

        for sentence in sentences:
            if not sentence.strip():
                continue

            # Calculate proportional duration
            char_ratio = len(sentence) / total_chars
            sentence_duration = duration * char_ratio

            new_segment = TranscriptSegment(
                start_time=current_time,
                end_time=current_time + sentence_duration,
                speaker=segment.speaker,
                text=sentence.strip(),
                speaker_role=segment.speaker_role,
                language=segment.language,
                confidence=segment.confidence,
                review_flags=segment.review_flags.copy(),
            )

            split_segments.append(new_segment)
            current_time += sentence_duration

    return Transcript(
        evidence_id=transcript.evidence_id,
        segments=split_segments,
        speakers=transcript.speakers.copy(),
        language_distribution=transcript.language_distribution.copy(),
        key_statements=transcript.key_statements.copy(),
        metadata=transcript.metadata.copy(),
    )
