"""File classification for Axon evidence packages."""

import re
from pathlib import Path
from typing import Optional

from ..models import (
    Case,
    ContentType,
    EvidenceItem,
    FileType,
    FILE_TYPE_MAP,
)


# Content type detection patterns (applied to filename)
CONTENT_TYPE_PATTERNS: list[tuple[str, ContentType]] = [
    # Body-worn camera
    (r"bwc|bodycam|body[_-]?cam|body[_-]?worn", ContentType.BWC_FOOTAGE),
    # Interviews and statements
    (r"interview", ContentType.INTERVIEW),
    (r"victim[_-]?statement|victim[_-]?stmt", ContentType.VICTIM_STATEMENT),
    (r"witness[_-]?statement|witness[_-]?stmt", ContentType.WITNESS_STATEMENT),
    (r"suspect[_-]?statement|suspect[_-]?stmt", ContentType.SUSPECT_STATEMENT),
    # Reports and logs
    (r"cad[_-]?log|dispatch", ContentType.CAD_LOG),
    (r"police[_-]?report|pr[_-]?\d+", ContentType.POLICE_REPORT),
    (r"incident[_-]?report|ir[_-]?\d+", ContentType.INCIDENT_REPORT),
    (r"evidence[_-]?log|chain[_-]?of[_-]?custody", ContentType.EVIDENCE_LOG),
    # Media types
    (r"photo|image|img|pic", ContentType.PHOTO),
    (r"surveillance|security[_-]?cam|cctv", ContentType.SURVEILLANCE),
    (r"audio|recording|rec", ContentType.AUDIO_RECORDING),
    (r"transcript", ContentType.TRANSCRIPT),
]


def classify_files(case: Case, extracted_dir: Path) -> Case:
    """
    Scan extracted directory and classify all files.

    Creates EvidenceItem objects for each file and adds them to the case.

    Args:
        case: Case object to populate
        extracted_dir: Directory containing extracted files

    Returns:
        Updated Case object with evidence items
    """
    # Walk through extracted directory
    for file_path in extracted_dir.rglob("*"):
        if not file_path.is_file():
            continue

        # Skip hidden files and system files
        if file_path.name.startswith(".") or file_path.name.startswith("__"):
            continue

        # Create evidence item
        evidence = _classify_file(file_path)
        if evidence:
            case.add_evidence(evidence)

    return case


def _classify_file(file_path: Path) -> Optional[EvidenceItem]:
    """
    Classify a single file and create an EvidenceItem.

    Args:
        file_path: Path to the file

    Returns:
        EvidenceItem or None if file should be skipped
    """
    # Get file extension and determine file type
    ext = file_path.suffix.lower()
    file_type = FILE_TYPE_MAP.get(ext, FileType.OTHER)

    # Skip unknown file types (unless they're common)
    if file_type == FileType.OTHER and ext not in (".json", ".xml", ".log"):
        return None

    # Generate evidence ID from filename
    evidence_id = _generate_evidence_id(file_path)

    # Detect content type from filename
    content_type = _detect_content_type(file_path.name, file_type)

    # Create evidence item
    evidence = EvidenceItem(
        id=evidence_id,
        filename=file_path.name,
        file_path=file_path,
        file_type=file_type,
        content_type=content_type,
        size_bytes=file_path.stat().st_size,
    )

    # Extract metadata from filename
    metadata = _parse_filename_metadata(file_path.name)
    evidence.metadata.update(metadata)

    return evidence


def _generate_evidence_id(file_path: Path) -> str:
    """
    Generate a unique evidence ID from filename.

    Extracts any existing evidence ID patterns, or creates one from filename.
    """
    filename = file_path.stem

    # Look for existing evidence ID patterns
    patterns = [
        r"Evidence[_-]?(\d+)",  # Evidence_001
        r"EVD[_-]?(\d+)",  # EVD001
        r"EV[_-]?(\d+)",  # EV001
        r"^(\d+)[_-]",  # 001_filename
    ]

    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return f"EVD-{match.group(1).zfill(3)}"

    # Generate from filename hash (first 8 chars)
    import hashlib
    hash_id = hashlib.md5(filename.encode()).hexdigest()[:8]
    return f"EVD-{hash_id}"


def _detect_content_type(filename: str, file_type: FileType) -> ContentType:
    """
    Detect content type from filename patterns.

    Args:
        filename: Name of the file
        file_type: Already-determined file type

    Returns:
        ContentType enum value
    """
    filename_lower = filename.lower()

    # Check against patterns
    for pattern, content_type in CONTENT_TYPE_PATTERNS:
        if re.search(pattern, filename_lower, re.IGNORECASE):
            return content_type

    # Default based on file type
    if file_type == FileType.VIDEO:
        return ContentType.BWC_FOOTAGE
    elif file_type == FileType.AUDIO:
        return ContentType.AUDIO_RECORDING
    elif file_type == FileType.IMAGE:
        return ContentType.PHOTO
    elif file_type == FileType.DOCUMENT:
        if "transcript" in filename_lower:
            return ContentType.TRANSCRIPT
        return ContentType.OTHER

    return ContentType.OTHER


def _parse_filename_metadata(filename: str) -> dict:
    """
    Extract metadata from Axon filename patterns.

    Axon filenames often contain structured information like:
    - Officer badge number
    - Unit identifier
    - Date/time stamps
    - Case numbers

    Returns:
        Dict of extracted metadata
    """
    metadata = {}

    # Officer/Unit patterns
    officer_match = re.search(r"(?:officer|ofc|deputy)[_-]?(\w+)", filename, re.IGNORECASE)
    if officer_match:
        metadata["officer"] = officer_match.group(1)

    unit_match = re.search(r"(?:unit|badge)[_-]?(\d+)", filename, re.IGNORECASE)
    if unit_match:
        metadata["unit"] = unit_match.group(1)

    # Date patterns
    date_patterns = [
        (r"(\d{4})(\d{2})(\d{2})", "{0}-{1}-{2}"),  # 20250115
        (r"(\d{4})[_-](\d{2})[_-](\d{2})", "{0}-{1}-{2}"),  # 2025-01-15
        (r"(\d{2})[_-](\d{2})[_-](\d{4})", "{2}-{0}-{1}"),  # 01-15-2025
    ]

    for pattern, fmt in date_patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                metadata["date"] = fmt.format(*match.groups())
                break
            except (ValueError, IndexError):
                continue

    # Time patterns
    time_match = re.search(r"(\d{2})(\d{2})(\d{2})(?!\d)", filename)
    if time_match:
        metadata["time"] = f"{time_match.group(1)}:{time_match.group(2)}:{time_match.group(3)}"

    # Camera number
    camera_match = re.search(r"(?:cam|camera)[_-]?(\d+)", filename, re.IGNORECASE)
    if camera_match:
        metadata["camera"] = camera_match.group(1)

    return metadata


def get_file_stats(case: Case) -> dict:
    """
    Get statistics about files in the case.

    Returns:
        Dict with counts by file type and content type
    """
    stats = {
        "total_files": len(case.evidence_items),
        "total_size_mb": sum(e.size_bytes for e in case.evidence_items) / (1024 * 1024),
        "by_file_type": {},
        "by_content_type": {},
        "media_files": 0,
        "transcribable_files": 0,
    }

    for evidence in case.evidence_items:
        # Count by file type
        ft = evidence.file_type.value
        stats["by_file_type"][ft] = stats["by_file_type"].get(ft, 0) + 1

        # Count by content type
        ct = evidence.content_type.value
        stats["by_content_type"][ct] = stats["by_content_type"].get(ct, 0) + 1

        # Count media files
        if evidence.is_media:
            stats["media_files"] += 1

        if evidence.is_transcribable:
            stats["transcribable_files"] += 1

    return stats
