"""Ingest module for Axon evidence packages."""

from pathlib import Path
from typing import Optional

from ..models import Case
from .file_classifier import classify_files, get_file_stats
from .metadata_parser import extract_case_metadata
from .toc_parser import find_toc_file, parse_toc, update_case_from_toc
from .zip_extractor import extract_axon_zip, list_zip_contents


def ingest_axon_package(
    zip_path: Path,
    output_dir: Path,
    case_id: Optional[str] = None,
    court_case: Optional[str] = None,
    show_progress: bool = True,
) -> Case:
    """
    Ingest an Axon evidence package and create a Case.

    This is the main entry point for processing Axon ZIP exports.
    It performs:
    1. ZIP extraction
    2. File classification
    3. ToC parsing (if present)
    4. Metadata extraction

    Args:
        zip_path: Path to the Axon ZIP file
        output_dir: Directory to extract and process files
        case_id: Optional case ID (auto-extracted if not provided)
        court_case: Optional court case number
        show_progress: Whether to show progress indicators

    Returns:
        Populated Case object
    """
    # Convert to Path objects
    zip_path = Path(zip_path)
    output_dir = Path(output_dir)

    # Step 1: Extract ZIP
    case = extract_axon_zip(
        zip_path=zip_path,
        output_dir=output_dir,
        case_id=case_id,
        show_progress=show_progress,
    )

    # Set court case if provided
    if court_case:
        case.court_case = court_case

    # Step 2: Classify files
    extracted_dir = output_dir / "extracted"
    case = classify_files(case, extracted_dir)

    # Step 3: Parse ToC if present
    toc_path = find_toc_file(extracted_dir)
    if toc_path:
        toc_entries = parse_toc(toc_path)
        case = update_case_from_toc(case, toc_entries)

    # Step 4: Extract additional metadata
    case = extract_case_metadata(case, extracted_dir)

    # Step 5: Save case state
    case.save()

    return case


__all__ = [
    "ingest_axon_package",
    "extract_axon_zip",
    "list_zip_contents",
    "classify_files",
    "get_file_stats",
    "extract_case_metadata",
    "find_toc_file",
    "parse_toc",
    "update_case_from_toc",
]
