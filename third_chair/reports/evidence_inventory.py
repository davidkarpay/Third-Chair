"""Evidence inventory report generation.

Creates detailed inventory of all evidence items in a case,
suitable for legal discovery tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import Case, EvidenceItem, FileType, ContentType


@dataclass
class InventoryItem:
    """A single item in the evidence inventory."""

    item_number: int
    evidence_id: str
    filename: str
    file_type: str
    content_type: str
    size_bytes: int
    duration_seconds: Optional[float] = None
    has_transcript: bool = False
    has_translation: bool = False
    has_summary: bool = False
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    notes: str = ""


@dataclass
class EvidenceInventory:
    """Complete evidence inventory for a case."""

    case_id: str
    court_case: Optional[str]
    generated_at: datetime
    items: list[InventoryItem] = field(default_factory=list)
    total_count: int = 0
    total_size_bytes: int = 0
    total_duration_seconds: float = 0.0

    # Counts by type
    video_count: int = 0
    audio_count: int = 0
    document_count: int = 0
    image_count: int = 0

    # Counts by content type
    by_content_type: dict[str, int] = field(default_factory=dict)


def generate_evidence_inventory(case: Case) -> EvidenceInventory:
    """
    Generate a comprehensive evidence inventory.

    Args:
        case: Case to inventory

    Returns:
        EvidenceInventory with all items
    """
    inventory = EvidenceInventory(
        case_id=case.case_id,
        court_case=case.court_case,
        generated_at=datetime.now(),
    )

    for i, evidence in enumerate(case.evidence_items, start=1):
        item = _create_inventory_item(i, evidence)
        inventory.items.append(item)

        # Update totals
        inventory.total_count += 1
        inventory.total_size_bytes += evidence.size_bytes

        if evidence.duration_seconds:
            inventory.total_duration_seconds += evidence.duration_seconds

        # Count by file type
        if evidence.file_type == FileType.VIDEO:
            inventory.video_count += 1
        elif evidence.file_type == FileType.AUDIO:
            inventory.audio_count += 1
        elif evidence.file_type == FileType.DOCUMENT:
            inventory.document_count += 1
        elif evidence.file_type == FileType.IMAGE:
            inventory.image_count += 1

        # Count by content type
        content = evidence.content_type.value if evidence.content_type else "unknown"
        inventory.by_content_type[content] = inventory.by_content_type.get(content, 0) + 1

    return inventory


def _create_inventory_item(number: int, evidence: EvidenceItem) -> InventoryItem:
    """Create an inventory item from evidence."""
    notes_parts = []

    # Check for issues
    if evidence.processing_status.value == "error":
        notes_parts.append(f"Error: {evidence.error_message or 'Unknown'}")

    # Check for flags
    if evidence.transcript:
        flagged_count = sum(
            1 for s in evidence.transcript.segments
            if s.review_flags
        )
        if flagged_count > 0:
            notes_parts.append(f"{flagged_count} flagged segments")

    # Check for low confidence
    if evidence.metadata.get("ocr_confidence", 1.0) < 0.8:
        notes_parts.append("Low OCR confidence")

    # Check for Spanish content
    if evidence.metadata.get("spanish_percentage", 0) > 20:
        notes_parts.append("Contains Spanish")

    return InventoryItem(
        item_number=number,
        evidence_id=evidence.id,
        filename=evidence.filename,
        file_type=evidence.file_type.value,
        content_type=evidence.content_type.value if evidence.content_type else "unknown",
        size_bytes=evidence.size_bytes,
        duration_seconds=evidence.duration_seconds,
        has_transcript=evidence.transcript is not None,
        has_translation=_has_translations(evidence),
        has_summary=evidence.summary is not None,
        page_count=evidence.metadata.get("page_count"),
        word_count=evidence.metadata.get("word_count"),
        notes="; ".join(notes_parts) if notes_parts else "",
    )


def _has_translations(evidence: EvidenceItem) -> bool:
    """Check if evidence has any translated content."""
    if not evidence.transcript:
        return False

    return any(s.translation for s in evidence.transcript.segments)


def format_inventory_text(inventory: EvidenceInventory) -> str:
    """
    Format inventory as plain text.

    Args:
        inventory: Inventory to format

    Returns:
        Formatted text
    """
    lines = []

    # Header
    lines.append("=" * 70)
    lines.append("EVIDENCE INVENTORY")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Case ID: {inventory.case_id}")
    if inventory.court_case:
        lines.append(f"Court Case: {inventory.court_case}")
    lines.append(f"Generated: {inventory.generated_at.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # Summary
    lines.append("-" * 40)
    lines.append("SUMMARY")
    lines.append("-" * 40)
    lines.append(f"Total Items: {inventory.total_count}")
    lines.append(f"Total Size: {_format_size(inventory.total_size_bytes)}")
    if inventory.total_duration_seconds > 0:
        lines.append(f"Total Duration: {_format_duration(inventory.total_duration_seconds)}")
    lines.append("")
    lines.append("By Type:")
    lines.append(f"  Videos: {inventory.video_count}")
    lines.append(f"  Audio: {inventory.audio_count}")
    lines.append(f"  Documents: {inventory.document_count}")
    lines.append(f"  Images: {inventory.image_count}")
    lines.append("")

    if inventory.by_content_type:
        lines.append("By Content:")
        for content_type, count in sorted(inventory.by_content_type.items()):
            lines.append(f"  {content_type}: {count}")
        lines.append("")

    # Item list
    lines.append("-" * 40)
    lines.append("ITEMS")
    lines.append("-" * 40)

    for item in inventory.items:
        lines.append("")
        lines.append(f"[{item.item_number}] {item.filename}")
        lines.append(f"    ID: {item.evidence_id}")
        lines.append(f"    Type: {item.file_type} / {item.content_type}")
        lines.append(f"    Size: {_format_size(item.size_bytes)}")

        if item.duration_seconds:
            lines.append(f"    Duration: {_format_duration(item.duration_seconds)}")

        if item.page_count:
            lines.append(f"    Pages: {item.page_count}")

        if item.word_count:
            lines.append(f"    Words: {item.word_count:,}")

        # Status indicators
        status = []
        if item.has_transcript:
            status.append("Transcribed")
        if item.has_translation:
            status.append("Translated")
        if item.has_summary:
            status.append("Summarized")

        if status:
            lines.append(f"    Status: {', '.join(status)}")

        if item.notes:
            lines.append(f"    Notes: {item.notes}")

    return "\n".join(lines)


def format_inventory_csv(inventory: EvidenceInventory) -> str:
    """
    Format inventory as CSV.

    Args:
        inventory: Inventory to format

    Returns:
        CSV string
    """
    lines = []

    # Header
    headers = [
        "Item #",
        "Evidence ID",
        "Filename",
        "File Type",
        "Content Type",
        "Size (bytes)",
        "Duration (sec)",
        "Has Transcript",
        "Has Translation",
        "Has Summary",
        "Page Count",
        "Word Count",
        "Notes",
    ]
    lines.append(",".join(headers))

    # Data rows
    for item in inventory.items:
        row = [
            str(item.item_number),
            item.evidence_id,
            f'"{item.filename}"',
            item.file_type,
            item.content_type,
            str(item.size_bytes),
            str(item.duration_seconds or ""),
            "Yes" if item.has_transcript else "No",
            "Yes" if item.has_translation else "No",
            "Yes" if item.has_summary else "No",
            str(item.page_count or ""),
            str(item.word_count or ""),
            f'"{item.notes}"' if item.notes else "",
        ]
        lines.append(",".join(row))

    return "\n".join(lines)


def _format_size(bytes_val: int) -> str:
    """Format bytes as human-readable size."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"


def _format_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"
