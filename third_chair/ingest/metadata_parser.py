"""Metadata extraction from Axon evidence packages."""

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from ..models import Case


def extract_case_metadata(case: Case, extracted_dir: Path) -> Case:
    """
    Extract and populate case metadata from various sources.

    Sources checked:
    1. ZIP filename
    2. Evidence filenames
    3. Table_of_Contents.xlsx (if present)
    4. Other metadata files

    Args:
        case: Case object to populate
        extracted_dir: Directory containing extracted files

    Returns:
        Updated Case object with metadata
    """
    # Try to extract from source ZIP name
    if case.source_zip:
        zip_metadata = _parse_axon_filename(case.source_zip)
        _update_case_metadata(case, zip_metadata)

    # Look for metadata in evidence filenames
    for evidence in case.evidence_items:
        file_metadata = _parse_axon_filename(evidence.filename)
        if file_metadata:
            # Only update case-level metadata if not already set
            if not case.agency and file_metadata.get("agency"):
                case.agency = file_metadata["agency"]
            if not case.incident_date and file_metadata.get("date"):
                try:
                    case.incident_date = date.fromisoformat(file_metadata["date"])
                except ValueError:
                    pass

    return case


def _parse_axon_filename(filename: str) -> dict[str, Any]:
    """
    Parse an Axon filename to extract metadata.

    Axon filename patterns include:
    - Case numbers: Case_2025-12345, 2025-CF-001234
    - Evidence IDs: Evidence_001, EVD001
    - Officer info: Officer_Smith, Badge_1234
    - Dates: 20250115, 2025-01-15
    - Camera info: CAM01, Unit_5

    Args:
        filename: Filename to parse

    Returns:
        Dict of extracted metadata
    """
    metadata: dict[str, Any] = {}
    filename_lower = filename.lower()

    # Case number patterns
    case_patterns = [
        (r"case[_-]?(\d{4}[_-]?\d+)", "case_number"),
        (r"(\d{4}[_-]cf[_-]\d+)", "case_number"),
        (r"(\d{4}[_-]mm[_-]\d+)", "case_number"),
        (r"incident[_-]?(\d+)", "incident_number"),
    ]

    for pattern, key in case_patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            metadata[key] = match.group(1).replace("_", "-")
            break

    # Officer information
    officer_patterns = [
        (r"(?:officer|ofc|deputy)[_-]?([a-z]+)", "officer_name"),
        (r"(?:badge|unit)[_-]?(\d+)", "badge_number"),
    ]

    for pattern, key in officer_patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            metadata[key] = match.group(1)

    # Date extraction
    date_patterns = [
        # YYYYMMDD
        (r"(?<!\d)(\d{4})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)",
         lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
        # YYYY-MM-DD
        (r"(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])",
         lambda m: m.group(0)),
        # MM-DD-YYYY
        (r"(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])-(\d{4})",
         lambda m: f"{m.group(3)}-{m.group(1)}-{m.group(2)}"),
    ]

    for pattern, formatter in date_patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                date_str = formatter(match)
                # Validate date
                datetime.strptime(date_str, "%Y-%m-%d")
                metadata["date"] = date_str
                break
            except ValueError:
                continue

    # Time extraction (HHMMSS)
    time_match = re.search(r"(?<!\d)([01]\d|2[0-3])([0-5]\d)([0-5]\d)(?!\d)", filename)
    if time_match:
        metadata["time"] = f"{time_match.group(1)}:{time_match.group(2)}:{time_match.group(3)}"

    # Agency patterns
    agency_patterns = [
        (r"pbso|palm[_-]?beach[_-]?sheriff", "Palm Beach County Sheriff's Office"),
        (r"fhp|florida[_-]?highway", "Florida Highway Patrol"),
        (r"miami[_-]?dade|mdpd", "Miami-Dade Police Department"),
        (r"broward|bso", "Broward Sheriff's Office"),
    ]

    for pattern, agency in agency_patterns:
        if re.search(pattern, filename_lower):
            metadata["agency"] = agency
            break

    # Content type hints
    content_hints = [
        (r"victim", "victim_related"),
        (r"witness", "witness_related"),
        (r"suspect|defendant", "suspect_related"),
        (r"scene|location", "scene_related"),
    ]

    for pattern, hint in content_hints:
        if re.search(pattern, filename_lower):
            metadata["content_hint"] = hint
            break

    return metadata


def _update_case_metadata(case: Case, metadata: dict[str, Any]) -> None:
    """Update case with extracted metadata."""
    if not case.case_id and metadata.get("case_number"):
        case.case_id = metadata["case_number"]

    if not case.agency and metadata.get("agency"):
        case.agency = metadata["agency"]

    if not case.incident_date and metadata.get("date"):
        try:
            case.incident_date = date.fromisoformat(metadata["date"])
        except ValueError:
            pass

    # Store additional metadata
    for key in ["officer_name", "badge_number", "incident_number"]:
        if metadata.get(key):
            case.metadata[key] = metadata[key]


def find_related_transcript(evidence_filename: str, all_files: list[Path]) -> Optional[Path]:
    """
    Find a pre-existing transcript file for a media file.

    Axon often exports transcripts alongside media files with patterns like:
    - video.mp4 -> Transcript_for_video.txt
    - video.mp4 -> video_transcript.docx

    Args:
        evidence_filename: Name of the media file
        all_files: List of all files in the extracted directory

    Returns:
        Path to transcript file if found, None otherwise
    """
    base_name = Path(evidence_filename).stem.lower()

    # Patterns to search for
    patterns = [
        f"transcript_for_{base_name}",
        f"{base_name}_transcript",
        f"{base_name}.transcript",
        f"transcript_{base_name}",
    ]

    for file_path in all_files:
        file_lower = file_path.stem.lower()
        ext_lower = file_path.suffix.lower()

        # Check if it's a document
        if ext_lower not in (".txt", ".docx", ".doc"):
            continue

        for pattern in patterns:
            if pattern in file_lower or file_lower in pattern:
                return file_path

    return None


def extract_axon_evidence_id(filename: str) -> Optional[str]:
    """
    Extract the Axon evidence ID from a filename.

    Axon evidence IDs follow patterns like:
    - X123456789
    - AXON-123456789
    - Evidence_X123456789

    Args:
        filename: Filename to parse

    Returns:
        Evidence ID if found, None otherwise
    """
    patterns = [
        r"(X\d{9,})",  # X followed by 9+ digits
        r"AXON[_-]?(\d+)",  # AXON prefix
        r"Evidence[_-]?(X?\d+)",  # Evidence prefix
    ]

    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return match.group(1)

    return None
