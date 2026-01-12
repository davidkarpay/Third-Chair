"""Third Chair - Legal Discovery Processing Tool."""

__version__ = "0.1.0"
__author__ = "David Karpay"

from .models import Case, EvidenceItem, Transcript, Witness

__all__ = [
    "__version__",
    "Case",
    "EvidenceItem",
    "Transcript",
    "Witness",
]
