"""Translation module for language detection and translation."""

from ..models import Case, Language, Transcript
from .language_detector import (
    detect_code_switching,
    detect_language,
    detect_languages_in_transcript,
)
from .ollama_translator import (
    check_ollama_available,
    ensure_model_loaded,
    translate_segments,
    translate_text,
    unload_model,
)
from .phrase_extractor import (
    extract_spanish_phrases,
    process_transcript_phrases,
)


def translate_transcript(
    transcript: Transcript,
    detect_language_first: bool = True,
    extract_phrases: bool = True,
    show_progress: bool = True,
) -> Transcript:
    """
    Full translation pipeline for a transcript.

    This performs:
    1. Language detection for each segment
    2. Spanish phrase extraction from mixed segments
    3. Translation of Spanish/Mixed segments

    Args:
        transcript: Transcript to translate
        detect_language_first: Whether to run language detection
        extract_phrases: Whether to extract phrases from mixed segments
        show_progress: Whether to show progress

    Returns:
        Updated transcript with translations
    """
    if show_progress:
        print(f"Translating transcript {transcript.evidence_id}...")

    # Step 1: Detect languages
    if detect_language_first:
        if show_progress:
            print("  Detecting languages...")
        transcript = detect_languages_in_transcript(transcript)

        # Report language distribution
        if show_progress:
            dist = transcript.language_distribution
            print(f"    Distribution: {dist}")

    # Step 2: Translate segments
    if show_progress:
        print("  Translating segments...")
    transcript = translate_segments(
        transcript,
        source_langs=[Language.SPANISH, Language.MIXED],
        show_progress=show_progress,
    )

    # Step 3: Extract and translate phrases from mixed segments
    if extract_phrases:
        if show_progress:
            print("  Processing mixed-language phrases...")
        transcript = process_transcript_phrases(
            transcript,
            translate=True,
            show_progress=show_progress,
        )

    return transcript


def translate_case(
    case: Case,
    show_progress: bool = True,
) -> Case:
    """
    Translate all transcripts in a case.

    Args:
        case: Case with evidence items
        show_progress: Whether to show progress

    Returns:
        Updated case
    """
    # Check Ollama availability first
    if not check_ollama_available():
        print("Warning: Ollama not available. Skipping translation.")
        return case

    transcribed_items = [
        e for e in case.evidence_items
        if e.transcript is not None
    ]

    if not transcribed_items:
        if show_progress:
            print("No transcripts to translate.")
        return case

    if show_progress:
        print(f"Translating {len(transcribed_items)} transcripts...")

    for i, evidence in enumerate(transcribed_items):
        if show_progress:
            print(f"\n[{i+1}/{len(transcribed_items)}] {evidence.filename}")

        evidence.transcript = translate_transcript(
            evidence.transcript,
            show_progress=show_progress,
        )

    # Save updated case
    case.save()

    return case


__all__ = [
    # Main functions
    "translate_transcript",
    "translate_case",
    # Language detection
    "detect_language",
    "detect_code_switching",
    "detect_languages_in_transcript",
    # Translation
    "check_ollama_available",
    "ensure_model_loaded",
    "translate_text",
    "translate_segments",
    "unload_model",
    # Phrase extraction
    "extract_spanish_phrases",
    "process_transcript_phrases",
]
