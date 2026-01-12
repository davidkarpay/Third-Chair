"""ZIP file extraction for Axon evidence packages."""

import zipfile
from pathlib import Path
from typing import Optional

from rich.progress import Progress, SpinnerColumn, TextColumn

from ..models import Case


def extract_axon_zip(
    zip_path: Path,
    output_dir: Path,
    case_id: Optional[str] = None,
    show_progress: bool = True,
) -> Case:
    """
    Extract an Axon evidence ZIP file and create a Case object.

    Args:
        zip_path: Path to the ZIP file
        output_dir: Directory to extract files to
        case_id: Optional case ID (extracted from filename if not provided)
        show_progress: Whether to show progress bar

    Returns:
        Case object with metadata populated
    """
    if not zip_path.exists():
        raise FileNotFoundError(f"ZIP file not found: {zip_path}")

    if not zipfile.is_zipfile(zip_path):
        raise ValueError(f"Not a valid ZIP file: {zip_path}")

    # Create output directory structure
    extracted_dir = output_dir / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    # Compute source hash for chain of custody
    source_hash = Case.compute_file_hash(zip_path)

    # Extract case ID from filename if not provided
    if case_id is None:
        case_id = _extract_case_id_from_filename(zip_path.stem)

    # Create case object
    case = Case(
        case_id=case_id,
        source_zip=zip_path.name,
        source_hash=source_hash,
        output_dir=output_dir,
    )

    # Extract files
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.namelist()

        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                task = progress.add_task(f"Extracting {len(members)} files...", total=len(members))

                for member in members:
                    _extract_member(zf, member, extracted_dir)
                    progress.advance(task)
        else:
            for member in members:
                _extract_member(zf, member, extracted_dir)

    return case


def _extract_member(zf: zipfile.ZipFile, member: str, output_dir: Path) -> Optional[Path]:
    """
    Extract a single member from a ZIP file.

    Handles nested directories and skips problematic entries.
    """
    # Skip directories and hidden files
    if member.endswith("/") or member.startswith("__MACOSX"):
        return None

    # Skip hidden files
    basename = Path(member).name
    if basename.startswith("."):
        return None

    try:
        # Extract to output directory, preserving structure
        zf.extract(member, output_dir)
        return output_dir / member
    except (zipfile.BadZipFile, OSError) as e:
        # Log but don't fail on individual file errors
        print(f"Warning: Could not extract {member}: {e}")
        return None


def _extract_case_id_from_filename(filename: str) -> str:
    """
    Extract case ID from Axon ZIP filename.

    Axon filenames often follow patterns like:
    - Case_2025-12345_Evidence.zip
    - 2025-CF-001234_Export.zip
    - Evidence_Export_20250115.zip
    """
    import re

    # Pattern: Case number with year prefix
    patterns = [
        r"Case[_-]?(\d{4}[_-]\d+)",  # Case_2025-12345
        r"(\d{4}[_-]CF[_-]\d+)",  # 2025-CF-001234
        r"(\d{4}[_-]MM[_-]\d+)",  # 2025-MM-001234
        r"(\d{4}[_-]\d{5,})",  # 2025-12345
    ]

    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return match.group(1).replace("_", "-")

    # Fallback: use filename stem
    return filename[:30] if len(filename) > 30 else filename


def list_zip_contents(zip_path: Path) -> list[dict]:
    """
    List contents of a ZIP file without extracting.

    Returns list of dicts with file info.
    """
    if not zip_path.exists():
        raise FileNotFoundError(f"ZIP file not found: {zip_path}")

    contents = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir() or info.filename.startswith("__MACOSX"):
                continue

            contents.append({
                "filename": info.filename,
                "size_bytes": info.file_size,
                "compressed_size": info.compress_size,
                "date_time": info.date_time,
            })

    return contents
