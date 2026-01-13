"""Report generation module for Third Chair.

Generates attorney-ready reports in multiple formats:
- DOCX (Word document)
- PDF with Bates numbering
- Plain text
- CSV exports
"""

from pathlib import Path
from typing import Optional

from ..models import Case
from .attorney_report import (
    ReportConfig,
    ReportResult,
    generate_attorney_report,
    generate_transcript_files,
)
from .docx_generator import (
    DocxGenerator,
    generate_case_docx,
)
from .evidence_inventory import (
    EvidenceInventory,
    InventoryItem,
    format_inventory_csv,
    format_inventory_text,
    generate_evidence_inventory,
)
from .pdf_generator import (
    PdfGenerator,
    generate_case_pdf,
)
from .viewing_guide import (
    ViewingRecommendation,
    generate_viewing_guide,
    format_viewing_guide_text,
    write_viewing_guide,
    get_viewing_stats,
)


def generate_all_reports(
    case: Case,
    output_dir: Path,
    bates_prefix: str = "DEF",
    bates_start: int = 1,
    prepared_by: Optional[str] = None,
    include_transcripts: bool = True,
    show_progress: bool = True,
) -> ReportResult:
    """
    Generate all reports for a case.

    This is the main entry point for report generation.
    Creates DOCX, PDF (with Bates numbering), text reports,
    evidence inventory, timeline, witness list, and key statements.

    Args:
        case: Case to report on
        output_dir: Directory to save reports
        bates_prefix: Prefix for Bates numbers
        bates_start: Starting Bates number
        prepared_by: Name of report preparer
        include_transcripts: Whether to include full transcripts
        show_progress: Whether to show progress

    Returns:
        ReportResult with paths to all generated files
    """
    config = ReportConfig(
        format="all",
        bates_prefix=bates_prefix,
        bates_start=bates_start,
        prepared_by=prepared_by,
        include_transcripts=include_transcripts,
        include_inventory_csv=True,
    )

    result = generate_attorney_report(
        case=case,
        output_dir=output_dir,
        config=config,
        show_progress=show_progress,
    )

    # Also generate transcript files
    if show_progress:
        print("Generating transcript files...")

    transcript_files = generate_transcript_files(
        case=case,
        output_dir=output_dir,
        formats=["txt", "srt"],
        show_progress=show_progress,
    )

    result.files_created.extend([f.name for f in transcript_files])

    return result


def generate_quick_report(
    case: Case,
    output_path: Path,
    format: str = "docx",
) -> Path:
    """
    Generate a quick single-format report.

    Args:
        case: Case to report on
        output_path: Output file path
        format: Output format (docx or pdf)

    Returns:
        Path to generated file
    """
    output_path = Path(output_path)

    if format == "docx":
        return generate_case_docx(case=case, output_path=output_path)
    elif format == "pdf":
        path, _ = generate_case_pdf(case=case, output_path=output_path)
        return path
    else:
        raise ValueError(f"Unsupported format: {format}")


__all__ = [
    # Main entry points
    "generate_all_reports",
    "generate_quick_report",
    "generate_attorney_report",
    "generate_transcript_files",
    # Configuration
    "ReportConfig",
    "ReportResult",
    # Evidence inventory
    "EvidenceInventory",
    "InventoryItem",
    "generate_evidence_inventory",
    "format_inventory_text",
    "format_inventory_csv",
    # DOCX generation
    "DocxGenerator",
    "generate_case_docx",
    # PDF generation
    "PdfGenerator",
    "generate_case_pdf",
    # Viewing guide
    "ViewingRecommendation",
    "generate_viewing_guide",
    "format_viewing_guide_text",
    "write_viewing_guide",
    "get_viewing_stats",
]
