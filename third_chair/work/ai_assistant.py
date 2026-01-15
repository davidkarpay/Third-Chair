"""AI-assisted work item creation using gemma2:2b.

Uses a lightweight local model for fast (~1s) responses to:
- Suggest work items based on case analysis
- Create structured work items from natural language
"""

import json
import re
from typing import Optional

from ..summarization.ollama_client import OllamaClient
from ..models import Case
from .models import WorkItem, WorkItemType, Priority, generate_item_id
from .storage import WorkStorage


# Model configuration - gemma2:2b for speed
DEFAULT_MODEL = "gemma2:2b"


# System prompt for work item creation
WORK_ITEM_SYSTEM_PROMPT = """You are a legal case assistant helping attorneys manage their case work.
You create structured work items for legal cases.

Work item types:
- investigation: Facts to discover (witness interviews, document requests, evidence analysis)
- legal_question: Legal research needed (case law, statutory interpretation, procedural issues)
- objective: Case goals (plea targets, trial strategy, desired outcomes)
- action: Tasks to complete (file motion, prepare exhibit, send discovery)
- fact: Established facts that support case theory

Priority levels: low, medium, high, critical

Always respond with valid JSON."""


def _parse_work_item_response(text: str) -> Optional[dict]:
    """Parse LLM response into work item data.

    Args:
        text: Raw LLM response

    Returns:
        Parsed dict or None if parsing fails
    """
    # Try to extract JSON from response
    # Handle markdown code blocks
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if json_match:
        text = json_match.group(1)

    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _build_case_context(case: Case) -> str:
    """Build context string from case data.

    Args:
        case: The case to summarize

    Returns:
        Context string for the LLM
    """
    lines = [
        f"Case ID: {case.case_id}",
        f"Evidence items: {case.evidence_count}",
        f"Media files: {case.media_count}",
        f"Witnesses: {len(case.witnesses.witnesses)}",
    ]

    # Add witness info
    if case.witnesses.witnesses:
        lines.append("\nKey witnesses:")
        for w in case.witnesses.witnesses[:5]:
            role = w.role.value if hasattr(w.role, "value") else str(w.role)
            lines.append(f"  - {w.display_name} ({role})")

    # Add proposition info
    if case.propositions:
        lines.append(f"\nPropositions: {len(case.propositions)}")
        for prop in case.propositions[:3]:
            lines.append(f"  - {prop.statement[:80]}...")

    # Add timeline events
    if case.timeline:
        lines.append(f"\nTimeline events: {len(case.timeline)}")

    return "\n".join(lines)


def create_work_item_from_text(
    storage: WorkStorage,
    text: str,
    case: Optional[Case] = None,
    model: str = DEFAULT_MODEL,
) -> Optional[WorkItem]:
    """Create a work item from natural language description.

    Args:
        storage: WorkStorage for the case
        text: Natural language description of the work
        case: Optional case for context
        model: Ollama model to use

    Returns:
        Created WorkItem or None if creation failed
    """
    client = OllamaClient(model=model, timeout=30)

    if not client.is_available():
        return None

    # Build prompt
    prompt = f"""Create a work item from this description:

"{text}"

Respond with JSON:
{{
  "type": "investigation|legal_question|objective|action|fact",
  "title": "Short title (under 60 chars)",
  "description": "Detailed description",
  "priority": "low|medium|high|critical",
  "tags": ["tag1", "tag2"]
}}"""

    if case:
        prompt = f"Case context:\n{_build_case_context(case)}\n\n{prompt}"

    response = client.generate(
        prompt=prompt,
        system=WORK_ITEM_SYSTEM_PROMPT,
        temperature=0.1,
        max_tokens=256,
    )

    if not response.success:
        return None

    # Parse response
    data = _parse_work_item_response(response.text)
    if not data:
        return None

    # Validate type
    try:
        item_type = WorkItemType(data.get("type", "action"))
    except ValueError:
        item_type = WorkItemType.ACTION

    # Create item
    return storage.create_item(
        item_type=item_type,
        title=data.get("title", text[:60]),
        description=data.get("description", text),
        priority=data.get("priority", "medium"),
        tags=data.get("tags", []),
    )


def suggest_work_items(
    storage: WorkStorage,
    case: Case,
    max_suggestions: int = 5,
    model: str = DEFAULT_MODEL,
) -> list[dict]:
    """Analyze case and suggest work items.

    Args:
        storage: WorkStorage for the case
        case: The case to analyze
        max_suggestions: Maximum number of suggestions
        model: Ollama model to use

    Returns:
        List of suggested work items (as dicts, not yet created)
    """
    client = OllamaClient(model=model, timeout=60)

    if not client.is_available():
        return []

    context = _build_case_context(case)

    prompt = f"""Analyze this legal case and suggest {max_suggestions} work items the attorney should create.

{context}

For each suggestion, provide JSON with:
- type: investigation, legal_question, objective, action, or fact
- title: Short descriptive title
- description: Why this work is needed
- priority: low, medium, high, or critical

Respond with a JSON array of suggestions:
[
  {{"type": "...", "title": "...", "description": "...", "priority": "..."}},
  ...
]"""

    response = client.generate(
        prompt=prompt,
        system=WORK_ITEM_SYSTEM_PROMPT,
        temperature=0.3,
        max_tokens=1024,
    )

    if not response.success:
        return []

    # Parse response
    text = response.text.strip()

    # Try to extract JSON array
    array_match = re.search(r"\[[\s\S]*\]", text)
    if array_match:
        try:
            suggestions = json.loads(array_match.group(0))
            if isinstance(suggestions, list):
                return suggestions[:max_suggestions]
        except json.JSONDecodeError:
            pass

    return []


def create_suggested_items(
    storage: WorkStorage,
    suggestions: list[dict],
) -> list[WorkItem]:
    """Create work items from suggestions.

    Args:
        storage: WorkStorage for the case
        suggestions: List of suggestion dicts

    Returns:
        List of created WorkItems
    """
    created = []

    for suggestion in suggestions:
        try:
            item_type = WorkItemType(suggestion.get("type", "action"))
        except ValueError:
            item_type = WorkItemType.ACTION

        item = storage.create_item(
            item_type=item_type,
            title=suggestion.get("title", "Untitled"),
            description=suggestion.get("description", ""),
            priority=suggestion.get("priority", "medium"),
        )
        created.append(item)

    return created
