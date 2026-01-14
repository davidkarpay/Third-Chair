"""Proposition extractor for the Skanda Framework.

Seeds proposits from existing case data:
- Flagged transcript segments (THREAT_KEYWORD, VIOLENCE_KEYWORD)
- Key statements
- Timeline events
- Vision analysis key findings

Groups proposits into propositions by shared entities, time windows,
and semantic similarity.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..models import (
    BurdenInfo,
    BurdenStandard,
    Case,
    EvidenceRef,
    MaterialIssue,
    MaterialIssueRef,
    Polarity,
    ProponentInfo,
    Proposition,
    PropositionKind,
    Proposit,
    ReviewFlag,
    Skanda,
    MATERIAL_ISSUE_TEMPLATES,
)


@dataclass
class ExtractionConfig:
    """Configuration for proposition extraction."""
    include_threats: bool = True
    include_violence: bool = True
    include_low_confidence: bool = False
    include_timeline: bool = True
    min_confidence: float = 0.5
    default_proponent: str = "Defense"
    default_issue: str = "self_defense"


class PropositionExtractor:
    """
    Extracts proposits from case data and groups into propositions.

    This extractor seeds proposits from:
    - Flagged transcript segments
    - Key statements
    - Timeline events
    - Vision analysis findings

    It then groups proposits into propositions based on:
    - Shared entities (names, speakers)
    - Shared time window
    - Semantic similarity (if embeddings available)
    """

    def __init__(self, case: Case, config: Optional[ExtractionConfig] = None):
        """
        Initialize the extractor.

        Args:
            case: The case to extract propositions from
            config: Extraction configuration
        """
        self.case = case
        self.config = config or ExtractionConfig()
        self._proposit_counter = 0
        self._proposition_counter = 0

    def extract(self) -> list[Proposition]:
        """
        Extract propositions from the case.

        Returns:
            List of propositions with their skandas
        """
        # Step 1: Extract all proposits from various sources
        proposits = []
        proposits.extend(self._extract_from_flagged_segments())
        proposits.extend(self._extract_from_key_statements())
        proposits.extend(self._extract_from_timeline())
        proposits.extend(self._extract_from_vision_analysis())

        if not proposits:
            return []

        # Step 2: Group proposits into propositions
        propositions = self._group_proposits(proposits)

        return propositions

    def _next_proposit_id(self) -> str:
        """Generate next proposit ID."""
        self._proposit_counter += 1
        return f"pz_{self._proposit_counter:04d}"

    def _next_proposition_id(self) -> str:
        """Generate next proposition ID."""
        self._proposition_counter += 1
        return f"prop_{self._proposition_counter:05d}"

    def _extract_from_flagged_segments(self) -> list[Proposit]:
        """Extract proposits from flagged transcript segments."""
        proposits = []

        for evidence in self.case.evidence_items:
            if not evidence.transcript:
                continue

            for segment in evidence.transcript.segments:
                if not segment.review_flags:
                    continue

                # Check flags based on config
                has_relevant_flag = False
                flags_present = []

                if self.config.include_threats and ReviewFlag.THREAT_KEYWORD in segment.review_flags:
                    has_relevant_flag = True
                    flags_present.append("THREAT")

                if self.config.include_violence and ReviewFlag.VIOLENCE_KEYWORD in segment.review_flags:
                    has_relevant_flag = True
                    flags_present.append("VIOLENCE")

                if self.config.include_low_confidence and ReviewFlag.LOW_CONFIDENCE in segment.review_flags:
                    has_relevant_flag = True
                    flags_present.append("LOW_CONFIDENCE")

                if not has_relevant_flag:
                    continue

                if segment.confidence < self.config.min_confidence:
                    continue

                # Create evidence reference
                evidence_ref = EvidenceRef(
                    evidence_id=evidence.id,
                    filename=evidence.filename,
                    source_type="transcript_segment",
                    speaker=segment.speaker,
                    speaker_role=str(segment.speaker_role) if segment.speaker_role else None,
                    start_time_seconds=segment.start_time,
                    end_time_seconds=segment.end_time,
                    transcript_segment_id=f"{evidence.id}_{segment.start_time}",
                )

                # Determine kind based on content
                kind = self._classify_proposit_kind(segment.text)

                # Create claim text
                speaker_name = evidence.transcript.get_speaker_name(segment.speaker)
                claim = f'{speaker_name} stated: "{segment.text}"'

                # Determine polarity based on speaker role
                # Officers and state witnesses typically support State
                # Victims, defendants, defense witnesses support Defense
                polarity = self._determine_polarity(segment.speaker_role, flags_present)

                proposit = Proposit(
                    id=self._next_proposit_id(),
                    claim=claim,
                    kind=kind,
                    polarity=polarity,
                    evidence_refs=[evidence_ref],
                    weight=self._calculate_initial_weight(segment.confidence, flags_present),
                )

                proposits.append(proposit)

        return proposits

    def _extract_from_key_statements(self) -> list[Proposit]:
        """Extract proposits from key statements in transcripts."""
        proposits = []

        for evidence in self.case.evidence_items:
            if not evidence.transcript:
                continue

            for segment in evidence.transcript.key_statements:
                # Skip if already captured by flagged segments
                if segment.review_flags:
                    continue

                evidence_ref = EvidenceRef(
                    evidence_id=evidence.id,
                    filename=evidence.filename,
                    source_type="transcript_segment",
                    speaker=segment.speaker,
                    speaker_role=str(segment.speaker_role) if segment.speaker_role else None,
                    start_time_seconds=segment.start_time,
                    end_time_seconds=segment.end_time,
                    transcript_segment_id=f"{evidence.id}_{segment.start_time}",
                )

                speaker_name = evidence.transcript.get_speaker_name(segment.speaker)
                claim = f'{speaker_name} stated: "{segment.text}"'

                proposit = Proposit(
                    id=self._next_proposit_id(),
                    claim=claim,
                    kind=self._classify_proposit_kind(segment.text),
                    polarity=self._determine_polarity(segment.speaker_role, []),
                    evidence_refs=[evidence_ref],
                    weight=self._calculate_initial_weight(segment.confidence, []),
                )

                proposits.append(proposit)

        return proposits

    def _extract_from_timeline(self) -> list[Proposit]:
        """Extract proposits from timeline events."""
        if not self.config.include_timeline:
            return []

        proposits = []

        for event in self.case.timeline:
            evidence_ref = EvidenceRef(
                evidence_id=event.evidence_id or "timeline",
                filename=event.metadata.get("filename", "timeline"),
                source_type="timeline_event",
            )

            proposit = Proposit(
                id=self._next_proposit_id(),
                claim=f"Timeline event: {event.description}",
                kind=PropositionKind.INFERENCE,
                polarity=Polarity.SUPPORTS,  # Timeline events are neutral by default
                evidence_refs=[evidence_ref],
                weight=0.4,  # Lower weight for timeline-derived proposits
            )

            proposits.append(proposit)

        return proposits

    def _extract_from_vision_analysis(self) -> list[Proposit]:
        """Extract proposits from vision analysis of images."""
        proposits = []

        for evidence in self.case.evidence_items:
            vision_analysis = evidence.metadata.get("vision_analysis")
            if not vision_analysis:
                continue

            # Extract from key findings
            for finding in vision_analysis.get("key_findings", []):
                evidence_ref = EvidenceRef(
                    evidence_id=evidence.id,
                    filename=evidence.filename,
                    source_type="image",
                )

                proposit = Proposit(
                    id=self._next_proposit_id(),
                    claim=f"Image analysis ({evidence.filename}): {finding}",
                    kind=PropositionKind.DIRECT_OBSERVATION,
                    polarity=Polarity.SUPPORTS,
                    evidence_refs=[evidence_ref],
                    weight=0.5,
                )

                proposits.append(proposit)

            # Create proposits for detected weapons/injuries
            if vision_analysis.get("weapons_detected"):
                evidence_ref = EvidenceRef(
                    evidence_id=evidence.id,
                    filename=evidence.filename,
                    source_type="image",
                )

                proposit = Proposit(
                    id=self._next_proposit_id(),
                    claim=f"Weapon visible in {evidence.filename}",
                    kind=PropositionKind.DIRECT_OBSERVATION,
                    polarity=Polarity.SUPPORTS,
                    evidence_refs=[evidence_ref],
                    weight=0.7,  # Higher weight for weapon detection
                )

                proposits.append(proposit)

            if vision_analysis.get("injuries_visible"):
                evidence_ref = EvidenceRef(
                    evidence_id=evidence.id,
                    filename=evidence.filename,
                    source_type="image",
                )

                proposit = Proposit(
                    id=self._next_proposit_id(),
                    claim=f"Injuries visible in {evidence.filename}",
                    kind=PropositionKind.DIRECT_OBSERVATION,
                    polarity=Polarity.SUPPORTS,
                    evidence_refs=[evidence_ref],
                    weight=0.7,
                )

                proposits.append(proposit)

        return proposits

    def _classify_proposit_kind(self, text: str) -> PropositionKind:
        """Classify the kind of proposit based on text content."""
        text_lower = text.lower()

        # Check for perception verbs (direct observation)
        perception_verbs = ["i saw", "i heard", "i watched", "i noticed", "i observed", "i felt"]
        if any(verb in text_lower for verb in perception_verbs):
            return PropositionKind.DIRECT_OBSERVATION

        # Check for admission patterns
        admission_patterns = ["i did", "i was", "i went", "i hit", "i grabbed", "i took"]
        if any(pattern in text_lower for pattern in admission_patterns):
            return PropositionKind.ADMISSION

        # Check for hearsay/inference patterns
        hearsay_patterns = ["he said", "she said", "they said", "told me", "i think", "i believe"]
        if any(pattern in text_lower for pattern in hearsay_patterns):
            return PropositionKind.INFERENCE

        # Default to direct observation for first-person statements
        if text_lower.startswith("i "):
            return PropositionKind.DIRECT_OBSERVATION

        return PropositionKind.DOCUMENT_CONTENT

    def _determine_polarity(self, speaker_role: Optional[str], flags: list[str]) -> Polarity:
        """
        Determine polarity based on speaker role and content.

        For now, all proposits are marked as SUPPORTS since actual polarity
        depends on the proposition they're grouped into.
        """
        # This is a simplification - real polarity should be determined
        # based on the proposition the proposit is grouped into
        return Polarity.SUPPORTS

    def _calculate_initial_weight(self, confidence: float, flags: list[str]) -> float:
        """Calculate initial weight for a proposit."""
        weight = confidence

        # Boost for threat/violence content
        if "THREAT" in flags or "VIOLENCE" in flags:
            weight *= 1.2

        # Cap at 1.0
        return min(weight, 1.0)

    def _group_proposits(self, proposits: list[Proposit]) -> list[Proposition]:
        """
        Group proposits into propositions.

        For now, this creates a single proposition with all proposits.
        A more sophisticated implementation would:
        - Cluster by shared entities
        - Cluster by time window
        - Use embeddings for semantic similarity
        """
        if not proposits:
            return []

        # Get default material issue
        issue_template = MATERIAL_ISSUE_TEMPLATES.get(
            self.config.default_issue,
            MATERIAL_ISSUE_TEMPLATES["self_defense"],
        )

        # Create a single proposition with all proposits
        # In a real implementation, we would cluster proposits
        proposition = Proposition(
            id=self._next_proposition_id(),
            statement="Extracted propositions from case evidence (requires manual refinement)",
            proponent=ProponentInfo(
                party=self.config.default_proponent,
                attorney_note="Auto-extracted from flagged segments",
            ),
            material_issue=MaterialIssueRef(
                issue_id=issue_template.id,
                label=issue_template.label,
                elements=issue_template.elements,
            ),
            burden=BurdenInfo(
                persuasion_party=issue_template.default_burden_party,
                persuasion_standard=issue_template.default_burden_standard,
            ),
            skanda=Skanda(
                proposits=proposits,
            ),
        )

        return [proposition]


def extract_propositions_from_case(
    case: Case,
    config: Optional[ExtractionConfig] = None,
) -> list[Proposition]:
    """
    Extract propositions from a case.

    This is the main entry point for proposition extraction.

    Args:
        case: The case to extract from
        config: Optional extraction configuration

    Returns:
        List of extracted propositions
    """
    extractor = PropositionExtractor(case, config)
    return extractor.extract()
