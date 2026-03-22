"""Tests for build_knowledge_tool_registry adapter."""
from __future__ import annotations

from typing import Any

import pytest

from polisyos.scientist.agent.tools.knowledge_tools_adapter import (
    build_knowledge_tool_registry,
)
from polisyos.scientist.agent.tools.registry import ToolRegistry


class MockKnowledgeToolkit:
    """Minimal mock toolkit with a few representative methods."""

    def search_datasets(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for datasets matching a query."""
        return [{"id": "ds-001", "name": f"Mock result for {query}"}]

    def find_datasets_for_metric(self, metric: str) -> list[dict[str, Any]]:
        """Find datasets that contain a specific metric."""
        return [{"metric": metric}]

    def search_evidence(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        """Search for causal evidence."""
        return []

    def get_parameter_prior(self, parameter: str) -> dict[str, Any]:
        """Get prior distribution for a parameter."""
        return {"parameter": parameter, "mean": 0.0}

    def search_legal_provisions(self, query: str) -> list[dict[str, Any]]:
        """Search for legal provisions."""
        return []

    def _private_method(self) -> None:
        """Should not be exposed."""

    def format_results(self) -> str:
        """Methods starting with format_ should be excluded."""
        return ""


class TestBuildKnowledgeToolRegistry:
    def test_returns_registry(self):
        toolkit = MockKnowledgeToolkit()
        registry = build_knowledge_tool_registry(toolkit)
        assert isinstance(registry, ToolRegistry)

    def test_registered_methods(self):
        toolkit = MockKnowledgeToolkit()
        registry = build_knowledge_tool_registry(toolkit)
        defs = registry.list_definitions()
        names = {d.name for d in defs}
        assert "search_datasets" in names
        assert "find_datasets_for_metric" in names
        assert "search_evidence" in names
        assert "get_parameter_prior" in names
        assert "search_legal_provisions" in names

    def test_private_methods_excluded(self):
        toolkit = MockKnowledgeToolkit()
        registry = build_knowledge_tool_registry(toolkit)
        defs = registry.list_definitions()
        names = {d.name for d in defs}
        assert "_private_method" not in names

    def test_format_methods_excluded(self):
        toolkit = MockKnowledgeToolkit()
        registry = build_knowledge_tool_registry(toolkit)
        defs = registry.list_definitions()
        names = {d.name for d in defs}
        assert "format_results" not in names

    def test_tool_definition_has_valid_schema(self):
        toolkit = MockKnowledgeToolkit()
        registry = build_knowledge_tool_registry(toolkit)
        defn, _ = registry.get("search_datasets")
        assert defn.parameters["type"] == "object"
        assert "query" in defn.parameters["properties"]
        assert defn.parameters["properties"]["query"]["type"] == "string"

    def test_required_params_detected(self):
        toolkit = MockKnowledgeToolkit()
        registry = build_knowledge_tool_registry(toolkit)
        defn, _ = registry.get("search_datasets")
        assert "query" in defn.parameters["required"]
        # 'limit' has a default, so it should NOT be required
        assert "limit" not in defn.parameters["required"]

    def test_tool_execution(self):
        toolkit = MockKnowledgeToolkit()
        registry = build_knowledge_tool_registry(toolkit)
        result = registry.execute("search_datasets", {"query": "gdp"})
        assert result.error is None
        assert isinstance(result.result, list)
        assert result.result[0]["name"] == "Mock result for gdp"

    def test_domain_inference(self):
        toolkit = MockKnowledgeToolkit()
        registry = build_knowledge_tool_registry(toolkit)
        defn, _ = registry.get("search_datasets")
        assert defn.domain == "datasets"
        defn2, _ = registry.get("search_evidence")
        assert defn2.domain == "academic"
        defn3, _ = registry.get("search_legal_provisions")
        assert defn3.domain == "legal"

    def test_openai_tools_format(self):
        toolkit = MockKnowledgeToolkit()
        registry = build_knowledge_tool_registry(toolkit)
        tools = registry.to_openai_tools()
        assert all(t["type"] == "function" for t in tools)
        names = {t["function"]["name"] for t in tools}
        assert "search_datasets" in names
