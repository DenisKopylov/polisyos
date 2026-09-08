"""Tests for build_knowledge_tool_registry adapter."""

from __future__ import annotations

from typing import Any

import pytest

from polisyos.data_forge.domains.academic.knowledge.types import (
    CLAIM_VOCABULARY_PROJECTION_RULE_VERSION,
    ClaimLineageAuditPage,
    ClaimLineageAuditRecord,
    ClaimVocabularyLimitation,
    ClaimVocabularyProjectionBinding,
    ClaimVocabularySourceRowBinding,
)
from polisyos.ir.analytics.literature import VersionedClaimVocabularyEnvelope
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

    def audit_academic_claim_lineage(
        self,
        *,
        status: str = "all",
        cursor: str | None = None,
        limit: int = 100,
    ) -> ClaimLineageAuditPage:
        """Audit typed academic claim lineage without reconstruction."""
        del cursor, limit
        source = ClaimVocabularySourceRowBinding(
            source_table="ac_causal_claims_raw",
            source_schema_version="legacy_v1",
            source_identity="claim-1|work-1",
            source_row_sha256="a" * 64,
        )
        binding = ClaimVocabularyProjectionBinding(
            projection_rule_version=CLAIM_VOCABULARY_PROJECTION_RULE_VERSION,
            subject_kind="claim_row",
            source_rows=(source,),
            projected_vocabulary_sha256="b" * 64,
        )
        return ClaimLineageAuditPage(
            items=(
                ClaimLineageAuditRecord(
                    id="claim-1",
                    work_id="work-1",
                    cause="x",
                    effect="y",
                    legacy_strength_label="moderate",
                    vocabulary=VersionedClaimVocabularyEnvelope(
                        cause="x",
                        effect="y",
                        legacy_strength_label="moderate",
                    ),
                    projection_binding=binding,
                    limitations=(
                        ClaimVocabularyLimitation.AMBIGUOUS_LEGACY_VOCABULARY,
                    ),
                ),
            ),
            total_identities=69_798,
            next_cursor="opaque-cursor",
            status_filter=status,
            projection_rule_version=CLAIM_VOCABULARY_PROJECTION_RULE_VERSION,
        )

    def search_legal_provisions(self, query: str) -> list[dict[str, Any]]:
        """Search for legal provisions."""
        return []

    def _private_method(self) -> None:
        """Should not be exposed."""

    def format_results(self) -> str:
        """Methods starting with format_ should be excluded."""
        return ""


class MockScholarSearchService:
    async def scholar_web_search(self, *, query: str, max_results: int = 10) -> dict:
        return {
            "provider": "mock",
            "query": query,
            "error": None,
            "results": [{"title": f"Result for {query}", "rank": 1}],
            "max_results": max_results,
        }

    async def scholar_fetch_open(self, *, url: str) -> dict:
        return {"url": url, "status": "ok"}

    async def scholar_find_in_page(self, *, url: str, pattern: str) -> dict:
        return {
            "page": {"url": url, "status": "ok"},
            "snippets": [{"text": pattern}],
        }


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
        assert "audit_academic_claim_lineage" in names
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
        audit_defn, _ = registry.get("audit_academic_claim_lineage")
        assert audit_defn.domain == "academic"

    def test_claim_lineage_audit_serializes_typed_absence_and_binding(self):
        registry = build_knowledge_tool_registry(MockKnowledgeToolkit())

        result = registry.execute(
            "audit_academic_claim_lineage",
            {"status": "not_established", "limit": 1},
        )

        assert result.error is None
        assert result.result["total_identities"] == 69_798
        assert result.result["next_cursor"] == "opaque-cursor"
        item = result.result["items"][0]
        assert item["vocabulary"]["design_family_hint_status"] == "not_established"
        assert item["vocabulary"]["evidence_strength_status"] == "not_established"
        assert item["limitations"] == ["ambiguous_legacy_vocabulary"]
        assert item["projection_binding"]["source_rows"][0]["source_identity"] == (
            "claim-1|work-1"
        )
        assert "strength" not in item
        assert "strength" not in item["vocabulary"]

    def test_openai_tools_format(self):
        toolkit = MockKnowledgeToolkit()
        registry = build_knowledge_tool_registry(toolkit)
        tools = registry.to_openai_tools()
        assert all(t["type"] == "function" for t in tools)
        names = {t["function"]["name"] for t in tools}
        assert "search_datasets" in names

    @pytest.mark.asyncio
    async def test_merges_optional_scholar_search_tools(self):
        toolkit = MockKnowledgeToolkit()
        registry = build_knowledge_tool_registry(
            toolkit,
            scholar_search_service=MockScholarSearchService(),
        )

        names = {definition.name for definition in registry.list_definitions()}
        assert "scholar_web_search" in names
        assert "scholar_fetch_open" in names
        assert "scholar_find_in_page" in names

        result = await registry.aexecute("scholar_web_search", {"query": "minimum wage"})
        assert result.error is None
        assert result.result["provider"] == "mock"
