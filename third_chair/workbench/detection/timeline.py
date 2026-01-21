"""Timeline conflict detection for the Evidence Workbench."""

import json
import re
from typing import Optional

import httpx

from ..config import get_workbench_config
from ..database import WorkbenchDB
from ..extraction.prompts import TIMELINE_ANALYSIS_SYSTEM, TIMELINE_CONFLICT_USER
from ..models import (
    ConnectionType,
    ExtractionType,
    Severity,
    SuggestedConnection,
)


class TimelineDetector:
    """Detects timeline conflicts between events."""

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
                "temperature": 0.2,
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

    def analyze_events(
        self,
        events: list[dict],
    ) -> list[dict]:
        """Analyze a list of events for timeline conflicts.

        Args:
            events: List of event dicts with id, content, start_time, evidence_id

        Returns:
            List of conflict dicts with event_a_id, event_b_id, description, severity
        """
        if len(events) < 2:
            return []

        # Build events list for prompt
        events_list = "\n".join(
            f"- ID: {e['id']}\n"
            f"  Time: {e.get('start_time', 'unknown')}s\n"
            f"  Source: {e.get('evidence_id', 'unknown')}\n"
            f"  Event: {e['content']}"
            for e in events
        )

        prompt = TIMELINE_CONFLICT_USER.format(events_list=events_list)
        response_text = self._generate(prompt, TIMELINE_ANALYSIS_SYSTEM)
        parsed = self._parse_json_response(response_text)

        if not parsed or not parsed.get("has_conflicts"):
            return []

        return parsed.get("conflicts", [])


def detect_timeline_conflicts(
    db: WorkbenchDB,
    model: Optional[str] = None,
    progress_callback: Optional[callable] = None,
) -> list[SuggestedConnection]:
    """Detect timeline conflicts between event extractions.

    Args:
        db: WorkbenchDB instance
        model: Optional model override
        progress_callback: Optional callback(current, total) for progress

    Returns:
        List of detected timeline conflict connections
    """
    # Get all event extractions
    events = db.get_extractions(extraction_type=ExtractionType.EVENT)

    if len(events) < 2:
        return []

    # Sort by start_time
    events_sorted = sorted(
        events,
        key=lambda e: e.start_time if e.start_time is not None else float("inf"),
    )

    # Group events by evidence source for cross-reference
    events_by_evidence: dict[str, list] = {}
    for event in events_sorted:
        if event.evidence_id not in events_by_evidence:
            events_by_evidence[event.evidence_id] = []
        events_by_evidence[event.evidence_id].append(event)

    # Only analyze if we have events from multiple sources
    if len(events_by_evidence) < 2:
        return []

    detector = TimelineDetector(model=model)
    connections: list[SuggestedConnection] = []

    # Build event dicts for analysis
    event_dicts = [
        {
            "id": e.id,
            "content": e.content,
            "start_time": e.start_time,
            "end_time": e.end_time,
            "evidence_id": e.evidence_id,
            "speaker": e.speaker,
        }
        for e in events_sorted
    ]

    if progress_callback:
        progress_callback(1, 2)

    # Analyze events (batch for efficiency, but chunk if too many)
    chunk_size = 20
    all_conflicts: list[dict] = []

    for i in range(0, len(event_dicts), chunk_size):
        chunk = event_dicts[i : i + chunk_size]
        if len(chunk) >= 2:
            conflicts = detector.analyze_events(chunk)
            all_conflicts.extend(conflicts)

    if progress_callback:
        progress_callback(2, 2)

    # Create lookup for extraction IDs
    id_to_extraction = {e.id: e for e in events}

    # Convert conflicts to connections
    for conflict in all_conflicts:
        event_a_id = conflict.get("event_a_id")
        event_b_id = conflict.get("event_b_id")

        if not event_a_id or not event_b_id:
            continue

        extraction_a = id_to_extraction.get(event_a_id)
        extraction_b = id_to_extraction.get(event_b_id)

        if not extraction_a or not extraction_b:
            continue

        # Skip conflicts within same evidence
        if extraction_a.evidence_id == extraction_b.evidence_id:
            continue

        severity_str = conflict.get("severity", "moderate")
        try:
            severity = Severity(severity_str.lower())
        except ValueError:
            severity = Severity.MODERATE

        connection = SuggestedConnection.create(
            extraction_a_id=event_a_id,
            extraction_b_id=event_b_id,
            connection_type=ConnectionType.TEMPORAL_CONFLICT,
            confidence=0.7,  # Timeline conflicts get moderate confidence by default
            reasoning=conflict.get("description", "Timeline conflict detected"),
            evidence_snippets=[extraction_a.content, extraction_b.content],
            severity=severity,
        )
        connections.append(connection)

    detector.close()
    return connections
