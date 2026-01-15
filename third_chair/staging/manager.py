"""Staging manager for Axon ZIP file import workflow."""

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from ..models import Case
from ..utils.logging import get_logger
from .preview import ZipPreview, preview_axon_zip

logger = get_logger(__name__)


@dataclass
class StagingStatus:
    """Status of the staging area."""

    incoming_count: int = 0
    processing_count: int = 0
    failed_count: int = 0
    incoming_files: list[Path] = field(default_factory=list)
    processing_files: list[Path] = field(default_factory=list)
    failed_files: list[Path] = field(default_factory=list)


@dataclass
class ProcessingResult:
    """Result of processing a staged ZIP."""

    success: bool
    case: Optional[Case] = None
    error: Optional[str] = None
    zip_path: Path = field(default_factory=Path)
    output_dir: Optional[Path] = None


class StagingManager:
    """
    Manages the staging workflow for Axon ZIP imports.

    Directory structure:
        staging/
        ├── incoming/     # Drop ZIPs here
        ├── processing/   # Currently being ingested
        └── failed/       # Failed imports with error logs
    """

    def __init__(
        self,
        staging_dir: Path,
        cases_dir: Path,
    ) -> None:
        """
        Initialize the staging manager.

        Args:
            staging_dir: Root staging directory.
            cases_dir: Directory where completed cases are stored.
        """
        self.staging_dir = Path(staging_dir)
        self.cases_dir = Path(cases_dir)

        # Subdirectories
        self.incoming_dir = self.staging_dir / "incoming"
        self.processing_dir = self.staging_dir / "processing"
        self.failed_dir = self.staging_dir / "failed"

        # Ensure directories exist
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create staging directories if they don't exist."""
        self.incoming_dir.mkdir(parents=True, exist_ok=True)
        self.processing_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)
        self.cases_dir.mkdir(parents=True, exist_ok=True)

    def scan_incoming(self) -> list[ZipPreview]:
        """
        Find all ZIP files in incoming/ folder.

        Returns:
            List of ZipPreview objects for each ZIP found.
        """
        previews = []

        for zip_file in self.incoming_dir.glob("*.zip"):
            try:
                preview = preview_axon_zip(zip_file)
                previews.append(preview)
            except Exception as e:
                logger.error(f"Error previewing {zip_file}: {e}")
                # Create error preview
                previews.append(ZipPreview(
                    zip_path=zip_file,
                    zip_size_mb=zip_file.stat().st_size / (1024 * 1024) if zip_file.exists() else 0.0,
                    case_id="error",
                    validation_errors=[str(e)],
                ))

        # Sort by modification time (newest first)
        previews.sort(
            key=lambda p: p.zip_path.stat().st_mtime if p.zip_path.exists() else 0,
            reverse=True,
        )

        return previews

    def preview_zip(self, zip_path: Path) -> ZipPreview:
        """
        Get preview for a specific ZIP file.

        Args:
            zip_path: Path to the ZIP file.

        Returns:
            ZipPreview with metadata.
        """
        return preview_axon_zip(zip_path)

    def process_zip(
        self,
        zip_path: Path,
        case_id: Optional[str] = None,
        court_case: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> ProcessingResult:
        """
        Process a staged ZIP file.

        Moves the file through the staging workflow:
        1. incoming/ → processing/
        2. Run ingest
        3. processing/ → cases/ (success) or failed/ (error)

        Args:
            zip_path: Path to the ZIP file in incoming/.
            case_id: Optional override for case ID.
            court_case: Optional court case number.
            progress_callback: Optional callback(stage, progress) for updates.

        Returns:
            ProcessingResult with case or error.
        """
        # Lazy import to avoid circular dependencies
        from ..ingest import ingest_axon_package

        def report_progress(stage: str, progress: float) -> None:
            if progress_callback:
                progress_callback(stage, progress)

        zip_path = Path(zip_path)

        if not zip_path.exists():
            return ProcessingResult(
                success=False,
                error=f"File not found: {zip_path}",
                zip_path=zip_path,
            )

        # Get preview for case ID if not provided
        if not case_id:
            preview = preview_axon_zip(zip_path)
            case_id = preview.case_id

        # Create processing directory
        processing_subdir = self.processing_dir / case_id
        processing_subdir.mkdir(parents=True, exist_ok=True)

        # Move ZIP to processing
        report_progress("Moving to processing", 0.1)
        processing_zip = processing_subdir / zip_path.name

        try:
            shutil.move(str(zip_path), str(processing_zip))
        except Exception as e:
            return ProcessingResult(
                success=False,
                error=f"Failed to move to processing: {e}",
                zip_path=zip_path,
            )

        # Create output directory in cases/
        output_dir = self.cases_dir / case_id
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Run ingest
            report_progress("Extracting files", 0.2)
            case = ingest_axon_package(
                zip_path=processing_zip,
                output_dir=output_dir,
                case_id=case_id,
                court_case=court_case,
                show_progress=False,  # We handle progress ourselves
            )

            report_progress("Ingest complete", 0.9)

            # Clean up processing directory
            shutil.rmtree(processing_subdir, ignore_errors=True)

            report_progress("Done", 1.0)

            logger.info(f"Successfully processed {zip_path.name} → {case_id}")

            return ProcessingResult(
                success=True,
                case=case,
                zip_path=zip_path,
                output_dir=output_dir,
            )

        except Exception as e:
            logger.error(f"Failed to process {zip_path.name}: {e}")

            # Move to failed/
            failed_subdir = self.failed_dir / case_id
            failed_subdir.mkdir(parents=True, exist_ok=True)

            # Move ZIP and create error log
            try:
                shutil.move(str(processing_zip), str(failed_subdir / zip_path.name))
            except Exception:
                pass

            # Write error log
            error_log = failed_subdir / "error.json"
            error_data = {
                "zip_file": zip_path.name,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            with open(error_log, "w") as f:
                json.dump(error_data, f, indent=2)

            # Clean up processing directory
            shutil.rmtree(processing_subdir, ignore_errors=True)

            return ProcessingResult(
                success=False,
                error=str(e),
                zip_path=zip_path,
            )

    def get_status(self) -> StagingStatus:
        """
        Get current staging area status.

        Returns:
            StagingStatus with counts and file lists.
        """
        incoming = list(self.incoming_dir.glob("*.zip"))
        processing = list(self.processing_dir.iterdir()) if self.processing_dir.exists() else []
        failed = list(self.failed_dir.iterdir()) if self.failed_dir.exists() else []

        return StagingStatus(
            incoming_count=len(incoming),
            processing_count=len([d for d in processing if d.is_dir()]),
            failed_count=len([d for d in failed if d.is_dir()]),
            incoming_files=incoming,
            processing_files=[d for d in processing if d.is_dir()],
            failed_files=[d for d in failed if d.is_dir()],
        )

    def delete_from_incoming(self, zip_path: Path) -> bool:
        """
        Delete a ZIP from incoming/ folder.

        Args:
            zip_path: Path to the ZIP file.

        Returns:
            True if deleted, False otherwise.
        """
        try:
            if zip_path.exists() and zip_path.parent == self.incoming_dir:
                zip_path.unlink()
                logger.info(f"Deleted {zip_path.name} from incoming")
                return True
        except Exception as e:
            logger.error(f"Failed to delete {zip_path}: {e}")
        return False

    def retry_failed(self, case_id: str) -> Optional[ProcessingResult]:
        """
        Retry processing a failed ZIP.

        Moves the ZIP back to incoming/ and processes it.

        Args:
            case_id: Case ID of the failed import.

        Returns:
            ProcessingResult or None if not found.
        """
        failed_subdir = self.failed_dir / case_id

        if not failed_subdir.exists():
            return None

        # Find the ZIP file
        zips = list(failed_subdir.glob("*.zip"))
        if not zips:
            return None

        zip_path = zips[0]

        # Move back to incoming
        incoming_path = self.incoming_dir / zip_path.name
        try:
            shutil.move(str(zip_path), str(incoming_path))
            shutil.rmtree(failed_subdir, ignore_errors=True)
        except Exception as e:
            logger.error(f"Failed to move {zip_path} for retry: {e}")
            return None

        # Process
        return self.process_zip(incoming_path, case_id=case_id)

    def clear_failed(self, case_id: Optional[str] = None) -> int:
        """
        Clear failed imports.

        Args:
            case_id: Specific case ID to clear, or None to clear all.

        Returns:
            Number of items cleared.
        """
        cleared = 0

        if case_id:
            failed_subdir = self.failed_dir / case_id
            if failed_subdir.exists():
                shutil.rmtree(failed_subdir)
                cleared = 1
        else:
            for subdir in self.failed_dir.iterdir():
                if subdir.is_dir():
                    shutil.rmtree(subdir)
                    cleared += 1

        return cleared
