"""Viewing guide generator for Third Chair.

Generates recommended video viewing timestamps based on flagged
transcript segments (threats, violence keywords, low confidence).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..models import Case, FileType


@dataclass
class ViewingRecommendation:
    """A recommended moment to watch in a video."""

    filename: str
    timestamp_seconds: float
    timestamp_formatted: str  # "MM:SS"
    flags: list[str] = field(default_factory=list)
    statement_preview: str = ""
    speaker: str = ""
    speaker_role: Optional[str] = None


def format_timestamp(seconds: float) -> str:
    """Convert seconds to MM:SS format."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def generate_viewing_guide(
    case: Case,
    flag_filter: Optional[list[str]] = None,
) -> dict[str, list[ViewingRecommendation]]:
    """
    Extract flagged moments from transcripts, grouped by video.

    Args:
        case: Case with transcribed evidence
        flag_filter: If provided, only include segments with these flags

    Returns:
        Dict mapping filename to list of ViewingRecommendation
    """
    guide: dict[str, list[ViewingRecommendation]] = {}

    for evidence in case.evidence_items:
        # Only process videos with transcripts
        if evidence.file_type != FileType.VIDEO:
            continue
        if not evidence.transcript:
            continue
        if not evidence.transcript.segments:
            continue

        recommendations = []
        for segment in evidence.transcript.segments:
            # Skip segments without flags
            if not segment.review_flags:
                continue

            # Apply flag filter if provided
            if flag_filter:
                matching_flags = [f for f in segment.review_flags if f in flag_filter]
                if not matching_flags:
                    continue
                flags_to_use = matching_flags
            else:
                flags_to_use = segment.review_flags

            # Create recommendation
            preview = segment.text[:80]
            if len(segment.text) > 80:
                preview += "..."

            recommendations.append(ViewingRecommendation(
                filename=evidence.filename,
                timestamp_seconds=segment.start_time,
                timestamp_formatted=format_timestamp(segment.start_time),
                flags=flags_to_use,
                statement_preview=preview,
                speaker=segment.speaker,
                speaker_role=segment.speaker_role,
            ))

        if recommendations:
            # Sort by timestamp
            guide[evidence.filename] = sorted(
                recommendations,
                key=lambda r: r.timestamp_seconds
            )

    return guide


def _clean_flag(flag) -> str:
    """Clean flag name for display (remove enum prefix and _KEYWORD suffix)."""
    flag_str = str(flag)
    # Handle ReviewFlag enum
    if "ReviewFlag." in flag_str:
        flag_str = flag_str.replace("ReviewFlag.", "")
    # Remove _KEYWORD suffix
    flag_str = flag_str.replace("_KEYWORD", "")
    return flag_str


def _clean_role(role) -> str:
    """Clean speaker role for display (remove enum prefix)."""
    if role is None:
        return ""
    role_str = str(role)
    if "SpeakerRole." in role_str:
        role_str = role_str.replace("SpeakerRole.", "")
    return role_str


def format_viewing_guide_text(
    guide: dict[str, list[ViewingRecommendation]],
    include_speaker: bool = True,
) -> str:
    """
    Format viewing guide as plain text.

    Args:
        guide: Dict from generate_viewing_guide()
        include_speaker: Whether to include speaker info

    Returns:
        Formatted text string
    """
    lines = []
    lines.append("=" * 60)
    lines.append("RECOMMENDED VIEWING GUIDE")
    lines.append("=" * 60)
    lines.append("")

    # Summary
    total_moments = sum(len(recs) for recs in guide.values())
    lines.append(f"Total flagged moments: {total_moments}")
    lines.append(f"Videos with flagged content: {len(guide)}")
    lines.append("")

    # Count by flag type
    flag_counts: dict[str, int] = {}
    for recs in guide.values():
        for rec in recs:
            for flag in rec.flags:
                clean_flag = _clean_flag(flag)
                flag_counts[clean_flag] = flag_counts.get(clean_flag, 0) + 1

    if flag_counts:
        lines.append("By flag type:")
        for flag, count in sorted(flag_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {flag}: {count}")
        lines.append("")

    lines.append("-" * 60)
    lines.append("")

    # Per-video details
    for filename in sorted(guide.keys()):
        recommendations = guide[filename]

        lines.append(f"=== {filename} ===")
        lines.append(f"    ({len(recommendations)} flagged moments)")
        lines.append("")

        for rec in recommendations:
            # Format flags - clean each flag
            flag_str = "+".join(_clean_flag(f) for f in rec.flags)

            # Format line
            if include_speaker and rec.speaker:
                if rec.speaker_role:
                    speaker_info = f" ({_clean_role(rec.speaker_role)})"
                else:
                    speaker_info = f" ({rec.speaker})"
            else:
                speaker_info = ""

            lines.append(f"  {rec.timestamp_formatted}  [{flag_str}]{speaker_info}")
            lines.append(f"          \"{rec.statement_preview}\"")
            lines.append("")

        lines.append("")

    return "\n".join(lines)


def write_viewing_guide(
    case: Case,
    output_path: Path,
    flag_filter: Optional[list[str]] = None,
    include_speaker: bool = True,
) -> Path:
    """
    Generate and write viewing guide to file.

    Args:
        case: Case with transcribed evidence
        output_path: Where to write the guide
        flag_filter: If provided, only include segments with these flags
        include_speaker: Whether to include speaker info

    Returns:
        Path to written file
    """
    guide = generate_viewing_guide(case, flag_filter)
    text = format_viewing_guide_text(guide, include_speaker)

    output_path = Path(output_path)
    output_path.write_text(text, encoding="utf-8")

    return output_path


def get_viewing_stats(case: Case) -> dict:
    """
    Get statistics about flagged moments.

    Args:
        case: Case with transcribed evidence

    Returns:
        Dict with statistics
    """
    guide = generate_viewing_guide(case)

    total_moments = sum(len(recs) for recs in guide.values())

    flag_counts: dict[str, int] = {}
    for recs in guide.values():
        for rec in recs:
            for flag in rec.flags:
                clean_flag = _clean_flag(flag)
                flag_counts[clean_flag] = flag_counts.get(clean_flag, 0) + 1

    return {
        "total_flagged_moments": total_moments,
        "videos_with_flags": len(guide),
        "flag_counts": flag_counts,
        "videos": list(guide.keys()),
    }
