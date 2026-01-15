"""File watcher for staging area auto-detection."""

import threading
import time
from pathlib import Path
from typing import Callable, Optional, Set

from ..utils.logging import get_logger
from .manager import StagingManager
from .preview import ZipPreview

logger = get_logger(__name__)


class StagingWatcher:
    """
    Watches the staging/incoming/ folder for new ZIP files.

    Uses polling-based detection (more reliable across platforms than
    filesystem events, especially on WSL2).
    """

    def __init__(
        self,
        manager: StagingManager,
        on_new_zip: Callable[[ZipPreview], None],
        poll_interval: float = 5.0,
        auto_process: bool = True,
        on_process_complete: Optional[Callable[[str, bool], None]] = None,
    ) -> None:
        """
        Initialize the staging watcher.

        Args:
            manager: StagingManager instance.
            on_new_zip: Callback when a new ZIP is detected.
            poll_interval: Seconds between directory scans.
            auto_process: If True, automatically process new ZIPs.
            on_process_complete: Callback(case_id, success) when processing completes.
        """
        self.manager = manager
        self.on_new_zip = on_new_zip
        self.poll_interval = poll_interval
        self.auto_process = auto_process
        self.on_process_complete = on_process_complete

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._known_files: Set[Path] = set()
        self._processing_lock = threading.Lock()
        self._currently_processing: Set[Path] = set()

    def start(self) -> None:
        """Start watching in background thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Watcher already running")
            return

        # Initialize known files to avoid processing existing files
        self._known_files = set(self.manager.incoming_dir.glob("*.zip"))

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info(f"Started staging watcher on {self.manager.incoming_dir}")

    def stop(self) -> None:
        """Stop the watcher."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.poll_interval + 1)
            self._thread = None
        logger.info("Stopped staging watcher")

    def is_running(self) -> bool:
        """Check if the watcher is running."""
        return self._thread is not None and self._thread.is_alive()

    def _watch_loop(self) -> None:
        """Main watch loop running in background thread."""
        while not self._stop_event.is_set():
            try:
                self._scan_for_new_files()
            except Exception as e:
                logger.error(f"Error in watcher loop: {e}")

            self._stop_event.wait(self.poll_interval)

    def _scan_for_new_files(self) -> None:
        """Scan for new ZIP files."""
        current_files = set(self.manager.incoming_dir.glob("*.zip"))
        new_files = current_files - self._known_files

        for zip_path in new_files:
            # Skip files currently being processed
            with self._processing_lock:
                if zip_path in self._currently_processing:
                    continue

            # Check if file is still being written (size stable)
            if not self._is_file_ready(zip_path):
                continue

            logger.info(f"New ZIP detected: {zip_path.name}")
            self._known_files.add(zip_path)

            try:
                preview = self.manager.preview_zip(zip_path)
                self.on_new_zip(preview)

                if self.auto_process:
                    self._process_in_background(zip_path)

            except Exception as e:
                logger.error(f"Error handling new ZIP {zip_path}: {e}")

        # Remove files that no longer exist
        self._known_files = current_files

    def _is_file_ready(self, path: Path, stability_seconds: float = 2.0) -> bool:
        """
        Check if a file is ready (not still being copied).

        Args:
            path: Path to check.
            stability_seconds: Time to wait for size stability.

        Returns:
            True if file appears complete.
        """
        try:
            size1 = path.stat().st_size
            time.sleep(stability_seconds)
            size2 = path.stat().st_size
            return size1 == size2 and size1 > 0
        except OSError:
            return False

    def _process_in_background(self, zip_path: Path) -> None:
        """Process a ZIP file in background thread."""
        def do_process():
            with self._processing_lock:
                self._currently_processing.add(zip_path)

            try:
                result = self.manager.process_zip(zip_path)

                if self.on_process_complete:
                    case_id = result.case.case_id if result.case else zip_path.stem
                    self.on_process_complete(case_id, result.success)

            except Exception as e:
                logger.error(f"Background processing failed for {zip_path}: {e}")
                if self.on_process_complete:
                    self.on_process_complete(zip_path.stem, False)

            finally:
                with self._processing_lock:
                    self._currently_processing.discard(zip_path)

        thread = threading.Thread(target=do_process, daemon=True)
        thread.start()

    def process_now(self, zip_path: Path) -> None:
        """
        Manually trigger processing of a specific ZIP.

        Args:
            zip_path: Path to the ZIP file.
        """
        if zip_path not in self._known_files:
            self._known_files.add(zip_path)

        self._process_in_background(zip_path)

    @property
    def pending_count(self) -> int:
        """Number of ZIPs waiting to be processed."""
        with self._processing_lock:
            return len(self._known_files) - len(self._currently_processing)
