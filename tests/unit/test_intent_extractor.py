"""Tests for intent extraction from natural language queries."""

import json
from unittest.mock import MagicMock, patch

import pytest

from third_chair.chat.intent_extractor import (
    extract_intent,
    format_confirmation,
    format_confirmation_prompt,
    ExtractedIntent,
    IntentResult,
    _parse_json_response,
    _unwrap_schema,
    _build_tool_descriptions,
)


class TestParseJsonResponse:
    """Tests for _parse_json_response function."""

    def test_parse_plain_json(self):
        """Parses raw JSON string."""
        text = '{"tool": "search", "confidence": 0.9}'

        result = _parse_json_response(text)

        assert result is not None
        assert result["tool"] == "search"
        assert result["confidence"] == 0.9

    def test_parse_json_in_markdown_block(self):
        """Extracts JSON from ```json ... ``` block."""
        text = '''Here is the result:
```json
{"tool": "list_witnesses", "params": {}, "confidence": 0.85}
```
'''

        result = _parse_json_response(text)

        assert result is not None
        assert result["tool"] == "list_witnesses"
        assert result["confidence"] == 0.85

    def test_parse_json_in_plain_code_block(self):
        """Extracts JSON from ``` ... ``` block without json marker."""
        text = '''
```
{"tool": "search", "confidence": 0.75}
```
'''

        result = _parse_json_response(text)

        assert result is not None
        assert result["tool"] == "search"

    def test_parse_json_with_extra_text(self):
        """Finds JSON object in surrounding text."""
        text = 'Based on the query, I think: {"tool": "search", "confidence": 0.8} should work.'

        result = _parse_json_response(text)

        assert result is not None
        assert result["tool"] == "search"

    def test_returns_none_for_invalid_json(self):
        """Returns None for unparseable input."""
        invalid_texts = [
            "This is not JSON at all",
            "{invalid json",
            "{'single': 'quotes'}",  # Python dict syntax, not JSON
            "",
        ]

        for text in invalid_texts:
            result = _parse_json_response(text)
            assert result is None, f"Should return None for: {text}"

    def test_parse_json_with_whitespace(self):
        """Handles JSON with various whitespace."""
        text = '''
{
    "tool": "search",
    "params": {
        "query": "test"
    },
    "confidence": 0.9
}
'''

        result = _parse_json_response(text)

        assert result is not None
        assert result["tool"] == "search"
        assert result["params"]["query"] == "test"


class TestUnwrapSchema:
    """Tests for _unwrap_schema function."""

    def test_unwrap_function_format(self):
        """Extracts function def from OpenAI format."""
        wrapped = {
            "type": "function",
            "function": {
                "name": "search_evidence",
                "description": "Search evidence",
                "parameters": {"type": "object"},
            },
        }

        result = _unwrap_schema(wrapped)

        assert result["name"] == "search_evidence"
        assert result["description"] == "Search evidence"

    def test_pass_through_flat_format(self):
        """Returns flat schema unchanged."""
        flat = {
            "name": "search_evidence",
            "description": "Search evidence",
            "parameters": {"type": "object"},
        }

        result = _unwrap_schema(flat)

        assert result == flat


class TestBuildToolDescriptions:
    """Tests for _build_tool_descriptions function."""

    def test_builds_description_list(self, sample_tool_schemas: list[dict]):
        """Builds readable tool descriptions."""
        result = _build_tool_descriptions(sample_tool_schemas)

        assert "search_evidence" in result
        assert "list_witnesses" in result
        assert "show_timeline" in result
        assert "query: string" in result

    def test_handles_empty_schemas(self):
        """Returns empty string for empty list."""
        result = _build_tool_descriptions([])

        assert result == ""


class TestExtractIntent:
    """Tests for extract_intent function."""

    def test_empty_query_returns_error(self, sample_tool_schemas: list[dict]):
        """Empty query returns IntentResult with error."""
        result = extract_intent("", sample_tool_schemas)

        assert result.success is False
        assert result.error == "Empty query"
        assert result.intent is None

    def test_whitespace_query_returns_error(self, sample_tool_schemas: list[dict]):
        """Whitespace-only query returns error."""
        result = extract_intent("   ", sample_tool_schemas)

        assert result.success is False
        assert result.error == "Empty query"

    def test_no_tools_returns_error(self):
        """Empty tool list returns error."""
        result = extract_intent("search for evidence", [])

        assert result.success is False
        assert result.error == "No tools available"

    def test_ollama_unavailable_returns_error(self, sample_tool_schemas: list[dict], mock_ollama_unavailable):
        """Returns graceful error when Ollama down."""
        result = extract_intent("search for evidence", sample_tool_schemas)

        assert result.success is False
        assert "not available" in result.error

    def test_successful_extraction(self, sample_tool_schemas: list[dict], mock_ollama):
        """Successfully extracts intent from query."""
        result = extract_intent("find evidence about the incident", sample_tool_schemas)

        assert result.success is True
        assert result.intent is not None
        assert result.intent.tool_name == "search_evidence"
        assert result.intent.confidence > 0

    def test_ollama_error_response(self, sample_tool_schemas: list[dict]):
        """Handles Ollama error response."""
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.error = "Connection refused"

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.generate.return_value = mock_response

        with patch("third_chair.chat.intent_extractor.get_ollama_client", return_value=mock_client):
            result = extract_intent("search for evidence", sample_tool_schemas)

        assert result.success is False
        assert "Connection refused" in result.error

    def test_unparseable_response(self, sample_tool_schemas: list[dict]):
        """Handles unparseable Ollama response."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = "I don't understand that query at all."

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.generate.return_value = mock_response

        with patch("third_chair.chat.intent_extractor.get_ollama_client", return_value=mock_client):
            result = extract_intent("search for evidence", sample_tool_schemas)

        assert result.success is False
        assert "Could not parse intent" in result.error

    def test_unknown_tool_returns_none_intent(self, sample_tool_schemas: list[dict]):
        """Unknown tool name returns intent with tool_name='none'."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "tool": "nonexistent_tool",
            "params": {},
            "confidence": 0.8,
            "interpretation": "Unknown tool",
            "alternatives": [],
        })

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.generate.return_value = mock_response

        with patch("third_chair.chat.intent_extractor.get_ollama_client", return_value=mock_client):
            result = extract_intent("do something unknown", sample_tool_schemas)

        assert result.success is True
        assert result.intent.tool_name == "none"
        assert result.intent.confidence == 0.0

    def test_fuzzy_match_tool_name(self, sample_tool_schemas: list[dict]):
        """Fuzzy matches close tool names."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "tool": "search",  # Partial match for "search_evidence"
            "params": {"query": "test"},
            "confidence": 0.85,
            "interpretation": "Search for test",
            "alternatives": [],
        })

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.generate.return_value = mock_response

        with patch("third_chair.chat.intent_extractor.get_ollama_client", return_value=mock_client):
            result = extract_intent("search for test", sample_tool_schemas)

        assert result.success is True
        assert result.intent.tool_name == "search_evidence"
        # Confidence slightly reduced for fuzzy match
        assert result.intent.confidence < 0.85

    def test_confidence_clamped_to_range(self, sample_tool_schemas: list[dict]):
        """Confidence values are clamped to 0-1 range."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = json.dumps({
            "tool": "search_evidence",
            "params": {},
            "confidence": 1.5,  # Out of range
            "interpretation": "Search",
            "alternatives": [],
        })

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.generate.return_value = mock_response

        with patch("third_chair.chat.intent_extractor.get_ollama_client", return_value=mock_client):
            result = extract_intent("search", sample_tool_schemas)

        assert result.intent.confidence == 1.0


class TestExtractedIntent:
    """Tests for ExtractedIntent dataclass."""

    def test_default_values(self):
        """Default values are set correctly."""
        intent = ExtractedIntent(tool_name="test")

        assert intent.tool_name == "test"
        assert intent.parameters == {}
        assert intent.confidence == 0.0
        assert intent.interpretation == ""
        assert intent.alternatives == []
        assert intent.raw_response == ""


class TestFormatConfirmation:
    """Tests for format_confirmation function."""

    def test_high_confidence_format(self):
        """High confidence shows interpretation and parameters."""
        intent = ExtractedIntent(
            tool_name="search_evidence",
            parameters={"query": "incident"},
            confidence=0.95,
            interpretation="Search for evidence about the incident",
        )

        result = format_confirmation(intent)

        assert "Search for evidence about the incident" in result
        assert "query=" in result
        assert "95%" in result
        assert "high" in result

    def test_low_confidence_shows_alternatives(self):
        """Low confidence includes alternatives."""
        intent = ExtractedIntent(
            tool_name="search_evidence",
            parameters={},
            confidence=0.45,
            interpretation="Maybe search?",
            alternatives=["Could be list_witnesses", "Could be show_timeline"],
        )

        result = format_confirmation(intent)

        assert "45%" in result
        assert "low" in result
        assert "Other possibilities" in result
        assert "Could be list_witnesses" in result

    def test_medium_confidence_format(self):
        """Medium confidence shows appropriate indicator."""
        intent = ExtractedIntent(
            tool_name="search_evidence",
            parameters={},
            confidence=0.65,
            interpretation="Search evidence",
        )

        result = format_confirmation(intent)

        assert "65%" in result
        assert "medium" in result

    def test_no_interpretation_uses_tool_name(self):
        """Falls back to tool name if no interpretation."""
        intent = ExtractedIntent(
            tool_name="search_evidence",
            parameters={},
            confidence=0.8,
            interpretation="",
        )

        result = format_confirmation(intent)

        assert "search_evidence" in result


class TestFormatConfirmationPrompt:
    """Tests for format_confirmation_prompt function."""

    def test_high_confidence_options(self):
        """High confidence shows Y/N options."""
        intent = ExtractedIntent(
            tool_name="search_evidence",
            confidence=0.9,
            interpretation="Search",
        )

        result = format_confirmation_prompt(intent)

        assert "[Y] Execute" in result
        assert "[N] Cancel" in result

    def test_medium_confidence_options(self):
        """Medium confidence shows alternatives option."""
        intent = ExtractedIntent(
            tool_name="search_evidence",
            confidence=0.7,
            interpretation="Search",
        )

        result = format_confirmation_prompt(intent)

        assert "[Y] Execute" in result
        assert "[?] Show alternatives" in result

    def test_low_confidence_options(self):
        """Low confidence shows numbered selection."""
        intent = ExtractedIntent(
            tool_name="search_evidence",
            confidence=0.3,
            interpretation="Maybe search",
            alternatives=["Alt 1", "Alt 2"],
        )

        result = format_confirmation_prompt(intent)

        assert "[1-3] Select option" in result
        assert "[?] Clarify" in result
