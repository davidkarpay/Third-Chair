"""Speaker diarization using pyannote.audio."""

from pathlib import Path
from typing import Optional

from ..config.settings import get_settings
from ..models import Transcript, TranscriptSegment


# Lazy-loaded pipeline instance
_pipeline = None


def get_diarization_pipeline():
    """
    Get or create the diarization pipeline instance.

    Requires HF_TOKEN environment variable for pyannote access.
    """
    global _pipeline

    if _pipeline is None:
        settings = get_settings()
        config = settings.diarization

        if not config.hf_token:
            raise ValueError(
                "HuggingFace token required for diarization. "
                "Set HF_TOKEN or HUGGINGFACE_TOKEN environment variable."
            )

        from pyannote.audio import Pipeline

        _pipeline = Pipeline.from_pretrained(
            config.model_name,
            use_auth_token=config.hf_token,
        )

    return _pipeline


def diarize_audio(
    audio_path: Path,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
) -> list[dict]:
    """
    Run speaker diarization on an audio file.

    Args:
        audio_path: Path to audio file (should be 16kHz mono WAV)
        min_speakers: Minimum number of speakers expected
        max_speakers: Maximum number of speakers expected

    Returns:
        List of diarization segments with start, end, speaker
    """
    settings = get_settings()
    config = settings.diarization

    pipeline = get_diarization_pipeline()

    # Build parameters
    params = {}
    if min_speakers is not None or config.min_speakers is not None:
        params["min_speakers"] = min_speakers or config.min_speakers
    if max_speakers is not None or config.max_speakers is not None:
        params["max_speakers"] = max_speakers or config.max_speakers

    # Run diarization
    diarization = pipeline(str(audio_path), **params)

    # Convert to list of segments
    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append({
            "start": turn.start,
            "end": turn.end,
            "speaker": speaker,
        })

    # Normalize speaker labels (SPEAKER_00 -> SPEAKER_1)
    segments = _normalize_speaker_labels(segments)

    return segments


def _normalize_speaker_labels(segments: list[dict]) -> list[dict]:
    """
    Normalize speaker labels to consistent format.

    Converts pyannote labels (SPEAKER_00, SPEAKER_01) to
    our format (SPEAKER_1, SPEAKER_2).
    """
    # Find unique speakers and create mapping
    unique_speakers = sorted(set(s["speaker"] for s in segments))
    speaker_map = {
        old: f"SPEAKER_{i+1}"
        for i, old in enumerate(unique_speakers)
    }

    # Apply mapping
    for segment in segments:
        segment["speaker"] = speaker_map[segment["speaker"]]

    return segments


def assign_speakers_to_transcript(
    transcript: Transcript,
    diarization_segments: list[dict],
    method: str = "midpoint",
) -> Transcript:
    """
    Assign speaker labels from diarization to transcript segments.

    Args:
        transcript: Transcript with segments to update
        diarization_segments: Diarization results
        method: Assignment method ("midpoint" or "overlap")

    Returns:
        Updated transcript with speaker labels
    """
    if not diarization_segments:
        return transcript

    for segment in transcript.segments:
        if method == "midpoint":
            speaker = _assign_by_midpoint(segment, diarization_segments)
        else:
            speaker = _assign_by_overlap(segment, diarization_segments)

        if speaker:
            segment.speaker = speaker

    return transcript


def _assign_by_midpoint(
    segment: TranscriptSegment,
    diarization_segments: list[dict],
) -> Optional[str]:
    """
    Assign speaker based on which diarization segment contains the midpoint.
    """
    midpoint = (segment.start_time + segment.end_time) / 2

    for diar in diarization_segments:
        if diar["start"] <= midpoint <= diar["end"]:
            return diar["speaker"]

    return None


def _assign_by_overlap(
    segment: TranscriptSegment,
    diarization_segments: list[dict],
) -> Optional[str]:
    """
    Assign speaker based on maximum overlap duration.
    """
    best_speaker = None
    best_overlap = 0.0

    for diar in diarization_segments:
        # Calculate overlap
        overlap_start = max(segment.start_time, diar["start"])
        overlap_end = min(segment.end_time, diar["end"])
        overlap = max(0, overlap_end - overlap_start)

        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = diar["speaker"]

    return best_speaker


def get_speaker_statistics(diarization_segments: list[dict]) -> dict:
    """
    Calculate speaking time statistics for each speaker.

    Args:
        diarization_segments: Diarization results

    Returns:
        Dict with speaker stats
    """
    stats = {}

    for segment in diarization_segments:
        speaker = segment["speaker"]
        duration = segment["end"] - segment["start"]

        if speaker not in stats:
            stats[speaker] = {
                "total_time": 0.0,
                "segment_count": 0,
            }

        stats[speaker]["total_time"] += duration
        stats[speaker]["segment_count"] += 1

    # Calculate percentages
    total_time = sum(s["total_time"] for s in stats.values())
    for speaker in stats:
        if total_time > 0:
            stats[speaker]["percentage"] = (stats[speaker]["total_time"] / total_time) * 100
        else:
            stats[speaker]["percentage"] = 0

    return stats


def unload_pipeline():
    """Unload the diarization pipeline to free memory."""
    global _pipeline
    if _pipeline is not None:
        del _pipeline
        _pipeline = None
        import gc
        gc.collect()
