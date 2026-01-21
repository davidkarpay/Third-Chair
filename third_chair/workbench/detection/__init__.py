"""Connection detection pipeline for the Evidence Workbench."""

from .detector import ConnectionDetector, detect_connections
from .inconsistency import detect_inconsistencies
from .timeline import detect_timeline_conflicts

__all__ = [
    "ConnectionDetector",
    "detect_connections",
    "detect_inconsistencies",
    "detect_timeline_conflicts",
]
