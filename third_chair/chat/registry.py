"""Tool registry for the Chat Research Assistant.

Provides a registry of tools that can be invoked by the function caller
to query case data, search transcripts, and manage propositions.
"""

from pathlib import Path
from typing import Any, Callable, Optional

from ..models import (
    Case,
    EvidenceRef,
    FileType,
    HoldsStatus,
    Polarity,
    Proposition,
    Proposit,
    PropositionKind,
    ReviewFlag,
)
from .tools import (
    ParameterType,
    Tool,
    ToolParameter,
    ToolResult,
)


class ToolRegistry:
    """
    Registry of tools available to the chat assistant.

    The registry provides JSON schemas for function calling and
    routes invocations to the appropriate handlers.
    """

    def __init__(self, case: Optional[Case] = None):
        """
        Initialize the tool registry.

        Args:
            case: The case to query. Can be set later via set_case().
        """
        self.case = case
        self._tools: dict[str, Tool] = {}
        self._register_default_tools()

    def set_case(self, case: Case) -> None:
        """Set the case to query."""
        self.case = case

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> list[Tool]:
        """List all registered tools, optionally filtered by category."""
        if category:
            return [t for t in self._tools.values() if t.category == category]
        return list(self._tools.values())

    def get_json_schemas(self) -> list[dict]:
        """Get JSON schemas for all tools (for function calling)."""
        return [tool.to_json_schema() for tool in self._tools.values()]

    def invoke(self, name: str, **kwargs) -> ToolResult:
        """Invoke a tool by name with arguments."""
        tool = self.get(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {name}",
                tool_name=name,
            )

        # Check if case is required
        if self.case is None and name not in ["help", "list_tools"]:
            return ToolResult(
                success=False,
                error="No case loaded. Load a case first.",
                tool_name=name,
            )

        return tool.invoke(**kwargs)

    def _register_default_tools(self) -> None:
        """Register all default tools."""
        self._register_case_tools()
        self._register_transcript_tools()
        self._register_witness_tools()
        self._register_proposition_tools()
        self._register_analysis_tools()

    def _register_case_tools(self) -> None:
        """Register case query tools."""

        # get_case_info
        self.register(Tool(
            name="get_case_info",
            description="Get basic case information including ID, date, and evidence counts.",
            parameters=[],
            handler=self._handle_get_case_info,
            category="case",
        ))

        # get_evidence_list
        self.register(Tool(
            name="get_evidence_list",
            description="List all evidence items, optionally filtered by type (VIDEO, AUDIO, DOCUMENT, IMAGE).",
            parameters=[
                ToolParameter(
                    name="file_type",
                    param_type=ParameterType.STRING,
                    description="Filter by file type",
                    required=False,
                    enum=["VIDEO", "AUDIO", "DOCUMENT", "IMAGE"],
                ),
            ],
            handler=self._handle_get_evidence_list,
            category="case",
        ))

        # get_evidence_details
        self.register(Tool(
            name="get_evidence_details",
            description="Get detailed information about a specific evidence file by filename.",
            parameters=[
                ToolParameter(
                    name="filename",
                    param_type=ParameterType.STRING,
                    description="The filename to get details for",
                    required=True,
                ),
            ],
            handler=self._handle_get_evidence_details,
            category="case",
        ))

        # get_timeline
        self.register(Tool(
            name="get_timeline",
            description="Get the chronological timeline of events in the case.",
            parameters=[],
            handler=self._handle_get_timeline,
            category="case",
        ))

    def _register_transcript_tools(self) -> None:
        """Register transcript search tools."""

        # search_transcripts
        self.register(Tool(
            name="search_transcripts",
            description="Search all transcripts for keywords or phrases. Returns matching segments with timestamps.",
            parameters=[
                ToolParameter(
                    name="query",
                    param_type=ParameterType.STRING,
                    description="The search query (keyword or phrase)",
                    required=True,
                ),
                ToolParameter(
                    name="speaker",
                    param_type=ParameterType.STRING,
                    description="Filter by speaker name or ID",
                    required=False,
                ),
            ],
            handler=self._handle_search_transcripts,
            category="transcript",
        ))

        # get_speaker_statements
        self.register(Tool(
            name="get_speaker_statements",
            description="Get all statements made by a specific speaker across all evidence.",
            parameters=[
                ToolParameter(
                    name="speaker",
                    param_type=ParameterType.STRING,
                    description="The speaker name or ID (e.g., 'SPEAKER_1' or 'Officer Smith')",
                    required=True,
                ),
                ToolParameter(
                    name="evidence_id",
                    param_type=ParameterType.STRING,
                    description="Filter to specific evidence file",
                    required=False,
                ),
            ],
            handler=self._handle_get_speaker_statements,
            category="transcript",
        ))

        # get_flagged_statements
        self.register(Tool(
            name="get_flagged_statements",
            description="Get statements with specific review flags (THREAT_KEYWORD, VIOLENCE_KEYWORD, LOW_CONFIDENCE).",
            parameters=[
                ToolParameter(
                    name="flag_type",
                    param_type=ParameterType.STRING,
                    description="The flag type to filter by",
                    required=True,
                    enum=["THREAT_KEYWORD", "VIOLENCE_KEYWORD", "LOW_CONFIDENCE", "CODE_SWITCHED"],
                ),
            ],
            handler=self._handle_get_flagged_statements,
            category="transcript",
        ))

        # get_transcript_at_time
        self.register(Tool(
            name="get_transcript_at_time",
            description="Get transcript content around a specific timestamp in a video.",
            parameters=[
                ToolParameter(
                    name="filename",
                    param_type=ParameterType.STRING,
                    description="The video/audio filename",
                    required=True,
                ),
                ToolParameter(
                    name="timestamp",
                    param_type=ParameterType.STRING,
                    description="The timestamp in MM:SS format (e.g., '2:30')",
                    required=True,
                ),
            ],
            handler=self._handle_get_transcript_at_time,
            category="transcript",
        ))

    def _register_witness_tools(self) -> None:
        """Register witness query tools."""

        # get_witness_list
        self.register(Tool(
            name="get_witness_list",
            description="Get list of all witnesses with their roles (OFFICER, VICTIM, WITNESS, SUSPECT).",
            parameters=[],
            handler=self._handle_get_witness_list,
            category="witness",
        ))

        # get_witness_statements
        self.register(Tool(
            name="get_witness_statements",
            description="Get all statements made by a specific witness across all evidence.",
            parameters=[
                ToolParameter(
                    name="name",
                    param_type=ParameterType.STRING,
                    description="The witness name",
                    required=True,
                ),
            ],
            handler=self._handle_get_witness_statements,
            category="witness",
        ))

        # who_said
        self.register(Tool(
            name="who_said",
            description="Find who said a specific quote and when.",
            parameters=[
                ToolParameter(
                    name="quote",
                    param_type=ParameterType.STRING,
                    description="The quote to search for (partial match supported)",
                    required=True,
                ),
            ],
            handler=self._handle_who_said,
            category="witness",
        ))

    def _register_proposition_tools(self) -> None:
        """Register proposition/skanda query tools."""

        # list_propositions
        self.register(Tool(
            name="list_propositions",
            description="List all propositions in the case, optionally filtered by material issue or proponent.",
            parameters=[
                ToolParameter(
                    name="material_issue",
                    param_type=ParameterType.STRING,
                    description="Filter by material issue ID",
                    required=False,
                ),
                ToolParameter(
                    name="proponent",
                    param_type=ParameterType.STRING,
                    description="Filter by proponent party (Defense, State)",
                    required=False,
                ),
            ],
            handler=self._handle_list_propositions,
            category="proposition",
        ))

        # get_proposition
        self.register(Tool(
            name="get_proposition",
            description="Get full details of a proposition including its skanda and evaluation.",
            parameters=[
                ToolParameter(
                    name="proposition_id",
                    param_type=ParameterType.STRING,
                    description="The proposition ID",
                    required=True,
                ),
            ],
            handler=self._handle_get_proposition,
            category="proposition",
        ))

        # get_proposition_drivers
        self.register(Tool(
            name="get_proposition_drivers",
            description="Get the top supporting and undermining proposits for a proposition with evidence citations.",
            parameters=[
                ToolParameter(
                    name="proposition_id",
                    param_type=ParameterType.STRING,
                    description="The proposition ID",
                    required=True,
                ),
            ],
            handler=self._handle_get_proposition_drivers,
            category="proposition",
        ))

        # find_contradictions_for_proposition
        self.register(Tool(
            name="find_contradictions_for_proposition",
            description="Find proposits that contradict a specific proposition.",
            parameters=[
                ToolParameter(
                    name="proposition_id",
                    param_type=ParameterType.STRING,
                    description="The proposition ID",
                    required=True,
                ),
            ],
            handler=self._handle_find_contradictions,
            category="proposition",
        ))

    def _register_analysis_tools(self) -> None:
        """Register analysis tools."""

        # find_contradictions
        self.register(Tool(
            name="find_contradictions",
            description="Find potentially contradictory statements about a topic across all evidence.",
            parameters=[
                ToolParameter(
                    name="topic",
                    param_type=ParameterType.STRING,
                    description="The topic to search for contradictions about",
                    required=True,
                ),
            ],
            handler=self._handle_find_contradictions_topic,
            category="analysis",
        ))

    # Handler implementations

    def _handle_get_case_info(self) -> dict:
        """Handle get_case_info tool."""
        return {
            "case_id": self.case.case_id,
            "court_case": self.case.court_case,
            "agency": self.case.agency,
            "incident_date": str(self.case.incident_date) if self.case.incident_date else None,
            "evidence_count": self.case.evidence_count,
            "media_count": self.case.media_count,
            "processed_count": self.case.processed_count,
            "witness_count": len(self.case.witnesses.witnesses),
            "proposition_count": self.case.proposition_count,
            "total_duration": self.case.total_duration_formatted,
        }

    def _handle_get_evidence_list(self, file_type: Optional[str] = None) -> list[dict]:
        """Handle get_evidence_list tool."""
        items = self.case.evidence_items
        if file_type:
            try:
                ft = FileType(file_type.upper())
                items = [e for e in items if e.file_type == ft]
            except ValueError:
                pass

        return [
            {
                "id": e.id,
                "filename": e.filename,
                "file_type": e.file_type.value,
                "duration": e.duration_formatted if e.duration_seconds else None,
                "has_transcript": e.transcript is not None,
                "processing_status": e.processing_status.value,
            }
            for e in items
        ]

    def _handle_get_evidence_details(self, filename: str) -> dict:
        """Handle get_evidence_details tool."""
        for e in self.case.evidence_items:
            if e.filename == filename:
                result = {
                    "id": e.id,
                    "filename": e.filename,
                    "file_type": e.file_type.value,
                    "content_type": e.content_type.value if e.content_type else None,
                    "size_mb": e.size_mb,
                    "duration": e.duration_formatted if e.duration_seconds else None,
                    "processing_status": e.processing_status.value,
                    "has_transcript": e.transcript is not None,
                    "summary": e.summary,
                }
                if e.transcript:
                    result["transcript_segments"] = len(e.transcript.segments)
                    result["speakers"] = list(e.transcript.speakers.keys())
                return result
        return {"error": f"Evidence not found: {filename}"}

    def _handle_get_timeline(self) -> list[dict]:
        """Handle get_timeline tool."""
        return [
            {
                "timestamp": e.timestamp.isoformat(),
                "description": e.description,
                "evidence_id": e.evidence_id,
                "source": e.source,
            }
            for e in self.case.timeline
        ]

    def _handle_search_transcripts(self, query: str, speaker: Optional[str] = None) -> list[dict]:
        """Handle search_transcripts tool."""
        results = []
        query_lower = query.lower()

        for evidence in self.case.evidence_items:
            if not evidence.transcript:
                continue

            for segment in evidence.transcript.segments:
                if query_lower not in segment.text.lower():
                    continue

                if speaker:
                    # Check speaker name or ID
                    speaker_name = evidence.transcript.get_speaker_name(segment.speaker)
                    if speaker.lower() not in segment.speaker.lower() and speaker.lower() not in speaker_name.lower():
                        continue

                results.append({
                    "filename": evidence.filename,
                    "timestamp": f"{int(segment.start_time // 60)}:{int(segment.start_time % 60):02d}",
                    "speaker": evidence.transcript.get_speaker_name(segment.speaker),
                    "speaker_role": str(segment.speaker_role) if segment.speaker_role else None,
                    "text": segment.text,
                    "confidence": segment.confidence,
                })

        return results[:50]  # Limit results

    def _handle_get_speaker_statements(self, speaker: str, evidence_id: Optional[str] = None) -> list[dict]:
        """Handle get_speaker_statements tool."""
        results = []
        speaker_lower = speaker.lower()

        for evidence in self.case.evidence_items:
            if evidence_id and evidence.id != evidence_id:
                continue
            if not evidence.transcript:
                continue

            for segment in evidence.transcript.segments:
                speaker_name = evidence.transcript.get_speaker_name(segment.speaker)
                if speaker_lower not in segment.speaker.lower() and speaker_lower not in speaker_name.lower():
                    continue

                results.append({
                    "filename": evidence.filename,
                    "timestamp": f"{int(segment.start_time // 60)}:{int(segment.start_time % 60):02d}",
                    "text": segment.text,
                    "flags": [str(f) for f in segment.review_flags],
                })

        return results

    def _handle_get_flagged_statements(self, flag_type: str) -> list[dict]:
        """Handle get_flagged_statements tool."""
        results = []
        try:
            flag = ReviewFlag(flag_type)
        except ValueError:
            return [{"error": f"Unknown flag type: {flag_type}"}]

        for evidence in self.case.evidence_items:
            if not evidence.transcript:
                continue

            for segment in evidence.transcript.segments:
                if flag not in segment.review_flags:
                    continue

                results.append({
                    "filename": evidence.filename,
                    "timestamp": f"{int(segment.start_time // 60)}:{int(segment.start_time % 60):02d}",
                    "speaker": evidence.transcript.get_speaker_name(segment.speaker),
                    "text": segment.text,
                    "flags": [str(f) for f in segment.review_flags],
                })

        return results

    def _handle_get_transcript_at_time(self, filename: str, timestamp: str) -> dict:
        """Handle get_transcript_at_time tool."""
        # Parse timestamp
        try:
            parts = timestamp.split(":")
            if len(parts) == 2:
                target_seconds = int(parts[0]) * 60 + int(parts[1])
            else:
                target_seconds = int(timestamp)
        except ValueError:
            return {"error": f"Invalid timestamp format: {timestamp}"}

        for evidence in self.case.evidence_items:
            if evidence.filename != filename:
                continue
            if not evidence.transcript:
                return {"error": f"No transcript for {filename}"}

            # Find segments around the timestamp (+/- 30 seconds)
            segments = []
            for segment in evidence.transcript.segments:
                if abs(segment.start_time - target_seconds) < 30:
                    segments.append({
                        "timestamp": f"{int(segment.start_time // 60)}:{int(segment.start_time % 60):02d}",
                        "speaker": evidence.transcript.get_speaker_name(segment.speaker),
                        "text": segment.text,
                    })

            return {
                "filename": filename,
                "target_timestamp": timestamp,
                "segments": segments,
            }

        return {"error": f"Evidence not found: {filename}"}

    def _handle_get_witness_list(self) -> list[dict]:
        """Handle get_witness_list tool."""
        return [
            {
                "id": w.id,
                "name": w.name,
                "role": str(w.role),
                "speaker_ids": w.speaker_ids,
                "verified": w.verified,
            }
            for w in self.case.witnesses.witnesses
        ]

    def _handle_get_witness_statements(self, name: str) -> list[dict]:
        """Handle get_witness_statements tool."""
        # Find the witness
        witness = None
        for w in self.case.witnesses.witnesses:
            if w.name and name.lower() in w.name.lower():
                witness = w
                break

        if not witness:
            return [{"error": f"Witness not found: {name}"}]

        # Get all statements by this witness's speaker IDs
        results = []
        for evidence in self.case.evidence_items:
            if not evidence.transcript:
                continue

            for segment in evidence.transcript.segments:
                if segment.speaker in witness.speaker_ids:
                    results.append({
                        "filename": evidence.filename,
                        "timestamp": f"{int(segment.start_time // 60)}:{int(segment.start_time % 60):02d}",
                        "text": segment.text,
                        "flags": [str(f) for f in segment.review_flags],
                    })

        return results

    def _handle_who_said(self, quote: str) -> dict:
        """Handle who_said tool."""
        quote_lower = quote.lower()

        for evidence in self.case.evidence_items:
            if not evidence.transcript:
                continue

            for segment in evidence.transcript.segments:
                if quote_lower in segment.text.lower():
                    speaker_name = evidence.transcript.get_speaker_name(segment.speaker)
                    return {
                        "speaker": speaker_name,
                        "speaker_id": segment.speaker,
                        "speaker_role": str(segment.speaker_role) if segment.speaker_role else None,
                        "filename": evidence.filename,
                        "timestamp": f"{int(segment.start_time // 60)}:{int(segment.start_time % 60):02d}",
                        "full_text": segment.text,
                    }

        return {"error": f"Quote not found: {quote}"}

    def _handle_list_propositions(
        self,
        material_issue: Optional[str] = None,
        proponent: Optional[str] = None,
    ) -> list[dict]:
        """Handle list_propositions tool."""
        props = self.case.propositions

        if material_issue:
            props = [p for p in props if p.material_issue.issue_id == material_issue]

        if proponent:
            props = [p for p in props if p.proponent.party.lower() == proponent.lower()]

        return [
            {
                "id": p.id,
                "statement": p.statement[:100] + "..." if len(p.statement) > 100 else p.statement,
                "proponent": p.proponent.party,
                "material_issue": p.material_issue.label,
                "holds_under_scrutiny": p.evaluation.holds_under_scrutiny.value if p.evaluation else "not_evaluated",
                "weight": p.evaluation.weight if p.evaluation else None,
                "proposit_count": len(p.skanda.proposits),
            }
            for p in props
        ]

    def _handle_get_proposition(self, proposition_id: str) -> dict:
        """Handle get_proposition tool."""
        prop = self.case.get_proposition(proposition_id)
        if not prop:
            return {"error": f"Proposition not found: {proposition_id}"}

        return {
            "id": prop.id,
            "statement": prop.statement,
            "proponent": {
                "party": prop.proponent.party,
                "note": prop.proponent.attorney_note,
            },
            "material_issue": {
                "id": prop.material_issue.issue_id,
                "label": prop.material_issue.label,
                "elements": prop.material_issue.elements,
            },
            "burden": {
                "persuasion_party": prop.burden.persuasion_party,
                "standard": prop.burden.persuasion_standard.value,
            },
            "evaluation": {
                "holds_under_scrutiny": prop.evaluation.holds_under_scrutiny.value,
                "weight": prop.evaluation.weight,
                "probative_value": prop.evaluation.probative_value,
                "review_flags": prop.evaluation.human_review_flags,
            } if prop.evaluation else None,
            "skanda": {
                "proposit_count": len(prop.skanda.proposits),
                "support_score": prop.skanda.support_score,
                "undermine_score": prop.skanda.undermine_score,
            },
        }

    def _handle_get_proposition_drivers(self, proposition_id: str) -> dict:
        """Handle get_proposition_drivers tool."""
        prop = self.case.get_proposition(proposition_id)
        if not prop:
            return {"error": f"Proposition not found: {proposition_id}"}

        supporting = []
        for p in prop.skanda.supporting[:5]:  # Top 5
            supporting.append({
                "id": p.id,
                "claim": p.claim,
                "weight": p.weight,
                "evidence": [
                    {
                        "filename": ref.filename,
                        "timestamp": f"{int(ref.start_time_seconds // 60)}:{int(ref.start_time_seconds % 60):02d}" if ref.start_time_seconds else None,
                        "speaker": ref.speaker,
                    }
                    for ref in p.evidence_refs
                ],
            })

        undermining = []
        for p in prop.skanda.undermining[:5]:  # Top 5
            undermining.append({
                "id": p.id,
                "claim": p.claim,
                "weight": p.weight,
                "evidence": [
                    {
                        "filename": ref.filename,
                        "timestamp": f"{int(ref.start_time_seconds // 60)}:{int(ref.start_time_seconds % 60):02d}" if ref.start_time_seconds else None,
                        "speaker": ref.speaker,
                    }
                    for ref in p.evidence_refs
                ],
            })

        return {
            "proposition_id": proposition_id,
            "top_supporting": supporting,
            "top_undermining": undermining,
        }

    def _handle_find_contradictions(self, proposition_id: str) -> list[dict]:
        """Handle find_contradictions_for_proposition tool."""
        prop = self.case.get_proposition(proposition_id)
        if not prop:
            return [{"error": f"Proposition not found: {proposition_id}"}]

        return [
            {
                "id": p.id,
                "claim": p.claim,
                "evidence": [ref.filename for ref in p.evidence_refs],
            }
            for p in prop.skanda.undermining
        ]

    def _handle_find_contradictions_topic(self, topic: str) -> list[dict]:
        """Handle find_contradictions tool."""
        # This is a placeholder - real implementation would use semantic search
        # to find potentially contradictory statements about a topic
        topic_lower = topic.lower()
        matches = []

        for evidence in self.case.evidence_items:
            if not evidence.transcript:
                continue

            for segment in evidence.transcript.segments:
                if topic_lower in segment.text.lower():
                    matches.append({
                        "filename": evidence.filename,
                        "timestamp": f"{int(segment.start_time // 60)}:{int(segment.start_time % 60):02d}",
                        "speaker": evidence.transcript.get_speaker_name(segment.speaker),
                        "text": segment.text,
                    })

        # In a real implementation, we would analyze these matches for contradictions
        return matches[:20]
