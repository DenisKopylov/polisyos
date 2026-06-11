from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

import polisyos.runtime.quality.layer3_health_metric_governance as g8

REPO_ROOT = Path(__file__).resolve().parents[4]


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


def test_g8_source_snapshot_reads_current_g0_to_g7_and_s14_artifacts() -> None:
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)

    assert snapshot.status == "pass"
    assert snapshot.source_count >= 44
    refs = {source.source_ref for source in snapshot.sources}
    assert "repo://architecture/policy_design_case/layer3_health_metric_ledgers.toml" in refs
    assert "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json" in refs
    assert "repo://architecture/policy_design_case/layer3_g4_governance_throughput_delta.json" in refs
    assert "repo://architecture/policy_design_case/layer3_g5_health_metric_delta.toml" in refs
    assert (
        "repo://architecture/policy_design_case/layer3_g5_dependency_health_metric_snapshot.json"
        in refs
    )
    assert (
        "repo://architecture/policy_design_case/layer3_g5_effective_evidence_independence.json"
        in refs
    )
    assert (
        "repo://architecture/policy_design_case/layer3_g5_useful_design_metric_eligibility_join.json"
        in refs
    )
    assert (
        "repo://architecture/policy_design_case/layer3_g6_demand_pull_vs_abstention_delta.json"
        in refs
    )
    assert "repo://architecture/policy_design_case/layer3_g6_conformance_report.json" in refs
    assert (
        "repo://architecture/policy_design_case/layer3_g6_orchestration_choice_audit.json"
        in refs
    )
    assert (
        "repo://architecture/policy_design_case/layer3_g7_search_recall_freshness_join.json"
        in refs
    )
    assert "repo://architecture/policy_design_case/layer3_g7_health_metric_delta.toml" in refs
    assert (
        "repo://architecture/policy_design_case/layer3_g7_g5_g6_authority_boundary_report.json"
        in refs
    )
    assert (
        "repo://architecture/policy_design_case/layer3_g7_region_widening_audit_surface.json"
        in refs
    )
    assert (
        "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
        in refs
    )


def test_g8_normalizes_current_metric_dialects_without_losing_raw_refs() -> None:
    registry = g8.build_g8_health_metric_registry()
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    signals = g8.build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=snapshot,
    )

    assert signals.status == "pass"
    by_metric = {metric_id: [] for metric_id in g8.G8_CANONICAL_METRIC_IDS}
    for signal in signals.signals:
        by_metric[signal.metric_id].append(signal)
        assert signal.raw_source_ref.startswith("repo://architecture/policy_design_case/")
        assert signal.authoritative_for == g8.G8_AUTHORITATIVE_FOR
        assert "closeout_authority" in signal.may_not_use_for

    assert all(by_metric.values())
    search_refs = {
        signal.raw_key
        for signal in by_metric["search-recall@known-seeds+index-staleness"]
    }
    assert "search-recall@known-seeds + index-staleness" in search_refs
    assert "search-recall@known-seeds+index-staleness(region)" in search_refs
    demand_readings = by_metric["demand-pull-vs-abstention"]
    assert any(signal.raw_key == "abstention_or_blocker_rate" for signal in demand_readings)
    assert any(
        signal.slice_id == "G6"
        and signal.raw_key == "abstention_or_blocker_rate"
        and signal.status == "abstention_inertia"
        for signal in demand_readings
    )
    assert any(
        signal.slice_id == "G6"
        and signal.raw_key == "grounded_result_rate"
        and signal.status == "no_grounded_response"
        for signal in demand_readings
    )
    assert any(
        signal.slice_id == "G3"
        and signal.raw_key == "search_recall.freshness_status"
        and signal.status == "pass"
        for signal in by_metric["search-recall@known-seeds+index-staleness"]
    )
    assert any(
        signal.slice_id == "GL"
        and signal.raw_key == "known_seed_status"
        and signal.status == "pass"
        for signal in by_metric["search-recall@known-seeds+index-staleness"]
    )
    assert any(
        signal.slice_id == "G7"
        and signal.raw_key == "g7_s14_grounded_breadth_feed_status"
        and signal.status == "blocked_no_real_grounded_breadth"
        for signal in demand_readings
    )


def test_g8_metric_trend_report_exposes_all_five_ci_visible_metrics() -> None:
    registry = g8.build_g8_health_metric_registry()
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    signals = g8.build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=snapshot,
    )
    report = g8.build_g8_metric_trend_report(registry=registry, signals=signals)

    assert report.status == "pass"
    assert {row.metric_id for row in report.metric_trends} == set(g8.G8_CANONICAL_METRIC_IDS)
    by_metric = {row.metric_id: row for row in report.metric_trends}
    assert by_metric["demand-pull-vs-abstention"].latest_status in {
        "abstention_inertia",
        "blocked_by_current_g5_unchanged_blocker",
        "blocked_no_real_grounded_breadth",
        "no_grounded_response",
        "pass",
    }
    assert by_metric["search-recall@known-seeds+index-staleness"].source_refs
    assert report.ci_report_status == "first_class_metric_trends_visible"
