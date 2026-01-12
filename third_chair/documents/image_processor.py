"""Image processing and OCR for evidence photos.

Extracts text from images using pytesseract OCR.
Handles common evidence image formats.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Supported image formats
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"}


@dataclass
class ImageOCRResult:
    """Result from OCR processing of an image."""

    file_path: Path
    text: str
    confidence: float = 0.0
    word_count: int = 0
    has_text: bool = False
    language: str = "eng"
    metadata: dict = field(default_factory=dict)


def is_image_file(file_path: Path) -> bool:
    """Check if a file is a supported image format."""
    return file_path.suffix.lower() in IMAGE_EXTENSIONS


def ocr_image(
    file_path: Path,
    language: str = "eng",
    preprocess: bool = True,
) -> ImageOCRResult:
    """
    Extract text from an image using OCR.

    Args:
        file_path: Path to image file
        language: Tesseract language code (eng, spa, etc.)
        preprocess: Whether to preprocess image for better OCR

    Returns:
        ImageOCRResult with extracted text
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise ImportError(
            "pytesseract and Pillow are required. "
            "Install with: pip install pytesseract Pillow"
        )

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Image not found: {file_path}")

    result = ImageOCRResult(
        file_path=file_path,
        text="",
        language=language,
    )

    try:
        # Load image
        image = Image.open(file_path)

        # Store image metadata
        result.metadata = {
            "format": image.format,
            "mode": image.mode,
            "size": image.size,
        }

        # Preprocess for better OCR
        if preprocess:
            image = _preprocess_image(image)

        # Run OCR with detailed output
        ocr_data = pytesseract.image_to_data(
            image,
            lang=language,
            output_type=pytesseract.Output.DICT,
        )

        # Extract text and calculate confidence
        texts = []
        confidences = []

        for i, text in enumerate(ocr_data["text"]):
            if text.strip():
                texts.append(text)
                conf = ocr_data["conf"][i]
                if conf > 0:  # -1 means no confidence
                    confidences.append(conf)

        result.text = " ".join(texts)
        result.text = _clean_ocr_text(result.text)
        result.word_count = len(result.text.split())
        result.has_text = result.word_count > 0

        if confidences:
            result.confidence = sum(confidences) / len(confidences) / 100.0

    except Exception as e:
        result.metadata["error"] = str(e)

    return result


def _preprocess_image(image):
    """Preprocess image for better OCR results."""
    from PIL import Image, ImageEnhance, ImageFilter

    # Convert to RGB if necessary
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Convert to grayscale
    image = image.convert("L")

    # Increase contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)

    # Increase sharpness
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(2.0)

    # Apply slight blur to reduce noise
    image = image.filter(ImageFilter.MedianFilter(size=3))

    # Binarize (convert to pure black and white)
    threshold = 128
    image = image.point(lambda p: 255 if p > threshold else 0)

    return image


def _clean_ocr_text(text: str) -> str:
    """Clean up OCR output."""
    if not text:
        return ""

    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)

    # Fix common OCR errors
    replacements = [
        (r"\|", "I"),  # Pipe often misread as I
        (r"(?<=[a-z])0(?=[a-z])", "o"),  # 0 in middle of word -> o
        (r"(?<=[a-z])1(?=[a-z])", "l"),  # 1 in middle of word -> l
        (r"\bOct\b(?=\s*\d)", "Oct"),  # Date fixes
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)

    return text.strip()


def ocr_image_to_text(file_path: Path) -> str:
    """
    Simple function to extract text from an image.

    Args:
        file_path: Path to image file

    Returns:
        Extracted text
    """
    result = ocr_image(file_path)
    return result.text


def batch_ocr_images(
    file_paths: list[Path],
    language: str = "eng",
    show_progress: bool = True,
) -> list[ImageOCRResult]:
    """
    OCR multiple images.

    Args:
        file_paths: List of image paths
        language: OCR language
        show_progress: Whether to show progress

    Returns:
        List of OCR results
    """
    results = []

    for i, path in enumerate(file_paths):
        if show_progress:
            print(f"  OCR [{i+1}/{len(file_paths)}]: {path.name}")

        try:
            result = ocr_image(path, language=language)
            results.append(result)
        except Exception as e:
            results.append(ImageOCRResult(
                file_path=path,
                text="",
                metadata={"error": str(e)},
            ))

    return results


def detect_image_language(file_path: Path) -> str:
    """
    Attempt to detect the language of text in an image.

    Args:
        file_path: Path to image

    Returns:
        Language code (eng, spa, etc.)
    """
    # First try English OCR
    result_eng = ocr_image(file_path, language="eng")

    # If low confidence or few words, try Spanish
    if result_eng.confidence < 0.5 or result_eng.word_count < 5:
        try:
            result_spa = ocr_image(file_path, language="spa")

            if result_spa.confidence > result_eng.confidence:
                return "spa"
        except Exception:
            pass

    return "eng"


def extract_date_from_image(file_path: Path) -> Optional[str]:
    """
    Try to extract a date from image text or EXIF data.

    Args:
        file_path: Path to image

    Returns:
        Date string if found, None otherwise
    """
    from PIL import Image
    from PIL.ExifTags import TAGS

    # Try EXIF data first
    try:
        image = Image.open(file_path)
        exif = image._getexif()

        if exif:
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag in ("DateTime", "DateTimeOriginal", "DateTimeDigitized"):
                    # Format: "YYYY:MM:DD HH:MM:SS"
                    if isinstance(value, str) and len(value) >= 10:
                        date_part = value[:10].replace(":", "-")
                        return date_part
    except Exception:
        pass

    # Try OCR for date
    try:
        result = ocr_image(file_path)
        text = result.text

        # Look for date patterns
        patterns = [
            r"(\d{4}[-/]\d{2}[-/]\d{2})",  # YYYY-MM-DD
            r"(\d{2}[-/]\d{2}[-/]\d{4})",  # MM-DD-YYYY
            r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",  # M/D/YY
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

    except Exception:
        pass

    return None
