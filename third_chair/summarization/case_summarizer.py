"""Case-level summarization.

Generates executive summaries for entire cases, including:
- Overall case narrative
- Key evidence highlights
- Critical statements across all transcripts
- Witness involvement summary
"""

from dataclasses import dataclass, field
from typing import Optional

from ..models import Case, EvidenceItem, Witness
from .ollama_client import get_ollama_client, OllamaResponse
from .timeline_builder import build_timeline, format_timeline, TimelineEntry
from .transcript_summarizer import TranscriptSummary, summarize_transcript


@dataclass
class CaseSummary:
    """Complete summary of a case."""

    case_id: str
    executive_summary: str = ""
    evidence_count: int = 0
    video_count: int = 0
    document_count: int = 0
    witness_count: int = 0
    timeline_entries: list[TimelineEntry] = field(default_factory=list)
    transcript_summaries: list[TranscriptSummary] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    threats_identified: int = 0
    violence_indicators: int = 0
    items_needing_review: list[str] = field(default_factory=list)
    spanish_content_percentage: float = 0.0


def summarize_case(
    case: Case,
    include_transcripts: bool = True,
    max_summary_length: int = 500,
) -> CaseSummary:
    """
    Generate a comprehensive summary of a case.

    Args:
        case: Case to summarize
        include_transcripts: Whether to summarize individual transcripts
        max_summary_length: Max words for executive summary

    Returns:
        CaseSummary with all summary data
    """
    client = get_ollama_client()

    result = CaseSummary(
        case_id=case.case_id,
        evidence_count=len(case.evidence_items),
    )

    # Count evidence types
    for evidence in case.evidence_items:
        if evidence.file_type.value in ("video", "audio"):
            result.video_count += 1
        elif evidence.file_type.value in ("document", "image"):
            result.document_count += 1

    # Count witnesses
    result.witness_count = len(case.witnesses)

    # Build timeline
    result.timeline_entries = build_timeline(case)

    # Summarize transcripts
    if include_transcripts:
        result.transcript_summaries = _summarize_all_transcripts(case)

        # Aggregate stats from transcript summaries
        for ts in result.transcript_summaries:
            result.threats_identified += ts.threat_count
            result.violence_indicators += ts.violence_count

        # Calculate Spanish content percentage
        if result.transcript_summaries:
            total_spanish = sum(ts.spanish_percentage for ts in result.transcript_summaries)
            result.spanish_content_percentage = total_spanish / len(result.transcript_summaries)

    # Identify items needing review
    result.items_needing_review = _identify_review_items(case)

    # Generate executive summary
    summary_text = _build_summary_input(case, result)
    response = client.summarize(
        text=summary_text,
        max_length=max_summary_length,
        context=f"Legal case {case.case_id} with {result.evidence_count} evidence items",
    )

    if response.success:
        result.executive_summary = response.text

    # Extract key findings
    key_findings_response = client.extract_key_points(
        text=summary_text,
        num_points=7,
    )

    if key_findings_response.success:
        result.key_findings = _parse_findings(key_findings_response.text)

    return result


def _summarize_all_transcripts(case: Case) -> list[TranscriptSummary]:
    """Summarize all transcripts in a case."""
    summaries = []

    for evidence in case.evidence_items:
        if evidence.transcript:
            try:
                summary = summarize_transcript(evidence.transcript)
                summaries.append(summary)
            except Exception:
                # Skip failed summaries
                pass

    return summaries


def _identify_review_items(case: Case) -> list[str]:
    """Identify evidence items that need human review."""
    review_items = []

    for evidence in case.evidence_items:
        needs_review = False
        reasons = []

        # Check for processing errors
        if evidence.processing_status.value == "error":
            needs_review = True
            reasons.append("processing error")

        # Check transcript quality
        if evidence.transcript:
            # Low confidence segments
            low_conf_count = sum(
                1 for s in evidence.transcript.segments
                if s.confidence < 0.7
            )
            if low_conf_count > len(evidence.transcript.segments) * 0.2:
                needs_review = True
                reasons.append("low confidence transcription")

            # Many flagged segments
            flagged_count = sum(
                1 for s in evidence.transcript.segments
                if s.review_flags
            )
            if flagged_count > 5:
                needs_review = True
                reasons.append(f"{flagged_count} flagged statements")

        # Check metadata for issues
        if evidence.metadata.get("ocr_confidence", 1.0) < 0.8:
            needs_review = True
            reasons.append("low OCR confidence")

        if needs_review:
            review_items.append(f"{evidence.filename}: {', '.join(reasons)}")

    return review_items


def _build_summary_input(case: Case, partial_summary: CaseSummary) -> str:
    """Build text input for AI summarization."""
    lines = []

    # Case header
    lines.append(f"Case: {case.case_id}")
    if case.court_case:
        lines.append(f"Court Case: {case.court_case}")
    if case.agency:
        lines.append(f"Agency: {case.agency}")
    if case.incident_date:
        lines.append(f"Incident Date: {case.incident_date}")

    lines.append("")

    # Evidence overview
    lines.append(f"Evidence Items: {partial_summary.evidence_count}")
    lines.append(f"  Videos/Audio: {partial_summary.video_count}")
    lines.append(f"  Documents: {partial_summary.document_count}")
    lines.append(f"Witnesses: {partial_summary.witness_count}")

    lines.append("")

    # Include existing summaries
    for evidence in case.evidence_items:
        if evidence.summary:
            lines.append(f"\n--- {evidence.filename} ---")
            lines.append(evidence.summary[:1000])

    # Include transcript summaries
    for ts in partial_summary.transcript_summaries:
        lines.append(f"\n--- Transcript Summary ({ts.evidence_id}) ---")
        lines.append(ts.summary[:500] if ts.summary else "No summary")
        if ts.key_points:
            lines.append("Key points:")
            for point in ts.key_points[:3]:
                lines.append(f"  - {point}")

    # Include timeline highlights
    if partial_summary.timeline_entries:
        lines.append("\n--- Key Timeline Events ---")
        critical_events = [
            e for e in partial_summary.timeline_entries
            if e.importance in ("critical", "high")
        ]
        for event in critical_events[:10]:
            lines.append(f"  {event.timestamp}: {event.description}")

    # Witness information
    if case.witnesses:
        lines.append("\n--- Witnesses ---")
        for witness in list(case.witnesses)[:10]:
            role = witness.role.value if witness.role else "unknown"
            name = witness.name or f"Speaker {witness.id}"
            lines.append(f"  {name} ({role})")

    # Threat and violence indicators
    if partial_summary.threats_identified > 0:
        lines.append(f"\nThreat Keywords Detected: {partial_summary.threats_identified}")
    if partial_summary.violence_indicators > 0:
        lines.append(f"Violence Indicators: {partial_summary.violence_indicators}")

    return "\n".join(lines)


def _parse_findings(text: str) -> list[str]:
    """Parse key findings from AI response."""
    import re

    findings = []
    parts = re.split(r"\d+[.)]\s*", text)

    for part in parts:
        part = part.strip()
        if part and len(part) > 15:
            findings.append(part)

    return findings[:7]


def format_case_summary(summary: CaseSummary) -> str:
    """
    Format a case summary as readable text.

    Args:
        summary: CaseSummary to format

    Returns:
        Formatted text string
    """
    lines = []

    # Header
    lines.append("=" * 60)
    lines.append(f"CASE SUMMARY: {summary.case_id}")
    lines.append("=" * 60)
    lines.append("")

    # Executive summary
    lines.append("EXECUTIVE SUMMARY")
    lines.append("-" * 40)
    lines.append(summary.executive_summary or "No summary available.")
    lines.append("")

    # Statistics
    lines.append("CASE STATISTICS")
    lines.append("-" * 40)
    lines.append(f"Total Evidence Items: {summary.evidence_count}")
    lines.append(f"  Video/Audio Files: {summary.video_count}")
    lines.append(f"  Documents: {summary.document_count}")
    lines.append(f"Witnesses Identified: {summary.witness_count}")
    lines.append(f"Timeline Events: {len(summary.timeline_entries)}")
    lines.append("")

    # Key findings
    if summary.key_findings:
        lines.append("KEY FINDINGS")
        lines.append("-" * 40)
        for i, finding in enumerate(summary.key_findings, 1):
            lines.append(f"{i}. {finding}")
        lines.append("")

    # Alerts
    if summary.threats_identified > 0 or summary.violence_indicators > 0:
        lines.append("ALERTS")
        lines.append("-" * 40)
        if summary.threats_identified > 0:
            lines.append(f"[!] Threat keywords detected: {summary.threats_identified}")
        if summary.violence_indicators > 0:
            lines.append(f"[!] Violence indicators: {summary.violence_indicators}")
        lines.append("")

    # Language note
    if summary.spanish_content_percentage > 5:
        lines.append("LANGUAGE NOTE")
        lines.append("-" * 40)
        lines.append(f"Spanish content detected in {summary.spanish_content_percentage:.1f}% of transcripts")
        lines.append("")

    # Items needing review
    if summary.items_needing_review:
        lines.append("ITEMS REQUIRING REVIEW")
        lines.append("-" * 40)
        for item in summary.items_needing_review:
            lines.append(f"  - {item}")
        lines.append("")

    # Timeline preview
    if summary.timeline_entries:
        lines.append("TIMELINE PREVIEW")
        lines.append("-" * 40)
        timeline_text = format_timeline(summary.timeline_entries[:15])
        lines.append(timeline_text)

    return "\n".join(lines)


def add_summary_to_case(case: Case) -> Case:
    """
    Generate and add summary to a case.

    Args:
        case: Case to update

    Returns:
        Updated case with summary
    """
    summary = summarize_case(case)
    case.summary = summary.executive_summary

    # Store additional summary data in case metadata
    case.metadata = case.metadata or {}
    case.metadata["key_findings"] = summary.key_findings
    case.metadata["threats_identified"] = summary.threats_identified
    case.metadata["violence_indicators"] = summary.violence_indicators
    case.metadata["items_needing_review"] = summary.items_needing_review
    case.metadata["spanish_percentage"] = summary.spanish_content_percentage

    return case
