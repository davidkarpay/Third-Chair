"""PDF text extraction with OCR fallback.

Extracts text from PDFs using:
1. pdfplumber for text-based PDFs
2. pytesseract OCR for scanned/image PDFs
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PDFPage:
    """Represents a single page from a PDF."""

    page_number: int
    text: str
    is_ocr: bool = False
    word_count: int = 0
    has_tables: bool = False
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass
class PDFDocument:
    """Represents an extracted PDF document."""

    file_path: Path
    pages: list[PDFPage] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    extraction_method: str = "text"  # "text", "ocr", or "mixed"

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def full_text(self) -> str:
        """Get all text from all pages."""
        return "\n\n".join(page.text for page in self.pages if page.text)

    @property
    def total_words(self) -> int:
        return sum(page.word_count for page in self.pages)

    def get_page(self, page_number: int) -> Optional[PDFPage]:
        """Get a specific page (1-indexed)."""
        for page in self.pages:
            if page.page_number == page_number:
                return page
        return None


def extract_pdf(
    file_path: Path,
    ocr_fallback: bool = True,
    extract_tables: bool = True,
) -> PDFDocument:
    """
    Extract text from a PDF file.

    Args:
        file_path: Path to the PDF file
        ocr_fallback: Whether to use OCR if text extraction fails
        extract_tables: Whether to extract tables

    Returns:
        PDFDocument with extracted content
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    doc = PDFDocument(file_path=file_path)

    # Try text extraction first
    pages = _extract_with_pdfplumber(file_path, extract_tables)

    # Check if we got meaningful text
    total_words = sum(p.word_count for p in pages)

    if total_words < 10 and ocr_fallback:
        # Likely a scanned PDF, try OCR
        ocr_pages = _extract_with_ocr(file_path)
        if ocr_pages:
            pages = ocr_pages
            doc.extraction_method = "ocr"
    elif any(p.is_ocr for p in pages):
        doc.extraction_method = "mixed"

    doc.pages = pages

    # Extract metadata
    doc.metadata = _extract_metadata(file_path)

    return doc


def _extract_with_pdfplumber(
    file_path: Path,
    extract_tables: bool = True,
) -> list[PDFPage]:
    """Extract text using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is required. Install with: pip install pdfplumber")

    pages = []

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            # Extract text
            text = page.extract_text() or ""
            text = _clean_text(text)

            # Count words
            word_count = len(text.split()) if text else 0

            # Extract tables if requested
            tables = []
            has_tables = False
            if extract_tables:
                try:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables = page_tables
                        has_tables = True
                except Exception:
                    pass

            pages.append(PDFPage(
                page_number=i,
                text=text,
                is_ocr=False,
                word_count=word_count,
                has_tables=has_tables,
                tables=tables,
            ))

    return pages


def _extract_with_ocr(file_path: Path) -> list[PDFPage]:
    """Extract text using OCR (for scanned PDFs)."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        print("Warning: OCR dependencies not available (pytesseract, pdf2image)")
        return []

    pages = []

    try:
        # Convert PDF pages to images
        images = convert_from_path(file_path, dpi=300)

        for i, image in enumerate(images, 1):
            # Run OCR
            text = pytesseract.image_to_string(image)
            text = _clean_text(text)
            word_count = len(text.split()) if text else 0

            pages.append(PDFPage(
                page_number=i,
                text=text,
                is_ocr=True,
                word_count=word_count,
            ))

    except Exception as e:
        print(f"Warning: OCR failed: {e}")

    return pages


def _extract_metadata(file_path: Path) -> dict:
    """Extract PDF metadata."""
    metadata = {}

    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            if pdf.metadata:
                metadata = {
                    k: v for k, v in pdf.metadata.items()
                    if v and isinstance(v, (str, int, float))
                }
    except Exception:
        pass

    return metadata


def _clean_text(text: str) -> str:
    """Clean extracted text."""
    if not text:
        return ""

    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)

    # Remove form feed and other control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)

    # Fix common OCR artifacts
    text = text.replace("|", "I")  # Common OCR error
    text = re.sub(r"(?<=[a-z])0(?=[a-z])", "o", text)  # 0 for o

    return text.strip()


def extract_text_from_pdf(file_path: Path) -> str:
    """
    Simple function to extract all text from a PDF.

    Args:
        file_path: Path to PDF file

    Returns:
        Extracted text as a single string
    """
    doc = extract_pdf(file_path)
    return doc.full_text


def is_scanned_pdf(file_path: Path) -> bool:
    """
    Check if a PDF is likely scanned (image-based).

    Args:
        file_path: Path to PDF file

    Returns:
        True if PDF appears to be scanned
    """
    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            total_words = 0
            for page in pdf.pages[:3]:  # Check first 3 pages
                text = page.extract_text() or ""
                total_words += len(text.split())

            # If very few words, likely scanned
            return total_words < 20

    except Exception:
        return False


def extract_tables_from_pdf(file_path: Path) -> list[dict]:
    """
    Extract tables from a PDF.

    Args:
        file_path: Path to PDF file

    Returns:
        List of tables, each as a dict with page number and data
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is required. Install with: pip install pdfplumber")

    tables = []

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            try:
                page_tables = page.extract_tables()
                for j, table in enumerate(page_tables):
                    if table:
                        tables.append({
                            "page": i,
                            "table_index": j,
                            "data": table,
                            "rows": len(table),
                            "cols": len(table[0]) if table else 0,
                        })
            except Exception:
                continue

    return tables
