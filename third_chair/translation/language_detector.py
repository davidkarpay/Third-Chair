"""Language detection for transcript segments."""

from typing import Optional

from ..models import Language, ReviewFlag, Transcript, TranscriptSegment


# Spanish indicator words for quick detection
SPANISH_INDICATORS = {
    # Common words
    "el", "la", "los", "las", "un", "una", "de", "del", "en", "que", "y",
    "es", "son", "está", "están", "no", "si", "sí", "como", "por", "para",
    "con", "su", "sus", "mi", "tu", "yo", "tú", "él", "ella", "nosotros",
    "ustedes", "ellos", "ellas", "este", "esta", "estos", "estas",
    # Common verbs
    "tengo", "tiene", "tienes", "vamos", "voy", "vas", "va", "quiero",
    "quiere", "puedo", "puede", "sabe", "sé", "dijo", "dice", "hacer",
    "hago", "hace", "fue", "era", "estaba", "había",
    # Question words
    "qué", "quién", "cómo", "cuándo", "dónde", "por qué", "cuál",
    # Common phrases
    "buenos", "buenas", "días", "noches", "gracias", "señor", "señora",
    "aquí", "allí", "ahora", "después", "antes", "muy", "más", "menos",
}

# English indicator words
ENGLISH_INDICATORS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "can", "may", "might", "must", "shall", "this", "that",
    "these", "those", "i", "you", "he", "she", "it", "we", "they",
    "what", "where", "when", "why", "how", "which", "who",
}

def detect_with_fastlangdetect(text: str, k: int = 2) -> Optional[list]:
    """
    Detect language using fast-langdetect library.

    Args:
        text: Text to analyze
        k: Number of top predictions to return

    Returns:
        List of dicts like [{"lang": "en", "score": 0.99}, ...] or None if unavailable
    """
    try:
        from fast_langdetect import detect
        # fast-langdetect returns list of dicts with lang and score
        results = detect(text.replace("\n", " "), k=k)
        return results
    except ImportError:
        return None
    except Exception:
        return None


def detect_language(text: str) -> tuple[Language, float]:
    """
    Detect the language of a text segment.

    Uses a two-tier approach:
    1. Quick keyword-based detection for obvious cases
    2. fast-langdetect library for ambiguous cases

    Args:
        text: Text to analyze

    Returns:
        Tuple of (Language enum, confidence score)
    """
    if not text or not text.strip():
        return Language.UNKNOWN, 0.0

    # Clean and lowercase
    text_lower = text.lower()
    words = set(text_lower.split())

    # Quick keyword check
    spanish_count = len(words & SPANISH_INDICATORS)
    english_count = len(words & ENGLISH_INDICATORS)
    total_words = len(words)

    if total_words == 0:
        return Language.UNKNOWN, 0.0

    spanish_ratio = spanish_count / total_words
    english_ratio = english_count / total_words

    # High confidence cases
    if spanish_ratio > 0.3 and english_ratio < 0.1:
        return Language.SPANISH, 0.9
    if english_ratio > 0.3 and spanish_ratio < 0.1:
        return Language.ENGLISH, 0.9

    # Mixed language detection
    if spanish_ratio > 0.1 and english_ratio > 0.1:
        return Language.MIXED, 0.7

    # Use fast-langdetect for ambiguous cases
    results = detect_with_fastlangdetect(text, k=2)
    if results:
        primary = results[0]
        primary_lang = primary.get("lang", "")
        primary_score = primary.get("score", 0.0)

        if primary_lang == "en":
            return Language.ENGLISH, float(primary_score)
        elif primary_lang == "es":
            return Language.SPANISH, float(primary_score)

        # Check if both English and Spanish are present
        if len(results) > 1:
            secondary_lang = results[1].get("lang", "")
            if {primary_lang, secondary_lang} == {"en", "es"}:
                return Language.MIXED, float(primary_score)

    # Fallback based on keyword ratios
    if spanish_ratio > english_ratio:
        return Language.SPANISH, max(0.5, spanish_ratio)
    elif english_ratio > spanish_ratio:
        return Language.ENGLISH, max(0.5, english_ratio)

    return Language.UNKNOWN, 0.3


def detect_code_switching(text: str) -> dict:
    """
    Detect code-switching (mixed Spanish/English) in text.

    Args:
        text: Text to analyze

    Returns:
        Dict with detection results
    """
    words = text.lower().split()

    if not words:
        return {
            "is_code_switched": False,
            "spanish_words": [],
            "english_words": [],
            "spanish_ratio": 0.0,
            "english_ratio": 0.0,
        }

    spanish_words = [w for w in words if w in SPANISH_INDICATORS]
    english_words = [w for w in words if w in ENGLISH_INDICATORS]

    spanish_ratio = len(spanish_words) / len(words)
    english_ratio = len(english_words) / len(words)

    # Code-switching: has significant words from both languages
    is_code_switched = (
        len(spanish_words) > 0
        and len(english_words) > 0
        and spanish_ratio >= 0.1
        and english_ratio >= 0.1
    )

    return {
        "is_code_switched": is_code_switched,
        "spanish_words": spanish_words,
        "english_words": english_words,
        "spanish_ratio": spanish_ratio,
        "english_ratio": english_ratio,
    }


def detect_languages_in_transcript(transcript: Transcript) -> Transcript:
    """
    Detect language for each segment in a transcript.

    Updates segments with language and review flags.

    Args:
        transcript: Transcript to process

    Returns:
        Updated transcript
    """
    language_counts: dict[str, int] = {}

    for segment in transcript.segments:
        lang, confidence = detect_language(segment.text)
        segment.language = lang
        segment.confidence = confidence

        # Track distribution
        lang_key = lang.value
        language_counts[lang_key] = language_counts.get(lang_key, 0) + 1

        # Add review flags
        if lang == Language.MIXED:
            if ReviewFlag.CODE_SWITCHED not in segment.review_flags:
                segment.review_flags.append(ReviewFlag.CODE_SWITCHED)

        if confidence < 0.5:
            if ReviewFlag.LOW_CONFIDENCE not in segment.review_flags:
                segment.review_flags.append(ReviewFlag.LOW_CONFIDENCE)

    transcript.language_distribution = language_counts

    return transcript
