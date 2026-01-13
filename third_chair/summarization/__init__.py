"""Summarization module for Third Chair.

Provides AI-powered summarization using Ollama:
- Transcript summaries with key statement extraction
- Timeline construction from evidence
- Executive case summaries
"""

from typing import Optional

from ..models import Case, EvidenceItem
from .case_summarizer import (
    CaseSummary,
    add_summary_to_case,
    format_case_summary,
    summarize_case,
)
from .ollama_client import (
    OllamaClient,
    OllamaResponse,
    check_ollama_ready,
    get_ollama_client,
)
from .timeline_builder import (
    TimelineEntry,
    add_timeline_to_case,
    build_timeline,
    format_timeline,
)
from .transcript_summarizer import (
    TranscriptSummary,
    flag_key_statements,
    summarize_evidence_transcript,
    summarize_transcript,
)


def summarize_case_evidence(
    case: Case,
    show_progress: bool = True,
) -> Case:
    """
    Summarize all evidence in a case.

    This is the main entry point for the summarization pipeline.
    It processes all transcripts and documents, builds the timeline,
    and generates an executive summary.

    Args:
        case: Case to summarize
        show_progress: Whether to show progress output

    Returns:
        Updated case with summaries
    """
    # Check Ollama availability
    is_ready, message = check_ollama_ready()
    if not is_ready:
        if show_progress:
            print(f"Warning: {message}")
            print("Proceeding without AI summaries...")

    # Get evidence items with transcripts
    transcript_items = [
        e for e in case.evidence_items
        if e.transcript is not None
    ]

    if show_progress:
        print(f"Summarizing {len(transcript_items)} transcripts...")

    # Summarize each transcript
    for i, evidence in enumerate(transcript_items):
        if show_progress:
            print(f"  [{i+1}/{len(transcript_items)}] {evidence.filename}")

        try:
            # Flag key statements first
            if evidence.transcript:
                flag_key_statements(evidence.transcript)

            # Generate summary
            summary = summarize_evidence_transcript(evidence, save_summary=True)

            if show_progress and summary:
                print(f"    Summary: {len(summary.summary)} chars, "
                      f"{len(summary.key_statements)} key statements")

        except Exception as e:
            if show_progress:
                print(f"    Error: {e}")

    # Build timeline
    if show_progress:
        print("\nBuilding timeline...")

    case = add_timeline_to_case(case)

    if show_progress:
        print(f"  {len(case.timeline)} timeline events")

    # Generate case summary
    if show_progress:
        print("\nGenerating case summary...")

    case = add_summary_to_case(case)

    if show_progress and case.summary:
        print(f"  Summary: {len(case.summary)} chars")

    # Save case
    case.save()

    if show_progress:
        print("\nSummarization complete.")

    return case


def get_case_summary_text(case: Case) -> str:
    """
    Get a formatted text summary of a case.

    Args:
        case: Case to summarize

    Returns:
        Formatted summary text
    """
    summary = summarize_case(case, include_transcripts=True)
    return format_case_summary(summary)


def get_timeline_text(case: Case) -> str:
    """
    Get a formatted timeline for a case.

    Args:
        case: Case to get timeline for

    Returns:
        Formatted timeline text
    """
    entries = build_timeline(case)
    return format_timeline(entries)


__all__ = [
    # Main pipeline
    "summarize_case_evidence",
    "get_case_summary_text",
    "get_timeline_text",
    # Ollama client
    "OllamaClient",
    "OllamaResponse",
    "get_ollama_client",
    "check_ollama_ready",
    # Transcript summarizer
    "TranscriptSummary",
    "summarize_transcript",
    "summarize_evidence_transcript",
    "flag_key_statements",
    # Timeline builder
    "TimelineEntry",
    "build_timeline",
    "format_timeline",
    "add_timeline_to_case",
    # Case summarizer
    "CaseSummary",
    "summarize_case",
    "format_case_summary",
    "add_summary_to_case",
]
