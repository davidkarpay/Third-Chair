"""Tool definitions for the Chat Research Assistant.

Defines the Tool dataclass and all available tools that can be invoked
by the function caller to query case data.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional


class ParameterType(str, Enum):
    """JSON Schema parameter types."""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolParameter:
    """A parameter for a tool function."""
    name: str
    param_type: ParameterType
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[list[str]] = None


@dataclass
class ToolResult:
    """Result from a tool invocation."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    tool_name: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "tool_name": self.tool_name,
        }


@dataclass
class Tool:
    """A tool that can be invoked by the chat assistant."""
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    handler: Optional[Callable] = None
    category: str = "general"

    def to_json_schema(self) -> dict:
        """Convert tool to JSON schema for function calling."""
        properties = {}
        required = []

        for param in self.parameters:
            prop = {
                "type": param.param_type.value,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default

            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        }

    def invoke(self, **kwargs) -> ToolResult:
        """Invoke the tool with the given arguments."""
        if not self.handler:
            return ToolResult(
                success=False,
                error=f"No handler registered for tool: {self.name}",
                tool_name=self.name,
            )

        try:
            result = self.handler(**kwargs)
            return ToolResult(
                success=True,
                data=result,
                tool_name=self.name,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                tool_name=self.name,
            )
