"""Tests for OTel trace attribute helpers."""

from __future__ import annotations

from polisyos.scientist.engine.trace_attributes import (
    ATTR_CACHE_HIT,
    ATTR_CELL_ID,
    ATTR_DURATION_MS,
    ATTR_NODE_ALIAS,
    ATTR_NODE_ID,
    ATTR_NODE_STATUS,
    ATTR_RETRY_COUNT,
    ATTR_RUN_ID,
    ATTR_TENANT_ID,
    ATTR_TIER_INDEX,
    ATTR_WORKFLOW_ID,
    build_node_span_attributes,
    enrich_node_span_result,
)

# ---------------------------------------------------------------------------
# Attribute constants
# ---------------------------------------------------------------------------


class TestAttributeConstants:
    def test_node_level_keys(self) -> None:
        assert ATTR_NODE_ID == "polisyos.scientist.node_id"
        assert ATTR_NODE_ALIAS == "polisyos.scientist.node_alias"
        assert ATTR_TIER_INDEX == "polisyos.scientist.tier_index"
        assert ATTR_RETRY_COUNT == "polisyos.scientist.retry_count"
        assert ATTR_CACHE_HIT == "polisyos.scientist.cache_hit"

    def test_workflow_level_keys(self) -> None:
        assert ATTR_WORKFLOW_ID == "polisyos.scientist.workflow_id"
        assert ATTR_RUN_ID == "polisyos.scientist.run_id"

    def test_tenant_keys(self) -> None:
        assert ATTR_TENANT_ID == "polisyos.tenant_id"
        assert ATTR_CELL_ID == "polisyos.cell_id"

    def test_status_keys(self) -> None:
        assert ATTR_NODE_STATUS == "polisyos.scientist.node_status"
        assert ATTR_DURATION_MS == "polisyos.scientist.duration_ms"


# ---------------------------------------------------------------------------
# build_node_span_attributes
# ---------------------------------------------------------------------------


class TestBuildNodeSpanAttributes:
    def test_required_keys_present(self) -> None:
        attrs = build_node_span_attributes(
            alias="loader",
            node_id="polisyos.nodes.loader",
            workflow_id="wf-1",
        )
        assert attrs[ATTR_NODE_ALIAS] == "loader"
        assert attrs[ATTR_NODE_ID] == "polisyos.nodes.loader"
        assert attrs[ATTR_WORKFLOW_ID] == "wf-1"
        assert attrs[ATTR_TIER_INDEX] == 0
        assert attrs[ATTR_RUN_ID] == ""

    def test_optional_tenant_and_cell_excluded_when_none(self) -> None:
        attrs = build_node_span_attributes(
            alias="a",
            node_id="n",
            workflow_id="w",
        )
        assert ATTR_TENANT_ID not in attrs
        assert ATTR_CELL_ID not in attrs

    def test_tenant_and_cell_included_when_set(self) -> None:
        attrs = build_node_span_attributes(
            alias="a",
            node_id="n",
            workflow_id="w",
            tenant_id="t-1",
            cell_id="c-1",
        )
        assert attrs[ATTR_TENANT_ID] == "t-1"
        assert attrs[ATTR_CELL_ID] == "c-1"

    def test_tier_index_and_run_id(self) -> None:
        attrs = build_node_span_attributes(
            alias="a",
            node_id="n",
            workflow_id="w",
            tier_index=3,
            run_id="R_abc123",
        )
        assert attrs[ATTR_TIER_INDEX] == 3
        assert attrs[ATTR_RUN_ID] == "R_abc123"


# ---------------------------------------------------------------------------
# enrich_node_span_result
# ---------------------------------------------------------------------------


class TestEnrichNodeSpanResult:
    def test_adds_status_and_duration(self) -> None:
        attrs: dict[str, str | int | bool] = {}
        result = enrich_node_span_result(attrs, status="ok", duration_ms=150)
        assert result[ATTR_NODE_STATUS] == "ok"
        assert result[ATTR_DURATION_MS] == 150

    def test_default_cache_hit_and_retry(self) -> None:
        attrs: dict[str, str | int | bool] = {}
        enrich_node_span_result(attrs, status="ok", duration_ms=10)
        assert attrs[ATTR_CACHE_HIT] is False
        assert attrs[ATTR_RETRY_COUNT] == 0

    def test_explicit_cache_hit_and_retry(self) -> None:
        attrs: dict[str, str | int | bool] = {}
        enrich_node_span_result(
            attrs,
            status="fail",
            duration_ms=3000,
            cache_hit=True,
            retry_count=2,
        )
        assert attrs[ATTR_CACHE_HIT] is True
        assert attrs[ATTR_RETRY_COUNT] == 2

    def test_mutates_and_returns_same_dict(self) -> None:
        attrs: dict[str, str | int | bool] = {"existing": "value"}
        result = enrich_node_span_result(attrs, status="skip", duration_ms=0)
        assert result is attrs
        assert attrs["existing"] == "value"
