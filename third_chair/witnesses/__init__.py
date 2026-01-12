"""Witness management module for Third Chair.

Handles:
- Speaker role detection (Officer, Victim, Witness, Suspect)
- Importing witness lists from various formats
- Matching imported witnesses to diarized speakers
"""

from pathlib import Path
from typing import Optional

from ..models import Case, Transcript, Witness, WitnessList, WitnessRole
from .speaker_roles import (
    assign_roles_to_transcript,
    detect_speaker_role,
    get_speakers_by_role,
    summarize_speaker_roles,
)
from .witness_importer import import_witness_list
from .witness_matcher import (
    extract_speakers_from_case,
    find_name_mentions,
    match_witnesses_to_speakers,
    suggest_speaker_names,
)


def process_witnesses(
    case: Case,
    witness_list_path: Optional[Path] = None,
    show_progress: bool = True,
) -> Case:
    """
    Full witness processing pipeline.

    Steps:
    1. Detect speaker roles in all transcripts
    2. Extract speakers as witnesses
    3. Import external witness list (if provided)
    4. Match imported witnesses to speakers

    Args:
        case: Case to process
        witness_list_path: Optional path to witness list file
        show_progress: Whether to show progress

    Returns:
        Updated case with witness information
    """
    if show_progress:
        print("Processing witnesses...")

    # Step 1: Detect speaker roles in transcripts
    if show_progress:
        print("  Detecting speaker roles...")

    for evidence in case.evidence_items:
        if evidence.transcript:
            evidence.transcript = assign_roles_to_transcript(evidence.transcript)

    # Step 2: Extract speakers from transcripts
    if show_progress:
        print("  Extracting speakers from transcripts...")

    speaker_witnesses = extract_speakers_from_case(case)
    if show_progress:
        print(f"    Found {len(speaker_witnesses.witnesses)} unique speakers")

    # Step 3: Import external witness list
    imported_witnesses = WitnessList()
    if witness_list_path:
        if show_progress:
            print(f"  Importing witness list from {witness_list_path}...")
        imported_witnesses = import_witness_list(witness_list_path)
        if show_progress:
            print(f"    Imported {len(imported_witnesses.witnesses)} witnesses")

    # Step 4: Match witnesses to speakers
    if imported_witnesses.witnesses:
        if show_progress:
            print("  Matching witnesses to speakers...")

        transcripts = [
            e.transcript for e in case.evidence_items
            if e.transcript is not None
        ]

        case.witnesses = match_witnesses_to_speakers(
            imported_witnesses,
            speaker_witnesses,
            transcripts,
        )

        verified_count = len([w for w in case.witnesses.witnesses if w.verified])
        if show_progress:
            print(f"    Matched {verified_count} witnesses to speakers")
    else:
        # No imported list, just use speakers
        case.witnesses = speaker_witnesses

    # Save updated case
    case.save()

    if show_progress:
        print(f"  Total witnesses: {len(case.witnesses.witnesses)}")
        _print_witness_summary(case.witnesses)

    return case


def _print_witness_summary(witnesses: WitnessList) -> None:
    """Print a summary of witnesses by role."""
    by_role: dict[WitnessRole, list[Witness]] = {}

    for witness in witnesses.witnesses:
        if witness.role not in by_role:
            by_role[witness.role] = []
        by_role[witness.role].append(witness)

    for role in WitnessRole:
        if role in by_role:
            names = [w.display_name for w in by_role[role]]
            print(f"    {role.value}: {', '.join(names[:3])}"
                  + (f" (+{len(names)-3} more)" if len(names) > 3 else ""))


def rename_speaker(
    case: Case,
    speaker_id: str,
    name: str,
) -> bool:
    """
    Rename a speaker across the case.

    Updates:
    - Witness name in witness list
    - Speaker mapping in transcripts

    Args:
        case: Case to update
        speaker_id: Speaker ID to rename (e.g., "SPEAKER_1")
        name: New name for the speaker

    Returns:
        True if speaker was found and renamed
    """
    # Find witness with this speaker ID
    witness = case.witnesses.get_by_speaker_id(speaker_id)

    if witness:
        witness.name = name
        witness.verified = True

        # Update transcript speaker mappings
        for evidence in case.evidence_items:
            if evidence.transcript:
                evidence.transcript.rename_speaker(speaker_id, name)

        case.save()
        return True

    return False


def get_unmatched_witnesses(case: Case) -> list[Witness]:
    """
    Get witnesses that haven't been matched to speakers.

    Returns:
        List of unmatched witnesses
    """
    return [
        w for w in case.witnesses.witnesses
        if not w.speaker_ids
    ]


def get_unnamed_speakers(case: Case) -> list[Witness]:
    """
    Get speakers that haven't been named.

    Returns:
        List of unnamed speaker witnesses
    """
    return case.witnesses.get_unnamed()


__all__ = [
    # Main functions
    "process_witnesses",
    "rename_speaker",
    "get_unmatched_witnesses",
    "get_unnamed_speakers",
    # Speaker roles
    "assign_roles_to_transcript",
    "detect_speaker_role",
    "get_speakers_by_role",
    "summarize_speaker_roles",
    # Import
    "import_witness_list",
    # Matching
    "extract_speakers_from_case",
    "match_witnesses_to_speakers",
    "find_name_mentions",
    "suggest_speaker_names",
]
