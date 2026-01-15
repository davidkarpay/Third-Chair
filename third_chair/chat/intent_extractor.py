"""Natural language intent extraction for chat interface.

Uses Ollama to parse user queries into structured tool invocations,
following the "intent problem" best practices:
- Separate interpretation from execution
- Confirm understanding before acting
- Provide alternatives when uncertain
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from ..summarization.ollama_client import get_ollama_client, OllamaResponse
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractedIntent:
    """Parsed intent from natural language query."""

    tool_name: str
    parameters: dict = field(default_factory=dict)
    confidence: float = 0.0  # 0.0-1.0
    interpretation: str = ""  # Human-readable explanation
    alternatives: list[str] = field(default_factory=list)
    raw_response: str = ""


@dataclass
class IntentResult:
    """Result of intent extraction attempt."""

    success: bool
    intent: Optional[ExtractedIntent] = None
    error: Optional[str] = None


# System prompt for intent extraction
INTENT_SYSTEM_PROMPT = """You are a legal discovery assistant that interprets user queries.

Your task: Given a user query and available tools, determine which tool the user wants to use and with what parameters.

IMPORTANT RULES:
1. Only use tools from the provided list
2. Extract parameter values from the query when possible
3. Provide a confidence score (0.0-1.0) based on how clear the intent is
4. If multiple interpretations are possible, list alternatives
5. Always respond in valid JSON format

Confidence guidelines:
- 0.9+: Query directly names the tool or uses exact keywords
- 0.7-0.9: Query clearly implies a specific tool
- 0.5-0.7: Query is somewhat ambiguous but one tool seems likely
- Below 0.5: Query is unclear or could match multiple tools equally"""


def _unwrap_schema(schema: dict) -> dict:
    """
    Unwrap OpenAI function-calling format to flat schema.

    Handles both formats:
    - Wrapped: {"type": "function", "function": {"name": ..., "description": ...}}
    - Flat: {"name": ..., "description": ...}

    Returns the inner function definition.
    """
    if schema.get("type") == "function" and "function" in schema:
        return schema["function"]
    return schema


def _build_tool_descriptions(tool_schemas: list[dict]) -> str:
    """Build a condensed tool description for the prompt."""
    lines = []
    for schema in tool_schemas:
        func = _unwrap_schema(schema)
        name = func.get("name", "")
        desc = func.get("description", "")
        params = func.get("parameters", {}).get("properties", {})

        param_strs = []
        for p_name, p_info in params.items():
            p_type = p_info.get("type", "string")
            param_strs.append(f"{p_name}: {p_type}")

        params_str = f"({', '.join(param_strs)})" if param_strs else "()"
        lines.append(f"- {name}{params_str}: {desc}")

    return "\n".join(lines)


def _build_extraction_prompt(
    query: str,
    tool_schemas: list[dict],
    case_context: Optional[str] = None,
) -> str:
    """Build the prompt for intent extraction."""
    tools_desc = _build_tool_descriptions(tool_schemas)

    prompt = f"""Available tools:
{tools_desc}

User query: "{query}"
"""

    if case_context:
        prompt += f"\nCase context: {case_context}\n"

    prompt += """
Respond in JSON format:
{
  "tool": "tool_name",
  "params": {"param1": "value1"},
  "confidence": 0.85,
  "interpretation": "Brief explanation of what the user wants",
  "alternatives": ["alternative interpretation 1", "alternative interpretation 2"]
}

If no tool matches, use tool="none" with confidence=0.0 and explain in alternatives."""

    return prompt


def _parse_json_response(text: str) -> Optional[dict]:
    """Parse JSON from Ollama response, handling markdown code blocks."""
    # Try to extract JSON from markdown code block
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if json_match:
        text = json_match.group(1)

    # Clean up common issues
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def extract_intent(
    query: str,
    tool_schemas: list[dict],
    case_context: Optional[str] = None,
    model: Optional[str] = None,
) -> IntentResult:
    """
    Extract user intent from natural language query.

    Args:
        query: User's natural language query
        tool_schemas: List of tool JSON schemas from registry
        case_context: Optional context about the current case
        model: Optional Ollama model (default: mistral:7b)

    Returns:
        IntentResult with extracted intent or error
    """
    if not query.strip():
        return IntentResult(success=False, error="Empty query")

    if not tool_schemas:
        return IntentResult(success=False, error="No tools available")

    # Use mistral:7b for intent extraction (lighter than summary model)
    model = model or "mistral:7b"

    client = get_ollama_client()

    # Check if Ollama is available
    if not client.is_available():
        return IntentResult(
            success=False,
            error="Ollama is not available. Using exact command matching."
        )

    # Build prompt
    prompt = _build_extraction_prompt(query, tool_schemas, case_context)

    logger.debug(f"Extracting intent for query: {query[:50]}...")

    # Generate response
    response: OllamaResponse = client.generate(
        prompt=prompt,
        system=INTENT_SYSTEM_PROMPT,
        model=model,
        temperature=0.1,  # Low temperature for consistent parsing
        max_tokens=512,
    )

    if not response.success:
        return IntentResult(
            success=False,
            error=f"Ollama error: {response.error}"
        )

    # Parse JSON response
    parsed = _parse_json_response(response.text)

    if not parsed:
        logger.warning(f"Could not parse intent response: {response.text[:200]}")
        return IntentResult(
            success=False,
            error="Could not parse intent from response"
        )

    # Extract fields
    tool_name = parsed.get("tool", "none") or "none"  # Handle null JSON value
    params = parsed.get("params", {})
    confidence = float(parsed.get("confidence", 0.0))
    interpretation = parsed.get("interpretation", "")
    alternatives = parsed.get("alternatives", [])

    # Validate tool exists - unwrap schemas and filter out None names
    valid_tools = {
        _unwrap_schema(s).get("name")
        for s in tool_schemas
    } - {None}  # Remove None in case of malformed schemas

    if tool_name and tool_name != "none" and tool_name not in valid_tools:
        # Try to find closest match
        for valid_name in valid_tools:
            if valid_name and (tool_name.lower() in valid_name.lower() or valid_name.lower() in tool_name.lower()):
                tool_name = valid_name
                confidence *= 0.9  # Slight penalty for fuzzy match
                break
        else:
            # No match found
            return IntentResult(
                success=True,
                intent=ExtractedIntent(
                    tool_name="none",
                    confidence=0.0,
                    interpretation=f"Unknown tool: {tool_name}",
                    alternatives=[f"Did you mean one of: {', '.join(list(valid_tools)[:5])}?"],
                    raw_response=response.text,
                )
            )

    intent = ExtractedIntent(
        tool_name=tool_name,
        parameters=params,
        confidence=min(1.0, max(0.0, confidence)),  # Clamp to 0-1
        interpretation=interpretation,
        alternatives=alternatives if isinstance(alternatives, list) else [alternatives],
        raw_response=response.text,
    )

    logger.debug(
        f"Extracted intent: {tool_name} (confidence: {confidence:.0%})"
    )

    return IntentResult(success=True, intent=intent)


def format_confirmation(intent: ExtractedIntent) -> str:
    """
    Format extracted intent for user confirmation.

    Args:
        intent: Extracted intent to format

    Returns:
        Formatted confirmation message
    """
    lines = []

    # Main interpretation
    if intent.interpretation:
        lines.append(f"I understood: {intent.interpretation}")
    else:
        lines.append(f"I understood: Execute '{intent.tool_name}'")

    # Parameters if any
    if intent.parameters:
        param_strs = [f"{k}={repr(v)}" for k, v in intent.parameters.items()]
        lines.append(f"  Parameters: {', '.join(param_strs)}")

    # Confidence indicator
    if intent.confidence >= 0.8:
        confidence_str = "high"
    elif intent.confidence >= 0.5:
        confidence_str = "medium"
    else:
        confidence_str = "low"
    lines.append(f"  Confidence: {intent.confidence:.0%} ({confidence_str})")

    # Alternatives if confidence is not high
    if intent.confidence < 0.8 and intent.alternatives:
        lines.append("  Other possibilities:")
        for alt in intent.alternatives[:3]:
            lines.append(f"    - {alt}")

    return "\n".join(lines)


def format_confirmation_prompt(intent: ExtractedIntent) -> str:
    """
    Format a confirmation prompt for the user.

    Args:
        intent: Extracted intent

    Returns:
        Confirmation prompt string
    """
    confirmation = format_confirmation(intent)

    if intent.confidence >= 0.8:
        return f"{confirmation}\n[Y] Execute  [N] Cancel"
    elif intent.confidence >= 0.5:
        return f"{confirmation}\n[Y] Execute  [N] Cancel  [?] Show alternatives"
    else:
        return f"{confirmation}\n[1-3] Select option  [N] Cancel  [?] Clarify"
