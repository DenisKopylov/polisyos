from __future__ import annotations

import pytest
from pydantic import ValidationError

import polisyos.runtime.quality.layer3_health_metric_governance as g8


def test_g8_declares_red_baseline_contract() -> None:
    assert g8.G8_SCHEMA_VERSION == (
        "policyos.policy_design_case.layer3_g8_health_metric_governance.v1"
    )
    assert g8.G8_RULE_VERSION == "policyos.layer3.g8.health_metric_governance.v1"
    assert g8.G8_SURFACE_ID == "layer3_g8_health_metric_governance_surface"
    assert g8.G8_GENERATED_ARTIFACT_FAMILY_ID == (
        "policy-design-case-layer3-g8-health-metric-governance-artifacts"
    )
    assert set(g8.G8_CANONICAL_METRIC_IDS) == {
        "envelope-expansion-rate",
        "adapter-semantic-loss",
        "governance-throughput",
        "demand-pull-vs-abstention",
        "search-recall@known-seeds+index-staleness",
    }
    assert "useful_design_rate_optimization" in g8.G8_MAY_NOT_USE_FOR
    assert "hidden_fixture_access" in g8.G8_MAY_NOT_USE_FOR
    assert "layer3_g8_metric_improved_by_threshold_lowering" in g8.ALL_ISSUE_CODES
    assert "layer3_g8_search_recall_miss_reported_as_domain_ceiling" in g8.ALL_ISSUE_CODES


def test_g8_models_are_strict_and_frozen() -> None:
    row = g8.Layer3G8Issue(
        issue_code="layer3_g8_metric_source_missing",
        ref="repo://missing",
        message="Metric source is missing.",
    )
    assert row.issue_code == "layer3_g8_metric_source_missing"
    with pytest.raises(ValidationError):
        g8.Layer3G8Issue(
            issue_code="layer3_g8_metric_source_missing",
            ref="repo://missing",
            message="Metric source is missing.",
            surprise=True,
        )
    with pytest.raises(ValidationError):
        row.ref = "repo://mutated"


def test_g8_metric_registry_preserves_g0_ledger_semantics() -> None:
    registry = g8.build_g8_health_metric_registry()

    assert registry.status == "pass"
    assert len(registry.entries) == 5
    by_id = {entry.metric_id: entry for entry in registry.entries}
    assert by_id["envelope-expansion-rate"].owner == "team-runtime-quality"
    assert by_id["governance-throughput"].owner == "principal-governance"
    assert by_id["search-recall@known-seeds+index-staleness"].trend_vocabulary == (
        "fresh_recall_ok",
        "search_ceiling",
    )
    assert by_id["search-recall@known-seeds+index-staleness"].source_ledger_ref == (
        "repo://architecture/policy_design_case/layer3_health_metric_ledgers.toml"
        "#search-recall@known-seeds+index-staleness"
    )


def test_g8_alias_normalization_accepts_existing_g1_to_g7_spellings() -> None:
    assert g8.canonical_metric_id("search-recall@known-seeds + index-staleness") == (
        "search-recall@known-seeds+index-staleness"
    )
    assert g8.canonical_metric_id(
        "search-recall@known-seeds+index-staleness(region)"
    ) == "search-recall@known-seeds+index-staleness"
    assert g8.canonical_metric_id("envelope_expansion_rate_region") == (
        "envelope-expansion-rate"
    )
    assert g8.canonical_metric_id("g4-governed-promoted-count") == (
        "governance-throughput"
    )
    assert g8.canonical_metric_id("abstention_or_blocker_rate") == (
        "demand-pull-vs-abstention"
    )
    assert g8.canonical_metric_id("g7_s14_grounded_breadth_feed_status") == (
        "demand-pull-vs-abstention"
    )
    assert g8.canonical_metric_id("search_recall.freshness_status") == (
        "search-recall@known-seeds+index-staleness"
    )
    assert g8.canonical_metric_id("gl_search_recall_freshness_status") == (
        "search-recall@known-seeds+index-staleness"
    )
    assert g8.canonical_metric_id("unknown-local-metric") is None
