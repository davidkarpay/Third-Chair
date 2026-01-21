"""LLM-based fact extraction from transcripts."""

import json
import re
from pathlib import Path
from typing import Optional

import httpx

from ..config import get_workbench_config
from ..database import WorkbenchDB, get_workbench_db
from ..models import Extraction, ExtractionType
from .prompts import TRANSCRIPT_EXTRACTION_SYSTEM, TRANSCRIPT_EXTRACTION_USER


class Extractor:
    """Extracts structured facts from transcript segments using LLM."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 180,
    ):
        """Initialize the extractor.

        Args:
            base_url: Ollama API URL (default from config)
            model: Model to use (default from config)
            timeout: Request timeout in seconds
        """
        config = get_workbench_config()

        self.base_url = base_url or config.ollama_base_url
        self.model = model or config.extraction_model
        self.temperature = config.extraction_temperature
        self.max_tokens = config.extraction_max_tokens
        self.timeout = timeout

        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def is_available(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            response = self._client.get(f"{self.base_url}/api/version")
            return response.status_code == 200
        except Exception:
            return False

    def _generate(self, prompt: str, system: str) -> Optional[str]:
        """Generate a response from Ollama."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        try:
            response = self._client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code != 200:
                return None

            data = response.json()
            return data.get("response", "").strip()

        except Exception:
            return None

    def _parse_json_response(self, text: str) -> Optional[dict]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        if not text:
            return None

        # Try to extract JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_match:
            text = json_match.group(1).strip()

        # Try to find JSON object
        try:
            # Find the first { and last }
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

        return None

    def extract_from_segment(
        self,
        evidence_id: str,
        segment_index: int,
        text: str,
        speaker: str,
        speaker_role: Optional[str] = None,
        start_time: float = 0.0,
        end_time: float = 0.0,
        translation: Optional[str] = None,
    ) -> list[Extraction]:
        """Extract facts from a single transcript segment.

        Args:
            evidence_id: ID of the evidence item
            segment_index: Index of the segment in the transcript
            text: The segment text
            speaker: Speaker identifier
            speaker_role: Role of the speaker (Officer, Victim, etc.)
            start_time: Start time in seconds
            end_time: End time in seconds
            translation: Optional translation if text is non-English

        Returns:
            List of extracted facts
        """
        # Build translation section if available
        translation_section = ""
        if translation:
            translation_section = f"Translation (English):\n{translation}"

        # Format the prompt
        prompt = TRANSCRIPT_EXTRACTION_USER.format(
            speaker=speaker,
            speaker_role=speaker_role or "Unknown",
            start_time=start_time,
            end_time=end_time,
            text=text,
            translation_section=translation_section,
        )

        # Generate extraction
        response_text = self._generate(prompt, TRANSCRIPT_EXTRACTION_SYSTEM)
        parsed = self._parse_json_response(response_text)

        if not parsed:
            return []

        extractions: list[Extraction] = []

        # Process statements
        for item in parsed.get("statements", []):
            extractions.append(
                Extraction.create(
                    evidence_id=evidence_id,
                    extraction_type=ExtractionType.STATEMENT,
                    content=item.get("content", ""),
                    segment_index=segment_index,
                    speaker=item.get("speaker", speaker),
                    speaker_role=speaker_role,
                    start_time=start_time,
                    end_time=end_time,
                    confidence=item.get("confidence", 0.8),
                )
            )

        # Process events
        for item in parsed.get("events", []):
            extractions.append(
                Extraction.create(
                    evidence_id=evidence_id,
                    extraction_type=ExtractionType.EVENT,
                    content=item.get("content", ""),
                    segment_index=segment_index,
                    speaker=speaker,
                    speaker_role=speaker_role,
                    start_time=start_time,
                    end_time=end_time,
                    confidence=item.get("confidence", 0.8),
                )
            )

        # Process entity mentions
        for item in parsed.get("entity_mentions", []):
            content = item.get("content", "")
            entity_type = item.get("entity_type", "")
            if entity_type:
                content = f"[{entity_type}] {content}"

            extractions.append(
                Extraction.create(
                    evidence_id=evidence_id,
                    extraction_type=ExtractionType.ENTITY_MENTION,
                    content=content,
                    segment_index=segment_index,
                    speaker=speaker,
                    speaker_role=speaker_role,
                    start_time=start_time,
                    end_time=end_time,
                    confidence=item.get("confidence", 0.8),
                )
            )

        # Process actions
        for item in parsed.get("actions", []):
            extractions.append(
                Extraction.create(
                    evidence_id=evidence_id,
                    extraction_type=ExtractionType.ACTION,
                    content=item.get("content", ""),
                    segment_index=segment_index,
                    speaker=item.get("actor", speaker),
                    speaker_role=speaker_role,
                    start_time=start_time,
                    end_time=end_time,
                    confidence=item.get("confidence", 0.8),
                )
            )

        return extractions

    def extract_from_transcript(
        self,
        evidence_id: str,
        segments: list[dict],
        progress_callback: Optional[callable] = None,
    ) -> list[Extraction]:
        """Extract facts from all segments of a transcript.

        Args:
            evidence_id: ID of the evidence item
            segments: List of segment dictionaries with text, speaker, etc.
            progress_callback: Optional callback(current, total) for progress

        Returns:
            List of all extracted facts
        """
        all_extractions: list[Extraction] = []
        total = len(segments)

        for idx, segment in enumerate(segments):
            if progress_callback:
                progress_callback(idx + 1, total)

            extractions = self.extract_from_segment(
                evidence_id=evidence_id,
                segment_index=idx,
                text=segment.get("text", ""),
                speaker=segment.get("speaker", "UNKNOWN"),
                speaker_role=segment.get("speaker_role"),
                start_time=segment.get("start_time", 0.0),
                end_time=segment.get("end_time", 0.0),
                translation=segment.get("translation"),
            )

            all_extractions.extend(extractions)

        return all_extractions


def extract_from_case(
    case_dir: Path,
    model: Optional[str] = None,
    show_progress: bool = True,
) -> int:
    """Extract facts from all evidence items in a case.

    Args:
        case_dir: Path to the case directory
        model: Optional model override
        show_progress: Whether to show progress output

    Returns:
        Number of extractions created
    """
    # Import Case model lazily
    from ...models.case import Case

    # Load case
    case_json = case_dir / "case.json"
    if not case_json.exists():
        raise FileNotFoundError(f"Case file not found: {case_json}")

    case = Case.load(case_json)

    # Initialize database
    db = get_workbench_db(case_dir)
    if not db.is_initialized():
        db.create_schema()

    # Create extractor
    extractor = Extractor(model=model)

    if not extractor.is_available():
        raise RuntimeError("Ollama is not available. Please ensure it is running.")

    total_extractions = 0

    # Track progress with rich if available
    if show_progress:
        try:
            from rich.console import Console
            from rich.progress import Progress

            console = Console()
        except ImportError:
            console = None
    else:
        console = None

    # Process each evidence item with transcript
    items_with_transcripts = [
        item for item in case.evidence_items if item.transcript and item.transcript.segments
    ]

    if console:
        console.print(f"Found {len(items_with_transcripts)} items with transcripts")

    for item in items_with_transcripts:
        if console:
            console.print(f"  Processing: {item.filename}")

        # Delete existing extractions for this evidence
        db.delete_extractions_for_evidence(item.id)

        # Convert segments to dicts
        segments = [
            {
                "text": seg.text,
                "speaker": seg.speaker,
                "speaker_role": seg.speaker_role.value if seg.speaker_role else None,
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "translation": seg.translation,
            }
            for seg in item.transcript.segments
        ]

        # Extract facts
        extractions = extractor.extract_from_transcript(
            evidence_id=item.id,
            segments=segments,
        )

        # Store in database
        if extractions:
            db.add_extractions_batch(extractions)
            total_extractions += len(extractions)

        if console:
            console.print(f"    Extracted {len(extractions)} facts")

    extractor.close()
    db.close()

    return total_extractions
