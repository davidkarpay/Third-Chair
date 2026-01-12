"""Transcription module for audio/video processing."""

from pathlib import Path
from typing import Optional

from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config.settings import get_settings
from ..models import Case, EvidenceItem, ProcessingStatus, Transcript
from .diarize import (
    assign_speakers_to_transcript,
    diarize_audio,
    get_speaker_statistics,
    unload_pipeline,
)
from .media_processor import (
    get_media_duration,
    get_media_info,
    has_audio_stream,
    normalize_audio,
)
from .segment_consolidator import consolidate_segments, split_long_segments
from .whisper_transcribe import (
    detect_language,
    transcribe_audio,
    transcribe_to_transcript,
    unload_model,
)


def transcribe_evidence(
    evidence: EvidenceItem,
    enable_diarization: bool = True,
    consolidate: bool = True,
    show_progress: bool = True,
) -> Transcript:
    """
    Transcribe a single evidence item.

    This is the main entry point for transcribing audio/video evidence.

    Args:
        evidence: Evidence item to transcribe
        enable_diarization: Whether to run speaker diarization
        consolidate: Whether to consolidate segments
        show_progress: Whether to show progress indicators

    Returns:
        Populated Transcript object
    """
    settings = get_settings()

    if not evidence.is_transcribable:
        raise ValueError(f"Evidence {evidence.id} is not transcribable")

    evidence.processing_status = ProcessingStatus.PROCESSING

    try:
        # Step 1: Get media duration
        duration = get_media_duration(evidence.file_path)
        if duration:
            evidence.duration_seconds = duration

        # Step 2: Normalize audio
        if show_progress:
            print(f"  Normalizing audio for {evidence.filename}...")

        wav_path = normalize_audio(evidence.file_path)

        # Step 3: Transcribe
        if show_progress:
            print(f"  Transcribing {evidence.filename}...")

        transcript = transcribe_to_transcript(
            audio_path=wav_path,
            evidence_id=evidence.id,
        )

        # Step 4: Diarization (if enabled and token available)
        if enable_diarization and settings.diarization.hf_token:
            if show_progress:
                print(f"  Running speaker diarization...")

            try:
                diar_segments = diarize_audio(wav_path)
                transcript = assign_speakers_to_transcript(
                    transcript,
                    diar_segments,
                    method="overlap",
                )

                # Store speaker stats
                stats = get_speaker_statistics(diar_segments)
                transcript.metadata["speaker_stats"] = stats
            except Exception as e:
                print(f"  Warning: Diarization failed: {e}")

        # Step 5: Consolidate segments
        if consolidate:
            transcript = consolidate_segments(transcript)

        # Step 6: Clean up temp file
        if wav_path.exists():
            wav_path.unlink()

        # Update evidence
        evidence.transcript = transcript
        evidence.processing_status = ProcessingStatus.COMPLETED

        return transcript

    except Exception as e:
        evidence.set_error(str(e))
        raise


def transcribe_case(
    case: Case,
    enable_diarization: bool = True,
    consolidate: bool = True,
    show_progress: bool = True,
) -> Case:
    """
    Transcribe all media files in a case.

    Args:
        case: Case with evidence items
        enable_diarization: Whether to run speaker diarization
        consolidate: Whether to consolidate segments
        show_progress: Whether to show progress indicators

    Returns:
        Updated case with transcripts
    """
    media_items = case.get_media_items()

    if not media_items:
        if show_progress:
            print("No media files to transcribe.")
        return case

    if show_progress:
        print(f"Transcribing {len(media_items)} media files...")

    for i, evidence in enumerate(media_items):
        if show_progress:
            print(f"\n[{i+1}/{len(media_items)}] Processing {evidence.filename}")

        try:
            transcribe_evidence(
                evidence=evidence,
                enable_diarization=enable_diarization,
                consolidate=consolidate,
                show_progress=show_progress,
            )
        except Exception as e:
            print(f"  Error: {e}")
            continue

    # Save updated case
    case.save()

    return case


def cleanup():
    """Unload models to free memory."""
    unload_model()
    unload_pipeline()


__all__ = [
    # Main functions
    "transcribe_evidence",
    "transcribe_case",
    "cleanup",
    # Media processing
    "normalize_audio",
    "get_media_duration",
    "get_media_info",
    "has_audio_stream",
    # Transcription
    "transcribe_audio",
    "transcribe_to_transcript",
    "detect_language",
    # Diarization
    "diarize_audio",
    "assign_speakers_to_transcript",
    "get_speaker_statistics",
    # Consolidation
    "consolidate_segments",
    "split_long_segments",
]
