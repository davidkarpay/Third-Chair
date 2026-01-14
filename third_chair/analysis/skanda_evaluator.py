"""Skanda Evaluator for the Skanda Framework.

Implements deterministic evaluation of propositions:
- holds_under_scrutiny: yes/no/uncertain
- weight: 0.0-1.0 for attention priority
- probative_value: relative to material issue
- burden_contribution: toward meeting the standard

The evaluator is deterministic and outputs explanations citing driver proposits.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..models import (
    BurdenContribution,
    Case,
    EvaluationDrivers,
    EvaluationSnapshot,
    HoldsStatus,
    Polarity,
    Proposition,
    PropositionKind,
    PropositionTest,
    Proposit,
    TestResult,
)


@dataclass
class EvaluationConfig:
    """Configuration for proposition evaluation."""
    # Thresholds for holds_under_scrutiny
    holds_threshold: float = 0.3  # support - undermine > threshold -> HOLDS
    fails_threshold: float = -0.3  # support - undermine < threshold -> FAILS

    # Weight computation
    base_weight: float = 0.5
    corroboration_bonus: float = 0.1
    contradiction_penalty: float = 0.15
    low_confidence_penalty: float = 0.2

    # Confidence thresholds
    min_confidence_threshold: float = 0.85


class SkandaEvaluator:
    """
    Evaluates propositions deterministically.

    The evaluator runs tests on each proposit and computes:
    - holds_under_scrutiny
    - weight
    - probative_value
    - burden_contribution

    All computations are deterministic and cite driver proposits.
    """

    def __init__(self, case: Case, config: Optional[EvaluationConfig] = None):
        """
        Initialize the evaluator.

        Args:
            case: The case context for corroboration checks
            config: Evaluation configuration
        """
        self.case = case
        self.config = config or EvaluationConfig()

    def evaluate(self, proposition: Proposition) -> EvaluationSnapshot:
        """
        Evaluate a proposition and return an evaluation snapshot.

        Args:
            proposition: The proposition to evaluate

        Returns:
            EvaluationSnapshot with computed values
        """
        # Step 1: Run tests on all proposits
        self._run_proposit_tests(proposition)

        # Step 2: Compute scores
        support_score = proposition.skanda.support_score
        undermine_score = proposition.skanda.undermine_score
        net_score = support_score - undermine_score

        # Step 3: Determine holds_under_scrutiny
        holds_status = self._compute_holds_status(net_score, proposition)

        # Step 4: Compute weight
        weight = self._compute_weight(proposition)

        # Step 5: Compute probative_value
        probative_value = self._compute_probative_value(proposition)

        # Step 6: Compute burden_contribution
        burden_contribution = self._compute_burden_contribution(
            proposition, holds_status, weight, probative_value
        )

        # Step 7: Identify drivers
        drivers = self._identify_drivers(proposition)

        # Step 8: Collect review flags
        review_flags = self._collect_review_flags(proposition)

        return EvaluationSnapshot(
            as_of=datetime.now(),
            holds_under_scrutiny=holds_status,
            weight=weight,
            probative_value=probative_value,
            burden_contribution=burden_contribution,
            drivers=drivers,
            human_review_flags=review_flags,
        )

    def _run_proposit_tests(self, proposition: Proposition) -> None:
        """Run tests on all proposits in the skanda."""
        for proposit in proposition.skanda.proposits:
            tests = []

            # Test: Personal knowledge
            personal_knowledge_test = self._test_personal_knowledge(proposit)
            tests.append(personal_knowledge_test)

            # Test: Transcript confidence
            confidence_test = self._test_transcript_confidence(proposit)
            tests.append(confidence_test)

            # Test: Source reliability
            reliability_test = self._test_source_reliability(proposit)
            tests.append(reliability_test)

            # Test: Corroboration
            corroboration_test = self._test_corroboration(proposit, proposition)
            tests.append(corroboration_test)

            # Test: Contradiction
            contradiction_test = self._test_contradiction(proposit, proposition)
            tests.append(contradiction_test)

            # Test: Speaker verified
            speaker_test = self._test_speaker_verified(proposit)
            tests.append(speaker_test)

            proposit.tests = tests

            # Update proposit weight based on test results
            proposit.weight = self._compute_proposit_weight(proposit, tests)

    def _test_personal_knowledge(self, proposit: Proposit) -> PropositionTest:
        """Test whether the proposit demonstrates personal knowledge."""
        claim_lower = proposit.claim.lower()

        # Check for perception verbs
        perception_indicators = [
            "i saw", "i heard", "i watched", "i noticed", "i observed",
            "i felt", "i witnessed", "i was there"
        ]

        has_perception = any(ind in claim_lower for ind in perception_indicators)

        if has_perception:
            return PropositionTest(
                test_id="t_personal_knowledge",
                name="Personal knowledge",
                method="classify_personal_knowledge_from_language",
                result=TestResult.PASS,
                reason="Uses perception verbs indicating contemporaneous observation",
            )

        # Check for hearsay indicators
        hearsay_indicators = ["told me", "said that", "i heard that", "they said"]
        has_hearsay = any(ind in claim_lower for ind in hearsay_indicators)

        if has_hearsay:
            return PropositionTest(
                test_id="t_personal_knowledge",
                name="Personal knowledge",
                method="classify_personal_knowledge_from_language",
                result=TestResult.WARN,
                reason="Contains hearsay indicators; may not be based on personal knowledge",
            )

        return PropositionTest(
            test_id="t_personal_knowledge",
            name="Personal knowledge",
            method="classify_personal_knowledge_from_language",
            result=TestResult.PASS,
            reason="No hearsay indicators detected",
        )

    def _test_transcript_confidence(self, proposit: Proposit) -> PropositionTest:
        """Test transcript confidence threshold."""
        # Get confidence from evidence ref metadata if available
        for ref in proposit.evidence_refs:
            if ref.source_type == "transcript_segment":
                # We don't store confidence in EvidenceRef, so we check the case
                evidence = self.case.get_evidence(ref.evidence_id)
                if evidence and evidence.transcript:
                    for segment in evidence.transcript.segments:
                        if segment.start_time == ref.start_time_seconds:
                            if segment.confidence < self.config.min_confidence_threshold:
                                return PropositionTest(
                                    test_id="t_transcript_confidence",
                                    name="Transcript confidence",
                                    method="min_segment_confidence_threshold",
                                    result=TestResult.WARN,
                                    reason=f"Segment confidence is {segment.confidence:.2f}; review audio",
                                    parameters={"threshold": self.config.min_confidence_threshold},
                                )

        return PropositionTest(
            test_id="t_transcript_confidence",
            name="Transcript confidence",
            method="min_segment_confidence_threshold",
            result=TestResult.PASS,
            reason="Transcript confidence meets threshold",
            parameters={"threshold": self.config.min_confidence_threshold},
        )

    def _test_source_reliability(self, proposit: Proposit) -> PropositionTest:
        """Test source reliability based on evidence type."""
        source_types = [ref.source_type for ref in proposit.evidence_refs]

        # Rank reliability
        high_reliability = ["transcript_segment", "image"]
        medium_reliability = ["document_span", "timeline_event"]

        if any(st in high_reliability for st in source_types):
            return PropositionTest(
                test_id="t_source_reliability",
                name="Source type reliability",
                method="source_reliability_profile",
                result=TestResult.PASS,
                reason="Based on contemporaneous recording/observation",
            )

        if any(st in medium_reliability for st in source_types):
            return PropositionTest(
                test_id="t_source_reliability",
                name="Source type reliability",
                method="source_reliability_profile",
                result=TestResult.WARN,
                reason="Based on document or derived timeline; verify against primary sources",
            )

        return PropositionTest(
            test_id="t_source_reliability",
            name="Source type reliability",
            method="source_reliability_profile",
            result=TestResult.WARN,
            reason="Unknown source type; manual review needed",
        )

    def _test_corroboration(self, proposit: Proposit, proposition: Proposition) -> PropositionTest:
        """Test whether the proposit is corroborated by other proposits."""
        # Count how many other proposits with same polarity exist
        same_polarity = [
            p for p in proposition.skanda.proposits
            if p.id != proposit.id and p.polarity == proposit.polarity
        ]

        if len(same_polarity) >= 2:
            return PropositionTest(
                test_id="t_corroboration",
                name="Corroboration",
                method="count_independent_sources",
                result=TestResult.PASS,
                reason=f"Corroborated by {len(same_polarity)} other proposits",
            )

        if len(same_polarity) == 1:
            return PropositionTest(
                test_id="t_corroboration",
                name="Corroboration",
                method="count_independent_sources",
                result=TestResult.WARN,
                reason="Only one other supporting proposit found",
            )

        return PropositionTest(
            test_id="t_corroboration",
            name="Corroboration",
            method="count_independent_sources",
            result=TestResult.WARN,
            reason="No corroborating proposits found",
        )

    def _test_contradiction(self, proposit: Proposit, proposition: Proposition) -> PropositionTest:
        """Test whether the proposit is contradicted by other proposits."""
        # Find proposits with opposite polarity
        opposite_polarity = [
            p for p in proposition.skanda.proposits
            if p.polarity != proposit.polarity
        ]

        if len(opposite_polarity) == 0:
            return PropositionTest(
                test_id="t_contradiction",
                name="Contradiction",
                method="find_opposing_polarity",
                result=TestResult.PASS,
                reason="No contradicting proposits found",
            )

        return PropositionTest(
            test_id="t_contradiction",
            name="Contradiction",
            method="find_opposing_polarity",
            result=TestResult.WARN,
            reason=f"Found {len(opposite_polarity)} contradicting proposit(s)",
        )

    def _test_speaker_verified(self, proposit: Proposit) -> PropositionTest:
        """Test whether the speaker is verified in the witness list."""
        for ref in proposit.evidence_refs:
            if ref.speaker:
                # Check if speaker is in verified witness list
                witness = self.case.witnesses.get_by_speaker_id(ref.speaker)
                if witness and witness.verified:
                    return PropositionTest(
                        test_id="t_speaker_verified",
                        name="Speaker verified",
                        method="check_witness_module",
                        result=TestResult.PASS,
                        reason=f"Speaker verified as {witness.name or witness.id}",
                    )

                if witness and not witness.verified:
                    return PropositionTest(
                        test_id="t_speaker_verified",
                        name="Speaker verified",
                        method="check_witness_module",
                        result=TestResult.WARN,
                        reason="Speaker identified but not verified",
                    )

        return PropositionTest(
            test_id="t_speaker_verified",
            name="Speaker verified",
            method="check_witness_module",
            result=TestResult.WARN,
            reason="Speaker not in witness list",
        )

    def _compute_proposit_weight(
        self,
        proposit: Proposit,
        tests: list[PropositionTest],
    ) -> float:
        """Compute weight for a proposit based on test results."""
        weight = self.config.base_weight

        # Count test results
        pass_count = sum(1 for t in tests if t.result == TestResult.PASS)
        warn_count = sum(1 for t in tests if t.result == TestResult.WARN)
        fail_count = sum(1 for t in tests if t.result == TestResult.FAIL)

        # Adjust weight
        weight += pass_count * 0.05
        weight -= warn_count * 0.1
        weight -= fail_count * 0.3

        # Kind-based adjustments
        if proposit.kind == PropositionKind.DIRECT_OBSERVATION:
            weight += 0.1
        elif proposit.kind == PropositionKind.INFERENCE:
            weight -= 0.1

        # Clamp to [0.1, 1.0]
        return max(0.1, min(1.0, weight))

    def _compute_holds_status(
        self,
        net_score: float,
        proposition: Proposition,
    ) -> HoldsStatus:
        """
        Compute holds_under_scrutiny based on net score.

        Simple decision rule:
        - If support - undermine > threshold and no critical dependency failed: HOLDS
        - If undermine - support > threshold: FAILS
        - Else: UNCERTAIN
        """
        # Check for critical failures
        for proposit in proposition.skanda.proposits:
            for test in proposit.tests:
                if test.result == TestResult.FAIL:
                    # Critical failure in any proposit -> uncertain at best
                    if net_score > self.config.holds_threshold:
                        return HoldsStatus.UNCERTAIN
                    return HoldsStatus.FAILS

        if net_score > self.config.holds_threshold:
            return HoldsStatus.HOLDS
        elif net_score < self.config.fails_threshold:
            return HoldsStatus.FAILS
        else:
            return HoldsStatus.UNCERTAIN

    def _compute_weight(self, proposition: Proposition) -> float:
        """
        Compute overall weight (attention priority) for the proposition.

        Weight combines:
        - Source reliability
        - Corroboration count
        - Specificity
        - Review flags
        """
        if not proposition.skanda.proposits:
            return 0.0

        # Average proposit weights
        avg_weight = sum(p.weight for p in proposition.skanda.proposits) / len(proposition.skanda.proposits)

        # Boost for corroboration
        supporting_count = len(proposition.skanda.supporting)
        if supporting_count >= 3:
            avg_weight += self.config.corroboration_bonus * 2
        elif supporting_count >= 2:
            avg_weight += self.config.corroboration_bonus

        # Penalty for contradictions
        undermining_count = len(proposition.skanda.undermining)
        avg_weight -= undermining_count * self.config.contradiction_penalty

        return max(0.0, min(1.0, avg_weight))

    def _compute_probative_value(self, proposition: Proposition) -> float:
        """
        Compute probative value relative to material issue.

        Higher if proposition directly addresses issue elements.
        """
        if not proposition.material_issue.elements:
            return 0.3  # Default low if no elements defined

        # For now, use a heuristic based on number of elements addressed
        # A real implementation would check if proposits address specific elements
        base_value = 0.5

        # Boost if we have strong supporting evidence
        if proposition.skanda.support_score > proposition.skanda.undermine_score:
            base_value += 0.2

        return min(1.0, base_value)

    def _compute_burden_contribution(
        self,
        proposition: Proposition,
        holds_status: HoldsStatus,
        weight: float,
        probative_value: float,
    ) -> BurdenContribution:
        """
        Compute burden contribution toward meeting the standard.

        Models: "If I accept this proposition, how much does it move
        the proponent toward meeting the standard?"
        """
        # Compute contribution based on holds status and weight
        if holds_status == HoldsStatus.HOLDS:
            contribution = weight * probative_value
            category = "likely_sufficient" if contribution > 0.6 else "borderline"
        elif holds_status == HoldsStatus.UNCERTAIN:
            contribution = weight * probative_value * 0.5
            category = "borderline"
        else:
            contribution = 0.1
            category = "unlikely_sufficient"

        # Generate explanation
        supporting = proposition.skanda.supporting
        undermining = proposition.skanda.undermining

        explanation_parts = []
        if supporting:
            explanation_parts.append(f"Supported by {len(supporting)} proposit(s)")
        if undermining:
            explanation_parts.append(f"Undermined by {len(undermining)} proposit(s)")

        if holds_status == HoldsStatus.HOLDS:
            explanation_parts.append("Evidence holds under scrutiny")
        elif holds_status == HoldsStatus.UNCERTAIN:
            explanation_parts.append("Requires additional corroboration")
        else:
            explanation_parts.append("Evidence does not hold under scrutiny")

        return BurdenContribution(
            toward_proponent=contribution,
            explanation="; ".join(explanation_parts),
            sufficiency_category=category,
        )

    def _identify_drivers(self, proposition: Proposition) -> EvaluationDrivers:
        """Identify top supporting and undermining proposits."""
        # Sort by weight
        supporting = sorted(
            proposition.skanda.supporting,
            key=lambda p: p.weight,
            reverse=True,
        )
        undermining = sorted(
            proposition.skanda.undermining,
            key=lambda p: p.weight,
            reverse=True,
        )

        return EvaluationDrivers(
            top_supporting=[p.id for p in supporting[:5]],
            top_undermining=[p.id for p in undermining[:5]],
        )

    def _collect_review_flags(self, proposition: Proposition) -> list[str]:
        """Collect human review flags from proposits."""
        flags = set()

        for proposit in proposition.skanda.proposits:
            for test in proposit.tests:
                if test.result == TestResult.WARN:
                    # Generate flag from test
                    flag = f"REVIEW_{test.name.upper().replace(' ', '_')}"
                    flags.add(flag)
                elif test.result == TestResult.FAIL:
                    flag = f"CRITICAL_{test.name.upper().replace(' ', '_')}"
                    flags.add(flag)

        return list(flags)


def evaluate_proposition(
    case: Case,
    proposition: Proposition,
    config: Optional[EvaluationConfig] = None,
) -> EvaluationSnapshot:
    """
    Evaluate a single proposition.

    Args:
        case: The case context
        proposition: The proposition to evaluate
        config: Optional evaluation configuration

    Returns:
        EvaluationSnapshot with computed values
    """
    evaluator = SkandaEvaluator(case, config)
    return evaluator.evaluate(proposition)


def evaluate_all_propositions(
    case: Case,
    config: Optional[EvaluationConfig] = None,
) -> None:
    """
    Evaluate all propositions in a case in-place.

    Args:
        case: The case with propositions to evaluate
        config: Optional evaluation configuration
    """
    evaluator = SkandaEvaluator(case, config)

    for proposition in case.propositions:
        proposition.evaluation = evaluator.evaluate(proposition)
        proposition.modified_at = datetime.now()
