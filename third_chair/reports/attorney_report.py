"""Attorney report generation.

Generates comprehensive reports for attorneys, combining:
- Evidence inventory
- Witness lists
- Timeline of events
- Key statements
- Executive summary
- Items needing review
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal

from ..models import Case
from .evidence_inventory import generate_evidence_inventory, format_inventory_text
from .docx_generator import generate_case_docx
from .pdf_generator import generate_case_pdf


@dataclass
class ReportConfig:
    """Configuration for report generation."""

    format: Literal["docx", "pdf", "text", "all"] = "docx"
    bates_prefix: str = "DEF"
    bates_start: int = 1
    prepared_by: Optional[str] = None
    include_transcripts: bool = False
    include_inventory_csv: bool = True


@dataclass
class ReportResult:
    """Result of report generation."""

    case_id: str
    generated_at: datetime
    output_dir: Path
    files_created: list[str] = field(default_factory=list)
    docx_path: Optional[Path] = None
    pdf_path: Optional[Path] = None
    text_path: Optional[Path] = None
    inventory_path: Optional[Path] = None
    final_bates_number: Optional[int] = None


def generate_attorney_report(
    case: Case,
    output_dir: Path,
    config: Optional[ReportConfig] = None,
    show_progress: bool = True,
) -> ReportResult:
    """
    Generate a comprehensive attorney report.

    Args:
        case: Case to report on
        output_dir: Directory to save reports
        config: Report configuration
        show_progress: Whether to show progress

    Returns:
        ReportResult with paths to generated files
    """
    config = config or ReportConfig()
    output_dir = Path(output_dir)
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    result = ReportResult(
        case_id=case.case_id,
        generated_at=datetime.now(),
        output_dir=reports_dir,
    )

    # Generate evidence inventory
    if show_progress:
        print("Generating evidence inventory...")

    inventory = generate_evidence_inventory(case)

    # Save inventory as text
    inventory_text = format_inventory_text(inventory)
    inventory_txt_path = reports_dir / "evidence_inventory.txt"
    inventory_txt_path.write_text(inventory_text)
    result.inventory_path = inventory_txt_path
    result.files_created.append("evidence_inventory.txt")

    # Save inventory as CSV if requested
    if config.include_inventory_csv:
        from .evidence_inventory import format_inventory_csv
        inventory_csv_path = reports_dir / "evidence_inventory.csv"
        inventory_csv_path.write_text(format_inventory_csv(inventory))
        result.files_created.append("evidence_inventory.csv")

    # Generate DOCX report
    if config.format in ("docx", "all"):
        if show_progress:
            print("Generating Word document...")

        docx_path = reports_dir / f"{case.case_id}_report.docx"
        generate_case_docx(
            case=case,
            output_path=docx_path,
            prepared_by=config.prepared_by,
            include_transcripts=config.include_transcripts,
        )
        result.docx_path = docx_path
        result.files_created.append(docx_path.name)

    # Generate PDF report
    if config.format in ("pdf", "all"):
        if show_progress:
            print("Generating PDF with Bates numbering...")

        pdf_path = reports_dir / f"{case.case_id}_report.pdf"
        _, final_bates = generate_case_pdf(
            case=case,
            output_path=pdf_path,
            bates_prefix=config.bates_prefix,
            bates_start=config.bates_start,
        )
        result.pdf_path = pdf_path
        result.final_bates_number = final_bates
        result.files_created.append(pdf_path.name)

    # Generate plain text report
    if config.format in ("text", "all"):
        if show_progress:
            print("Generating text report...")

        text_path = reports_dir / f"{case.case_id}_report.txt"
        text_content = _generate_text_report(case)
        text_path.write_text(text_content)
        result.text_path = text_path
        result.files_created.append(text_path.name)

    # Generate timeline file
    if show_progress:
        print("Generating timeline...")

    timeline_path = reports_dir / "timeline.txt"
    timeline_content = _format_timeline(case)
    timeline_path.write_text(timeline_content)
    result.files_created.append("timeline.txt")

    # Generate witness list
    if show_progress:
        print("Generating witness list...")

    witness_path = reports_dir / "witness_list.txt"
    witness_content = _format_witness_list(case)
    witness_path.write_text(witness_content)
    result.files_created.append("witness_list.txt")

    # Generate key statements file
    if show_progress:
        print("Generating key statements...")

    statements_path = reports_dir / "key_statements.txt"
    statements_content = _format_key_statements(case)
    statements_path.write_text(statements_content)
    result.files_created.append("key_statements.txt")

    if show_progress:
        print(f"\nGenerated {len(result.files_created)} report files.")

    return result


def _generate_text_report(case: Case) -> str:
    """Generate a plain text report."""
    lines = []

    # Header
    lines.append("=" * 70)
    lines.append("CASE ANALYSIS REPORT")
    lines.append("=" * 70)
    lines.append("")

    # Case info
    lines.append(f"Case ID: {case.case_id}")
    if case.court_case:
        lines.append(f"Court Case: {case.court_case}")
    if case.agency:
        lines.append(f"Agency: {case.agency}")
    if case.incident_date:
        lines.append(f"Incident Date: {case.incident_date.strftime('%B %d, %Y')}")
    lines.append(f"Report Generated: {datetime.now().strftime('%B %d, %Y %H:%M')}")
    lines.append("")

    # Executive summary
    lines.append("-" * 40)
    lines.append("EXECUTIVE SUMMARY")
    lines.append("-" * 40)
    if case.summary:
        lines.append(case.summary)
    else:
        lines.append("No summary available.")
    lines.append("")

    # Key findings
    if case.metadata and case.metadata.get("key_findings"):
        lines.append("-" * 40)
        lines.append("KEY FINDINGS")
        lines.append("-" * 40)
        for i, finding in enumerate(case.metadata["key_findings"], 1):
            lines.append(f"{i}. {finding}")
        lines.append("")

    # Alerts
    if case.metadata:
        threats = case.metadata.get("threats_identified", 0)
        violence = case.metadata.get("violence_indicators", 0)

        if threats > 0 or violence > 0:
            lines.append("-" * 40)
            lines.append("ALERTS")
            lines.append("-" * 40)
            if threats > 0:
                lines.append(f"[!] Threat keywords detected: {threats}")
            if violence > 0:
                lines.append(f"[!] Violence indicators: {violence}")
            lines.append("")

    # Statistics
    lines.append("-" * 40)
    lines.append("CASE STATISTICS")
    lines.append("-" * 40)
    lines.append(f"Total Evidence Items: {len(case.evidence_items)}")
    lines.append(f"Witnesses Identified: {len(case.witnesses.witnesses)}")
    lines.append(f"Timeline Events: {len(case.timeline)}")

    transcribed = sum(1 for e in case.evidence_items if e.transcript)
    lines.append(f"Transcribed Items: {transcribed}")

    if case.metadata and case.metadata.get("spanish_percentage"):
        lines.append(f"Spanish Content: {case.metadata['spanish_percentage']:.1f}%")
    lines.append("")

    # Items needing review
    if case.metadata and case.metadata.get("items_needing_review"):
        lines.append("-" * 40)
        lines.append("ITEMS REQUIRING REVIEW")
        lines.append("-" * 40)
        for item in case.metadata["items_needing_review"]:
            lines.append(f"  - {item}")
        lines.append("")

    return "\n".join(lines)


def _format_timeline(case: Case) -> str:
    """Format timeline as text."""
    lines = []
    lines.append("=" * 50)
    lines.append("TIMELINE OF EVENTS")
    lines.append("=" * 50)
    lines.append("")

    if not case.timeline:
        lines.append("No timeline events.")
        return "\n".join(lines)

    current_date = None

    for event in case.timeline:
        event_date = event.timestamp.date()

        if event_date != current_date:
            current_date = event_date
            lines.append("")
            lines.append(f"=== {event_date.strftime('%B %d, %Y')} ===")
            lines.append("")

        time_str = event.timestamp.strftime("%H:%M:%S")
        importance = event.metadata.get("importance", "normal") if event.metadata else "normal"

        prefix = ""
        if importance == "critical":
            prefix = "[!!!] "
        elif importance == "high":
            prefix = "[!] "

        lines.append(f"{time_str}  {prefix}{event.description}")

    return "\n".join(lines)


def _format_witness_list(case: Case) -> str:
    """Format witness list as text."""
    lines = []
    lines.append("=" * 50)
    lines.append("WITNESS LIST")
    lines.append("=" * 50)
    lines.append("")

    if not case.witnesses.witnesses:
        lines.append("No witnesses identified.")
        return "\n".join(lines)

    for i, witness in enumerate(case.witnesses.witnesses, 1):
        lines.append(f"[{i}] {witness.display_name}")
        lines.append(f"    Role: {witness.role.value}")
        lines.append(f"    Speaker IDs: {', '.join(witness.speaker_ids)}")
        lines.append(f"    Evidence appearances: {len(witness.evidence_appearances)}")
        lines.append(f"    Verified: {'Yes' if witness.verified else 'No'}")

        if witness.notes:
            lines.append(f"    Notes: {witness.notes}")

        lines.append("")

    return "\n".join(lines)


def _format_key_statements(case: Case) -> str:
    """Format key statements as text."""
    lines = []
    lines.append("=" * 50)
    lines.append("KEY STATEMENTS")
    lines.append("=" * 50)
    lines.append("")

    statements_found = False

    for evidence in case.evidence_items:
        if not evidence.transcript:
            continue

        if not evidence.transcript.key_statements:
            continue

        statements_found = True
        lines.append(f"--- {evidence.filename} ---")
        lines.append("")

        for segment in evidence.transcript.key_statements:
            speaker = evidence.transcript.get_speaker_name(segment.speaker)
            time_str = f"[{segment.start_time:.1f}s]"

            lines.append(f"{time_str} {speaker}:")
            lines.append(f"  {segment.text}")

            if segment.translation:
                lines.append(f"  [Translation: {segment.translation}]")

            if segment.review_flags:
                flags = ", ".join(f.value for f in segment.review_flags)
                lines.append(f"  Flags: {flags}")

            lines.append("")

    if not statements_found:
        lines.append("No key statements flagged.")

    return "\n".join(lines)


def generate_transcript_files(
    case: Case,
    output_dir: Path,
    formats: list[str] = None,
    show_progress: bool = True,
) -> list[Path]:
    """
    Generate individual transcript files for each evidence item.

    Args:
        case: Case with transcripts
        output_dir: Output directory
        formats: List of formats ("txt", "srt", "json")
        show_progress: Whether to show progress

    Returns:
        List of generated file paths
    """
    formats = formats or ["txt", "srt"]
    output_dir = Path(output_dir)
    transcripts_dir = output_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    generated = []

    for evidence in case.evidence_items:
        if not evidence.transcript:
            continue

        if show_progress:
            print(f"  {evidence.filename}")

        base_name = Path(evidence.filename).stem

        # Text format
        if "txt" in formats:
            txt_path = transcripts_dir / f"{base_name}.txt"
            txt_content = _format_transcript_txt(evidence)
            txt_path.write_text(txt_content)
            generated.append(txt_path)

        # SRT format
        if "srt" in formats:
            srt_path = transcripts_dir / f"{base_name}.srt"
            srt_content = _format_transcript_srt(evidence)
            srt_path.write_text(srt_content)
            generated.append(srt_path)

        # JSON format
        if "json" in formats:
            import json
            json_path = transcripts_dir / f"{base_name}.json"
            json_content = evidence.transcript.to_dict()
            json_path.write_text(json.dumps(json_content, indent=2, default=str))
            generated.append(json_path)

    return generated


def _format_transcript_txt(evidence) -> str:
    """Format transcript as plain text."""
    lines = []
    lines.append(f"Transcript: {evidence.filename}")
    lines.append("=" * 50)
    lines.append("")

    for segment in evidence.transcript.segments:
        speaker = evidence.transcript.get_speaker_name(segment.speaker)
        time_str = f"[{segment.start_time:.1f}s - {segment.end_time:.1f}s]"

        lines.append(f"{time_str} {speaker}:")
        lines.append(f"  {segment.text}")

        if segment.translation:
            lines.append(f"  [Translation: {segment.translation}]")

        lines.append("")

    return "\n".join(lines)


def _format_transcript_srt(evidence) -> str:
    """Format transcript as SRT subtitles."""
    lines = []

    for i, segment in enumerate(evidence.transcript.segments, 1):
        # Sequence number
        lines.append(str(i))

        # Timestamps (SRT format: HH:MM:SS,mmm --> HH:MM:SS,mmm)
        start = _seconds_to_srt_time(segment.start_time)
        end = _seconds_to_srt_time(segment.end_time)
        lines.append(f"{start} --> {end}")

        # Text with speaker
        speaker = evidence.transcript.get_speaker_name(segment.speaker)
        text = f"[{speaker}] {segment.text}"

        # Add translation if available
        if segment.translation:
            text += f"\n({segment.translation})"

        lines.append(text)
        lines.append("")  # Blank line between entries

    return "\n".join(lines)


def _seconds_to_srt_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
