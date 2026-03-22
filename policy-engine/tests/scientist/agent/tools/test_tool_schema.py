"""Tests for ToolDefinition schema."""
from __future__ import annotations

import pytest

from polisyos.scientist.agent.tools.schema import ToolDefinition


class TestToolDefinition:
    def test_valid_name(self):
        td = ToolDefinition(
            name="search_datasets",
            description="Search for datasets",
            parameters={"type": "object", "properties": {}},
        )
        assert td.name == "search_datasets"

    def test_invalid_name_uppercase(self):
        with pytest.raises(Exception):
            ToolDefinition(
                name="SearchDatasets",
                description="Bad name",
                parameters={"type": "object"},
            )

    def test_invalid_name_starts_with_number(self):
        with pytest.raises(Exception):
            ToolDefinition(
                name="1bad",
                description="Bad name",
                parameters={"type": "object"},
            )

    def test_to_openai_tool_format(self):
        td = ToolDefinition(
            name="search_evidence",
            description="Search for causal evidence",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "search query"},
                },
                "required": ["query"],
            },
        )
        result = td.to_openai_tool()
        assert result["type"] == "function"
        assert result["function"]["name"] == "search_evidence"
        assert result["function"]["description"] == "Search for causal evidence"
        assert result["function"]["parameters"]["required"] == ["query"]

    def test_domain_default_empty(self):
        td = ToolDefinition(
            name="test_tool",
            description="test",
            parameters={"type": "object"},
        )
        assert td.domain == ""

    def test_domain_set(self):
        td = ToolDefinition(
            name="search_datasets",
            description="test",
            parameters={"type": "object"},
            domain="datasets",
        )
        assert td.domain == "datasets"

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            ToolDefinition(
                name="test_tool",
                description="test",
                parameters={"type": "object"},
                unknown="x",
            )
