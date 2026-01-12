"""Whisper transcription using faster-whisper."""

from pathlib import Path
from typing import Optional

from ..config.settings import get_settings
from ..models import Language, Transcript, TranscriptSegment


# Lazy-loaded model instance
_model = None


def get_whisper_model():
    """
    Get or create the Whisper model instance.

    Uses singleton pattern to avoid loading model multiple times.
    """
    global _model

    if _model is None:
        from faster_whisper import WhisperModel

        settings = get_settings()
        config = settings.whisper

        _model = WhisperModel(
            config.model_size,
            device=config.device,
            compute_type=config.compute_type,
        )

    return _model


def transcribe_audio(
    audio_path: Path,
    language: Optional[str] = None,
    beam_size: Optional[int] = None,
    vad_filter: Optional[bool] = None,
) -> list[dict]:
    """
    Transcribe an audio file using Whisper.

    Args:
        audio_path: Path to audio file (should be 16kHz mono WAV)
        language: Language code (e.g., "en", "es") or None for auto-detect
        beam_size: Beam size for decoding
        vad_filter: Whether to use VAD filtering

    Returns:
        List of segment dicts with start, end, text, and word info
    """
    settings = get_settings()
    config = settings.whisper

    model = get_whisper_model()

    # Use provided values or fall back to config
    beam_size = beam_size if beam_size is not None else config.beam_size
    vad_filter = vad_filter if vad_filter is not None else config.vad_filter
    language = language if language is not None else config.language

    # Run transcription
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        beam_size=beam_size,
        vad_filter=vad_filter,
        word_timestamps=True,
    )

    # Convert to list of dicts
    result = []
    for segment in segments:
        seg_dict = {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
            "avg_logprob": segment.avg_logprob,
            "no_speech_prob": segment.no_speech_prob,
        }

        # Include word-level timestamps if available
        if segment.words:
            seg_dict["words"] = [
                {
                    "word": w.word,
                    "start": w.start,
                    "end": w.end,
                    "probability": w.probability,
                }
                for w in segment.words
            ]

        result.append(seg_dict)

    return result


def transcribe_to_transcript(
    audio_path: Path,
    evidence_id: str,
    language: Optional[str] = None,
) -> Transcript:
    """
    Transcribe audio and return a Transcript object.

    Args:
        audio_path: Path to audio file
        evidence_id: Evidence ID for the transcript
        language: Language hint for transcription

    Returns:
        Populated Transcript object
    """
    # Run transcription
    raw_segments = transcribe_audio(audio_path, language=language)

    # Convert to TranscriptSegment objects
    segments = []
    for seg in raw_segments:
        # Determine confidence level from log probability
        avg_logprob = seg.get("avg_logprob", 0)
        if avg_logprob > -0.5:
            confidence = 0.9
        elif avg_logprob > -1.0:
            confidence = 0.7
        else:
            confidence = 0.5

        transcript_seg = TranscriptSegment(
            start_time=seg["start"],
            end_time=seg["end"],
            speaker="SPEAKER_1",  # Will be updated by diarization
            text=seg["text"],
            language=Language.ENGLISH if language == "en" else Language.UNKNOWN,
            confidence=confidence,
        )

        segments.append(transcript_seg)

    # Create transcript
    transcript = Transcript(
        evidence_id=evidence_id,
        segments=segments,
    )

    return transcript


def detect_language(audio_path: Path, duration_limit: float = 30.0) -> tuple[str, float]:
    """
    Detect the primary language of an audio file.

    Args:
        audio_path: Path to audio file
        duration_limit: Maximum seconds to analyze

    Returns:
        Tuple of (language_code, confidence)
    """
    model = get_whisper_model()

    # Run with language detection
    _, info = model.transcribe(
        str(audio_path),
        language=None,  # Auto-detect
        beam_size=1,  # Fast
        vad_filter=True,
    )

    return info.language, info.language_probability


def unload_model():
    """Unload the Whisper model to free memory."""
    global _model
    if _model is not None:
        del _model
        _model = None
        # Force garbage collection
        import gc
        gc.collect()
