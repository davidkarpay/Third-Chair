"""Analysis module for Third Chair.

Provides proposition extraction and evaluation based on the Skanda Framework.
Propositions are evaluated deterministically to compute holds_under_scrutiny,
weight, probative_value, and burden_contribution.
"""

from .proposition_extractor import (
    PropositionExtractor,
    extract_propositions_from_case,
)
from .skanda_evaluator import (
    SkandaEvaluator,
    evaluate_proposition,
    evaluate_all_propositions,
)

__all__ = [
    "PropositionExtractor",
    "extract_propositions_from_case",
    "SkandaEvaluator",
    "evaluate_proposition",
    "evaluate_all_propositions",
]
