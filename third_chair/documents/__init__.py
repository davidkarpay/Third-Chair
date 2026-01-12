"""Document processing module for Third Chair.

Handles extraction and processing of:
- PDF documents (text and scanned)
- Word documents (DOCX)
- Images (OCR)
- Axon transcript documents
"""

from pathlib import Path
from typing import Optional

from ..models import Case, EvidenceItem, FileType, ProcessingStatus
from .docx_parser import (
    DocxDocument,
    DocxParagraph,
    DocxTable,
    AxonTranscript,
    AxonTranscriptSegment,
    extract_text_from_docx,
    is_axon_transcript,
    parse_axon_transcript,
    parse_docx,
)
from .image_processor import (
    ImageOCRResult,
    batch_ocr_images,
    detect_image_language,
    extract_date_from_image,
    is_image_file,
    ocr_image,
    ocr_image_to_text,
)
from .pdf_extractor import (
    PDFDocument,
    PDFPage,
    extract_pdf,
    extract_tables_from_pdf,
    extract_text_from_pdf,
    is_scanned_pdf,
)


def extract_document_text(file_path: Path) -> str:
    """
    Extract text from any supported document type.

    Auto-detects file type and uses appropriate extractor.

    Args:
        file_path: Path to document

    Returns:
        Extracted text
    """
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return extract_text_from_docx(file_path)
    elif ext == ".txt":
        return file_path.read_text(encoding="utf-8", errors="ignore")
    elif is_image_file(file_path):
        return ocr_image_to_text(file_path)
    else:
        raise ValueError(f"Unsupported document type: {ext}")


def process_document(
    evidence: EvidenceItem,
    ocr_if_needed: bool = True,
) -> EvidenceItem:
    """
    Process a document evidence item.

    Extracts text and stores as summary.

    Args:
        evidence: Evidence item to process
        ocr_if_needed: Whether to use OCR for scanned documents

    Returns:
        Updated evidence item
    """
    if evidence.file_type not in (FileType.DOCUMENT, FileType.IMAGE):
        return evidence

    evidence.processing_status = ProcessingStatus.PROCESSING

    try:
        file_path = evidence.file_path
        ext = file_path.suffix.lower()

        if ext == ".pdf":
            doc = extract_pdf(file_path, ocr_fallback=ocr_if_needed)
            evidence.summary = doc.full_text[:5000]  # Limit summary length
            evidence.metadata["extraction_method"] = doc.extraction_method
            evidence.metadata["page_count"] = doc.page_count
            evidence.metadata["word_count"] = doc.total_words

        elif ext in (".docx", ".doc"):
            # Check if it's an Axon transcript
            if is_axon_transcript(file_path):
                transcript = parse_axon_transcript(file_path)
                evidence.metadata["is_axon_transcript"] = True
                evidence.metadata["segment_count"] = transcript.segment_count
                evidence.metadata["speakers"] = transcript.speakers
                # Store full text as summary
                evidence.summary = "\n".join(
                    f"[{s.timestamp}] {s.speaker}: {s.text}"
                    for s in transcript.segments
                )[:5000]
            else:
                doc = parse_docx(file_path)
                evidence.summary = doc.full_text[:5000]
                evidence.metadata["word_count"] = doc.word_count
                evidence.metadata["table_count"] = len(doc.tables)

        elif ext == ".txt":
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            evidence.summary = text[:5000]
            evidence.metadata["word_count"] = len(text.split())

        elif is_image_file(file_path):
            result = ocr_image(file_path)
            evidence.summary = result.text[:5000] if result.text else None
            evidence.metadata["ocr_confidence"] = result.confidence
            evidence.metadata["has_text"] = result.has_text
            evidence.metadata["image_size"] = result.metadata.get("size")

        evidence.processing_status = ProcessingStatus.COMPLETED

    except Exception as e:
        evidence.set_error(str(e))

    return evidence


def process_case_documents(
    case: Case,
    ocr_if_needed: bool = True,
    show_progress: bool = True,
) -> Case:
    """
    Process all document evidence items in a case.

    Args:
        case: Case to process
        ocr_if_needed: Whether to use OCR for scanned documents
        show_progress: Whether to show progress

    Returns:
        Updated case
    """
    # Get document and image evidence
    doc_items = [
        e for e in case.evidence_items
        if e.file_type in (FileType.DOCUMENT, FileType.IMAGE)
        and e.processing_status == ProcessingStatus.PENDING
    ]

    if not doc_items:
        if show_progress:
            print("No documents to process.")
        return case

    if show_progress:
        print(f"Processing {len(doc_items)} documents...")

    for i, evidence in enumerate(doc_items):
        if show_progress:
            print(f"  [{i+1}/{len(doc_items)}] {evidence.filename}")

        try:
            process_document(evidence, ocr_if_needed=ocr_if_needed)

            if show_progress and evidence.summary:
                word_count = len(evidence.summary.split())
                print(f"    Extracted {word_count} words")

        except Exception as e:
            if show_progress:
                print(f"    Error: {e}")

    # Save updated case
    case.save()

    if show_progress:
        processed = sum(1 for e in doc_items if e.is_processed)
        print(f"\nProcessed {processed}/{len(doc_items)} documents")

    return case


def get_document_summary(case: Case) -> dict:
    """
    Get a summary of document processing for a case.

    Args:
        case: Case to summarize

    Returns:
        Dict with document statistics
    """
    doc_items = [
        e for e in case.evidence_items
        if e.file_type in (FileType.DOCUMENT, FileType.IMAGE)
    ]

    summary = {
        "total_documents": len(doc_items),
        "processed": sum(1 for e in doc_items if e.is_processed),
        "with_text": sum(1 for e in doc_items if e.summary),
        "by_type": {},
        "total_words": 0,
        "axon_transcripts": 0,
    }

    for evidence in doc_items:
        ext = evidence.file_path.suffix.lower()
        summary["by_type"][ext] = summary["by_type"].get(ext, 0) + 1

        if evidence.metadata.get("word_count"):
            summary["total_words"] += evidence.metadata["word_count"]

        if evidence.metadata.get("is_axon_transcript"):
            summary["axon_transcripts"] += 1

    return summary


__all__ = [
    # Main functions
    "extract_document_text",
    "process_document",
    "process_case_documents",
    "get_document_summary",
    # PDF
    "PDFDocument",
    "PDFPage",
    "extract_pdf",
    "extract_text_from_pdf",
    "extract_tables_from_pdf",
    "is_scanned_pdf",
    # DOCX
    "DocxDocument",
    "DocxParagraph",
    "DocxTable",
    "parse_docx",
    "extract_text_from_docx",
    # Axon transcripts
    "AxonTranscript",
    "AxonTranscriptSegment",
    "parse_axon_transcript",
    "is_axon_transcript",
    # Images
    "ImageOCRResult",
    "ocr_image",
    "ocr_image_to_text",
    "batch_ocr_images",
    "is_image_file",
    "detect_image_language",
    "extract_date_from_image",
]
