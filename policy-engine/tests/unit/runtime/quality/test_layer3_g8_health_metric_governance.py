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
