"""Tool definition schema for LLM function-calling."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolDefinition(BaseModel):
    """Describes a tool that an LLM agent can invoke via function-calling."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    description: str
    parameters: dict[str, Any]  # JSON Schema object
    domain: str = ""  # "datasets" | "academic" | "legal"
    timeout_s: float = Field(default=30.0, ge=1.0, le=600.0)

    def to_openai_tool(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
