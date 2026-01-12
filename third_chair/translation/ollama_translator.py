"""Translation using Ollama local LLM."""

import time
from typing import Optional

import httpx

from ..config.settings import get_settings
from ..models import Language, ReviewFlag, Transcript, TranscriptSegment


def check_ollama_available() -> bool:
    """
    Check if Ollama is running and accessible.

    Returns:
        True if Ollama is available, False otherwise
    """
    settings = get_settings()

    try:
        response = httpx.get(f"{settings.ollama.base_url}/api/version", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False


def ensure_model_loaded(model_name: Optional[str] = None) -> bool:
    """
    Ensure the translation model is loaded in Ollama.

    This "warms up" the model to avoid cold-start delays.

    Args:
        model_name: Model to load (default from settings)

    Returns:
        True if model is ready, False otherwise
    """
    settings = get_settings()
    model = model_name or settings.ollama.translation_model

    try:
        # Send a minimal request to load the model
        response = httpx.post(
            f"{settings.ollama.base_url}/api/generate",
            json={
                "model": model,
                "prompt": "Hello",
                "stream": False,
                "options": {"num_predict": 1},
            },
            timeout=120.0,  # Long timeout for model loading
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Warning: Could not load model {model}: {e}")
        return False


def translate_text(
    text: str,
    source_lang: str = "Spanish",
    target_lang: str = "English",
    context: Optional[str] = None,
    model_name: Optional[str] = None,
) -> str:
    """
    Translate text using Ollama.

    Args:
        text: Text to translate
        source_lang: Source language name
        target_lang: Target language name
        context: Optional context for better translation
        model_name: Model to use (default from settings)

    Returns:
        Translated text
    """
    settings = get_settings()
    model = model_name or settings.ollama.translation_model

    # Build prompt
    prompt = _build_translation_prompt(text, source_lang, target_lang, context)

    # Make request
    try:
        response = httpx.post(
            f"{settings.ollama.base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Low temperature for consistent translations
                    "num_predict": 512,
                },
            },
            timeout=settings.ollama.timeout,
        )

        if response.status_code != 200:
            raise RuntimeError(f"Ollama returned status {response.status_code}")

        result = response.json()
        translation = result.get("response", "").strip()

        # Clean up response
        translation = _clean_translation(translation)

        return translation

    except httpx.TimeoutException:
        raise RuntimeError("Translation timed out. Ollama may be overloaded.")
    except Exception as e:
        raise RuntimeError(f"Translation failed: {e}")


def _build_translation_prompt(
    text: str,
    source_lang: str,
    target_lang: str,
    context: Optional[str],
) -> str:
    """Build the translation prompt for Ollama."""
    prompt = f"""Translate the following {source_lang} text to {target_lang}.
Provide only the translation, no explanations or notes.

"""

    if context:
        prompt += f"Context: {context}\n\n"

    prompt += f"{source_lang} text: {text}\n\n{target_lang} translation:"

    return prompt


def _clean_translation(text: str) -> str:
    """Clean up translation output from LLM."""
    # Remove common prefixes
    prefixes = [
        "English translation:",
        "Translation:",
        "Here's the translation:",
        "The translation is:",
    ]

    text = text.strip()

    for prefix in prefixes:
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()

    # Remove quotes if wrapped
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]

    return text


def translate_segments(
    transcript: Transcript,
    source_langs: Optional[list[Language]] = None,
    min_words: int = 5,
    show_progress: bool = True,
) -> Transcript:
    """
    Translate segments in a transcript.

    Only translates segments in specified source languages.

    Args:
        transcript: Transcript to translate
        source_langs: Languages to translate (default: Spanish, Mixed)
        min_words: Minimum words to translate (shorter flagged for review)
        show_progress: Whether to show progress

    Returns:
        Updated transcript with translations
    """
    if source_langs is None:
        source_langs = [Language.SPANISH, Language.MIXED]

    # Check Ollama availability
    if not check_ollama_available():
        print("Warning: Ollama not available. Skipping translation.")
        return transcript

    # Ensure model is loaded
    if show_progress:
        print("Loading translation model...")
    ensure_model_loaded()

    # Get previous segment for context
    prev_segment: Optional[TranscriptSegment] = None
    translated_count = 0

    for i, segment in enumerate(transcript.segments):
        # Skip if not in target languages
        if segment.language not in source_langs:
            prev_segment = segment
            continue

        # Check word count
        word_count = len(segment.text.split())
        if word_count < min_words:
            # Flag for review but still translate
            if ReviewFlag.SHORT_PHRASE not in segment.review_flags:
                segment.review_flags.append(ReviewFlag.SHORT_PHRASE)

        # Build context from previous segment
        context = None
        if prev_segment and prev_segment.language == Language.ENGLISH:
            context = f"Previous speaker said: {prev_segment.text[:100]}"

        # Translate
        try:
            if show_progress and translated_count % 10 == 0:
                print(f"  Translating segment {i+1}/{len(transcript.segments)}...")

            translation = translate_text(
                text=segment.text,
                source_lang="Spanish" if segment.language == Language.SPANISH else "Mixed Spanish/English",
                target_lang="English",
                context=context,
            )

            segment.translation = translation
            translated_count += 1

            # Rate limiting - avoid overwhelming Ollama
            time.sleep(0.1)

        except Exception as e:
            print(f"  Warning: Translation failed for segment {i}: {e}")
            if ReviewFlag.TRANSLATION_UNCERTAIN not in segment.review_flags:
                segment.review_flags.append(ReviewFlag.TRANSLATION_UNCERTAIN)

        prev_segment = segment

    if show_progress:
        print(f"  Translated {translated_count} segments.")

    return transcript


def unload_model(model_name: Optional[str] = None):
    """
    Unload a model from Ollama to free memory.

    Args:
        model_name: Model to unload (default from settings)
    """
    settings = get_settings()
    model = model_name or settings.ollama.translation_model

    try:
        httpx.post(
            f"{settings.ollama.base_url}/api/generate",
            json={
                "model": model,
                "keep_alive": 0,  # Unload immediately
            },
            timeout=10.0,
        )
    except Exception:
        pass  # Ignore errors when unloading
