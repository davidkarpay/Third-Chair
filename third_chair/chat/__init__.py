"""Chat Research Assistant module for Third Chair.

Provides an interactive chat interface for attorneys to research case evidence
using natural language queries. Features:
- Function calling via llama3.2 to invoke Third Chair tools
- RAG system using ChromaDB + nomic-embed-text for conversation memory
- Fact extraction and contradiction detection
- Semantic search across transcripts
"""

from .tools import (
    ParameterType,
    Tool,
    ToolParameter,
    ToolResult,
)
from .registry import ToolRegistry

__all__ = [
    "ParameterType",
    "Tool",
    "ToolParameter",
    "ToolResult",
    "ToolRegistry",
]
