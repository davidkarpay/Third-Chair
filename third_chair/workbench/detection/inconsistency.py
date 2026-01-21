"""Inconsistency detection between extractions."""

import json
import re
from typing import Optional

import httpx

from ..config import get_workbench_config
from ..database import WorkbenchDB
from ..extraction.prompts import INCONSISTENCY_ANALYSIS_USER, INCONSISTENCY_FOCUS_SYSTEM
from ..models import (
    ConnectionType,
    Extraction,
    Severity,
    SuggestedConnection,
)


class InconsistencyDetector:
    """Detects inconsistencies between extractions using LLM analysis."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 180,
    ):
        """Initialize the detector.

        Args:
            base_url: Ollama API URL (default from config)
            model: Model to use (default from config)
            timeout: Request timeout in seconds
        """
        config = get_workbench_config()

        self.base_url = base_url or config.ollama_base_url
        self.model = model or config.extraction_model
        self.confidence_threshold = config.inconsistency_confidence_threshold
        self.timeout = timeout

        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def _generate(self, prompt: str, system: str) -> Optional[str]:
        """Generate a response from Ollama."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.2,  # Low temperature for consistency analysis
                "num_predict": 1024,
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
        """Parse JSON from LLM response."""
        if not text:
            return None

        # Try to extract JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_match:
            text = json_match.group(1).strip()

        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

        return None

    def analyze_pair(
        self,
        extraction_a: Extraction,
        extraction_b: Extraction,
    ) -> Optional[SuggestedConnection]:
        """Analyze a pair of extractions for inconsistencies.

        Args:
            extraction_a: First extraction
            extraction_b: Second extraction

        Returns:
            SuggestedConnection if inconsistency found, None otherwise
        """
        # Format the prompt
        prompt = INCONSISTENCY_ANALYSIS_USER.format(
            evidence_a_id=extraction_a.evidence_id,
            speaker_a=extraction_a.speaker or "Unknown",
            time_a=f"{extraction_a.start_time:.1f}s" if extraction_a.start_time else "N/A",
            content_a=extraction_a.content,
            evidence_b_id=extraction_b.evidence_id,
            speaker_b=extraction_b.speaker or "Unknown",
            time_b=f"{extraction_b.start_time:.1f}s" if extraction_b.start_time else "N/A",
            content_b=extraction_b.content,
        )

        response_text = self._generate(prompt, INCONSISTENCY_FOCUS_SYSTEM)
        parsed = self._parse_json_response(response_text)

        if not parsed:
            return None

        relationship = parsed.get("relationship", "unrelated")
        confidence = parsed.get("confidence", 0.0)

        # Only create connection if above threshold and is a meaningful relationship
        if confidence < self.confidence_threshold:
            return None

        if relationship == "inconsistent":
            connection_type = ConnectionType.INCONSISTENT_STATEMENT
        elif relationship == "corroborating":
            connection_type = ConnectionType.CORROBORATES
        else:
            return None  # Skip unrelated pairs

        # Map severity
        severity_str = parsed.get("severity", "minor")
        try:
            severity = Severity(severity_str.lower())
        except ValueError:
            severity = Severity.MINOR

        return SuggestedConnection.create(
            extraction_a_id=extraction_a.id,
            extraction_b_id=extraction_b.id,
            connection_type=connection_type,
            confidence=confidence,
            reasoning=parsed.get("reasoning", ""),
            evidence_snippets=[extraction_a.content, extraction_b.content],
            severity=severity if connection_type == ConnectionType.INCONSISTENT_STATEMENT else None,
        )


def detect_inconsistencies(
    db: WorkbenchDB,
    candidate_pairs: list[tuple[str, str, float]],
    model: Optional[str] = None,
    progress_callback: Optional[callable] = None,
) -> list[SuggestedConnection]:
    """Detect inconsistencies between pairs of extractions.

    Args:
        db: WorkbenchDB instance
        candidate_pairs: List of (extraction_a_id, extraction_b_id, similarity) tuples
        model: Optional model override
        progress_callback: Optional callback(current, total) for progress

    Returns:
        List of detected connections
    """
    detector = InconsistencyDetector(model=model)
    connections: list[SuggestedConnection] = []
    total = len(candidate_pairs)

    for i, (id_a, id_b, _similarity) in enumerate(candidate_pairs):
        if progress_callback:
            progress_callback(i + 1, total)

        extraction_a = db.get_extraction(id_a)
        extraction_b = db.get_extraction(id_b)

        if not extraction_a or not extraction_b:
            continue

        # Skip pairs from the same evidence item
        if extraction_a.evidence_id == extraction_b.evidence_id:
            continue

        connection = detector.analyze_pair(extraction_a, extraction_b)
        if connection:
            connections.append(connection)

    detector.close()
    return connections
