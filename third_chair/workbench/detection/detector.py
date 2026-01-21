"""Main connection detection orchestrator for the Evidence Workbench."""

from pathlib import Path
from typing import Optional

from ..config import get_workbench_config
from ..database import get_workbench_db
from ..embedding.similarity import find_similar_pairs
from ..models import ConnectionType, SuggestedConnection
from .inconsistency import detect_inconsistencies
from .timeline import detect_timeline_conflicts


class ConnectionDetector:
    """Orchestrates connection detection across all detection types."""

    def __init__(self, case_dir: Path, model: Optional[str] = None):
        """Initialize the detector.

        Args:
            case_dir: Path to the case directory
            model: Optional model override for LLM detection
        """
        self.case_dir = case_dir
        self.model = model
        self.config = get_workbench_config()
        self.db = get_workbench_db(case_dir)

    def close(self) -> None:
        """Close database connection."""
        self.db.close()

    def detect_all(
        self,
        types: Optional[list[str]] = None,
        show_progress: bool = True,
    ) -> dict[str, int]:
        """Run all detection passes.

        Args:
            types: Optional list of detection types to run
                   (inconsistency, timeline). If None, runs all.
            show_progress: Whether to show progress output

        Returns:
            Dict mapping detection type to number of connections found
        """
        if types is None:
            types = ["inconsistency", "timeline"]

        results: dict[str, int] = {}

        # Set up progress display
        console = None
        if show_progress:
            try:
                from rich.console import Console

                console = Console()
            except ImportError:
                pass

        # Run inconsistency detection
        if "inconsistency" in types:
            if console:
                console.print("[bold]Detecting inconsistencies...[/bold]")

            connections = self._detect_inconsistencies(console)
            results["inconsistency"] = len(connections)

            if console:
                console.print(f"  Found {len(connections)} potential inconsistencies")

        # Run timeline conflict detection
        if "timeline" in types:
            if console:
                console.print("[bold]Detecting timeline conflicts...[/bold]")

            connections = self._detect_timeline_conflicts(console)
            results["timeline"] = len(connections)

            if console:
                console.print(f"  Found {len(connections)} timeline conflicts")

        return results

    def _detect_inconsistencies(self, console=None) -> list[SuggestedConnection]:
        """Run inconsistency detection pass."""
        # Get all embeddings
        embeddings = self.db.get_all_embeddings()

        if len(embeddings) < 2:
            if console:
                console.print("  Not enough embeddings for comparison")
            return []

        if console:
            console.print(f"  Comparing {len(embeddings)} extractions...")

        # Find similar pairs
        candidate_pairs = find_similar_pairs(
            embeddings,
            threshold=self.config.similarity_threshold,
        )

        if console:
            console.print(f"  Found {len(candidate_pairs)} similar pairs to analyze")

        if not candidate_pairs:
            return []

        # Clear existing inconsistency connections
        self.db.delete_connections_by_type(ConnectionType.INCONSISTENT_STATEMENT)
        self.db.delete_connections_by_type(ConnectionType.CORROBORATES)

        # Detect inconsistencies
        connections = detect_inconsistencies(
            db=self.db,
            candidate_pairs=candidate_pairs,
            model=self.model,
        )

        # Store connections
        if connections:
            self.db.add_connections_batch(connections)

        return connections

    def _detect_timeline_conflicts(self, console=None) -> list[SuggestedConnection]:
        """Run timeline conflict detection pass."""
        # Clear existing timeline conflict connections
        self.db.delete_connections_by_type(ConnectionType.TEMPORAL_CONFLICT)

        # Detect timeline conflicts
        connections = detect_timeline_conflicts(
            db=self.db,
            model=self.model,
        )

        # Store connections
        if connections:
            self.db.add_connections_batch(connections)

        return connections


def detect_connections(
    case_dir: Path,
    types: Optional[list[str]] = None,
    model: Optional[str] = None,
    show_progress: bool = True,
) -> dict[str, int]:
    """Detect connections between extractions in a case.

    Args:
        case_dir: Path to the case directory
        types: Optional list of detection types (inconsistency, timeline)
        model: Optional model override
        show_progress: Whether to show progress output

    Returns:
        Dict mapping detection type to number of connections found
    """
    # Verify workbench is initialized
    db = get_workbench_db(case_dir)
    if not db.is_initialized():
        raise RuntimeError("Workbench not initialized. Run 'workbench init' first.")

    # Check for extractions and embeddings
    extraction_count = db.get_extraction_count()
    embedding_count = db.get_embedding_count()
    db.close()

    if extraction_count == 0:
        raise RuntimeError("No extractions found. Run 'workbench extract' first.")

    if embedding_count == 0:
        raise RuntimeError("No embeddings found. Run 'workbench embed' first.")

    # Run detection
    detector = ConnectionDetector(case_dir, model=model)
    results = detector.detect_all(types=types, show_progress=show_progress)
    detector.close()

    return results
