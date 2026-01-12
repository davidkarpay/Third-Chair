"""Spanish phrase extraction from mixed-language segments."""

import re
from pathlib import Path
from typing import Optional

from ..config.settings import get_settings
from ..models import Language, ReviewFlag, Transcript, TranscriptSegment
from .language_detector import SPANISH_INDICATORS, detect_language


# Common English function words to filter out
ENGLISH_FUNCTION_WORDS = {
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
    "my", "your", "his", "its", "our", "their", "mine", "yours", "ours", "theirs",
    "a", "an", "the", "this", "that", "these", "those",
    "is", "am", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "can", "may", "might", "must",
    "and", "or", "but", "so", "if", "when", "where", "what", "why", "how",
    "to", "of", "in", "on", "at", "for", "with", "by", "from", "up", "down",
    "yes", "no", "not", "ok", "okay",
}


def load_place_names() -> set[str]:
    """
    Load place names to preserve (not translate).

    Loads from places.json config file if available.
    """
    settings = get_settings()

    place_names = {
        # Default Palm Beach County places
        "palm beach", "west palm beach", "lake worth", "boynton beach",
        "delray beach", "boca raton", "jupiter", "wellington",
        "royal palm beach", "greenacres", "lantana", "riviera beach",
        # Common street names
        "military trail", "okeechobee", "southern", "congress",
        "jog road", "haverhill", "forest hill", "belvedere",
    }

    # Load from config file if available
    if settings.places_file and settings.places_file.exists():
        try:
            import json
            with open(settings.places_file) as f:
                data = json.load(f)
                if isinstance(data, dict) and "places" in data:
                    place_names.update(p.lower() for p in data["places"])
                elif isinstance(data, list):
                    place_names.update(p.lower() for p in data)
        except Exception:
            pass

    return place_names


def extract_spanish_phrases(text: str) -> list[dict]:
    """
    Extract Spanish phrases from mixed-language text.

    Uses a multi-stage approach:
    1. Split by sentence boundaries
    2. Split by clause boundaries
    3. Identify Spanish runs using indicator words

    Args:
        text: Mixed-language text

    Returns:
        List of dicts with phrase info
    """
    if not text:
        return []

    place_names = load_place_names()
    phrases = []

    # Stage 1: Split by sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)

    for sentence in sentences:
        # Stage 2: Split by clauses
        clauses = re.split(r"(?:,|;|\band\b|\bor\b|\bbut\b)", sentence)

        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue

            # Stage 3: Find Spanish runs
            spanish_runs = _find_spanish_runs(clause, place_names)
            phrases.extend(spanish_runs)

    return phrases


def _find_spanish_runs(text: str, place_names: set[str]) -> list[dict]:
    """
    Find runs of Spanish words within a text segment.

    Args:
        text: Text to analyze
        place_names: Set of place names to preserve

    Returns:
        List of extracted phrase dicts
    """
    words = text.split()
    if not words:
        return []

    phrases = []
    current_run = []
    current_start = 0

    for i, word in enumerate(words):
        word_lower = word.lower().strip(".,!?;:")

        # Check if this is a Spanish word
        is_spanish = word_lower in SPANISH_INDICATORS

        # Also check using full detection for longer words
        if not is_spanish and len(word_lower) > 3:
            lang, conf = detect_language(word_lower)
            is_spanish = lang == Language.SPANISH and conf > 0.6

        # Skip English function words
        if word_lower in ENGLISH_FUNCTION_WORDS:
            # Don't break a run for function words
            if current_run:
                current_run.append(word)
            continue

        # Check for place names (preserve, don't include in Spanish)
        is_place = any(place in text.lower() for place in place_names)

        if is_spanish and not is_place:
            if not current_run:
                current_start = i
            current_run.append(word)
        elif current_run:
            # End of Spanish run
            if len(current_run) >= 2:  # Minimum 2 words
                phrase_text = " ".join(current_run)
                phrases.append({
                    "text": phrase_text,
                    "start_word": current_start,
                    "end_word": i - 1,
                    "word_count": len(current_run),
                })
            current_run = []

    # Handle final run
    if current_run and len(current_run) >= 2:
        phrase_text = " ".join(current_run)
        phrases.append({
            "text": phrase_text,
            "start_word": current_start,
            "end_word": len(words) - 1,
            "word_count": len(current_run),
        })

    return phrases


def extract_and_translate_phrases(
    segment: TranscriptSegment,
    translator_func: Optional[callable] = None,
) -> TranscriptSegment:
    """
    Extract Spanish phrases from a segment and translate them.

    Args:
        segment: Segment to process
        translator_func: Optional translation function

    Returns:
        Updated segment with extracted phrases
    """
    if segment.language not in (Language.MIXED, Language.UNKNOWN):
        return segment

    phrases = extract_spanish_phrases(segment.text)

    if not phrases:
        return segment

    # Translate each phrase if translator provided
    if translator_func:
        for phrase in phrases:
            try:
                translation = translator_func(phrase["text"])
                phrase["translation"] = translation
            except Exception:
                phrase["translation"] = None

    segment.extracted_phrases = phrases

    # If phrases found, mark as code-switched
    if phrases and ReviewFlag.CODE_SWITCHED not in segment.review_flags:
        segment.review_flags.append(ReviewFlag.CODE_SWITCHED)

    return segment


def process_transcript_phrases(
    transcript: Transcript,
    translate: bool = True,
    show_progress: bool = True,
) -> Transcript:
    """
    Extract and optionally translate Spanish phrases from all segments.

    Args:
        transcript: Transcript to process
        translate: Whether to translate extracted phrases
        show_progress: Whether to show progress

    Returns:
        Updated transcript
    """
    translator_func = None

    if translate:
        from .ollama_translator import translate_text

        def _translate(text: str) -> str:
            return translate_text(text, source_lang="Spanish", target_lang="English")

        translator_func = _translate

    for i, segment in enumerate(transcript.segments):
        if segment.language in (Language.MIXED, Language.UNKNOWN):
            if show_progress and i % 20 == 0:
                print(f"  Processing phrases in segment {i+1}/{len(transcript.segments)}...")

            extract_and_translate_phrases(segment, translator_func)

    return transcript
