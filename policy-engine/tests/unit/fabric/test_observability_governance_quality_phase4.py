from __future__ import annotations

from datetime import UTC, datetime

import polisyos.fabric.connectors.components as connector_components
import pytest
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.fabric.connectors.governance_metadata import (
    validate_connector_governance_metadata,
)
from polisyos.fabric.connectors.quality.report import (
    DataQualityReport,
    FreshnessLevel,
    FreshnessStatus,
)
from polisyos.fabric.observability import (
    DEFAULT_FABRIC_SLO_TARGETS,
    FabricReliabilityBudgetError,
    FabricSLIName,
    assert_fabric_feature_expansion_allowed,
    build_fabric_health_snapshot,
    evaluate_fabric_reliability_budget,
)
from polisyos.fabric.provenance.lineage import (
    FabricLineageTracker,
    impact_analysis,
    trace_claim_origin,
)
from polisyos.fabric.quality import QualityIndicators
from polisyos.ir.connectors import QualityTier
from polisyos.scientist.governance.passes.quality_gate_pass import QualityGatePass


class _CollectingAlertSink:
    def __init__(self) -> None:
        self.alerts = []

    def emit(self, alert) -> None:
        self.alerts.append(alert)


def _passing_sli_observations() -> dict[FabricSLIName, float]:
    return {
        FabricSLIName.FETCH_SUCCESS: 0.999,
        FabricSLIName.SCHEMA_COMPLIANCE: 1.0,
        FabricSLIName.DATA_FRESHNESS: 300.0,
        FabricSLIName.MATERIALIZATION_FRESHNESS: 120.0,
        FabricSLIName.LINEAGE_COVERAGE: 1.0,
        FabricSLIName.REPLAY_SUCCESS: 1.0,
        FabricSLIName.QUARANTINE_RATE: 0.0,
        FabricSLIName.QUERY_LATENCY: 0.25,
    }


def test_fabric_slo_contract_covers_phase4_slis_and_blocks_burned_budget() -> None:
    target_names = {target.name for target in DEFAULT_FABRIC_SLO_TARGETS}
    assert target_names == set(FabricSLIName)

    healthy = evaluate_fabric_reliability_budget(_passing_sli_observations())

    assert healthy.feature_expansion_allowed is True
    assert all(assessment.healthy for assessment in healthy.assessments)
    assert assert_fabric_feature_expansion_allowed(healthy) is healthy

    burned = {
        **_passing_sli_observations(),
        FabricSLIName.FETCH_SUCCESS: 0.97,
        FabricSLIName.QUERY_LATENCY: 4.0,
    }
    report = evaluate_fabric_reliability_budget(burned)

    assert report.feature_expansion_allowed is False
    assert "P0" in report.paused_priorities
    assert "P1" in report.paused_priorities
    assert any("fetch_success" in reason for reason in report.reasons)
    assert any("query_latency" in reason for reason in report.reasons)
    with pytest.raises(FabricReliabilityBudgetError):
        assert_fabric_feature_expansion_allowed(report)


def test_fabric_health_snapshot_includes_slo_component_when_observations_are_supplied(
    tmp_path,
) -> None:
    class _Metrics:
        def __init__(self) -> None:
            self.assessments = []

        def record_fabric_slo_assessment(self, **payload) -> None:
            self.assessments.append(payload)

    sink = _CollectingAlertSink()
    metrics = _Metrics()
    observations = {
        **_passing_sli_observations(),
        FabricSLIName.LINEAGE_COVERAGE: 0.50,
    }

    snapshot = build_fabric_health_snapshot(
        fact_log_root=tmp_path,
        sli_observations=observations,
        alert_sink=sink,
        metrics=metrics,
    )

    slo = next(component for component in snapshot.components if component.name == "slo")
    assert snapshot.healthy is False
    assert slo.healthy is False
    assert any("lineage_coverage" in reason for reason in slo.reasons)
    assert [alert.component for alert in sink.alerts] == ["slo"]
    assert {item["sli_name"] for item in metrics.assessments} == {
        sli.value for sli in FabricSLIName
    }
    lineage_metric = next(
        item for item in metrics.assessments if item["sli_name"] == "lineage_coverage"
    )
    assert lineage_metric["healthy"] is False
    assert lineage_metric["burn_ratio"] > 1.0


def test_builtin_production_connectors_have_phase4_governance_metadata() -> None:
    components = connector_components.__polisyos_components__
    assert components

    reports = [
        validate_connector_governance_metadata(component.connector_class.metadata)
        for component in components
    ]

    failures = {
        report.connector_id: [f"{issue.field}: {issue.message}" for issue in report.issues]
        for report in reports
        if not report.passed
    }
    assert failures == {}


def test_fabric_quality_evidence_propagates_to_scientist_governance() -> None:
    report = DataQualityReport(
        dataset_id="worldbank.wdi.generic",
        schema_id="worldbank.wdi.generic",
        validated_at=datetime(2026, 4, 27, tzinfo=UTC),
        score=0.96,
        tier=QualityTier.GOLD,
        grade="A",
        freshness_status=FreshnessStatus(
            level=FreshnessLevel.FRESH,
            cache_age_seconds=0,
            data_age_seconds=3600,
            ttl_seconds=86_400,
            schedule="daily",
            last_updated=datetime(2026, 4, 27, tzinfo=UTC),
            fetched_at=datetime(2026, 4, 27, 1, tzinfo=UTC),
            message="fresh",
        ),
        completeness_score=0.98,
        consistency_score=0.99,
        quality_indicators=QualityIndicators(
            metric_id="worldbank.wdi.generic",
            missingness=0.02,
            staleness_days=0,
            coverage=1.0,
            row_count=500,
            computation_method="connector_quality_validator",
        ),
        row_count=500,
        source_id="worldbank.wdi",
        component_scores={"freshness": 1.0, "completeness": 0.98, "consistency": 0.99},
    )
    state = {"data_quality_report": report}
    ctx = PassContext(
        ir=None,
        state=state,
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="phase4-quality",
    )

    issues = QualityGatePass().validate(ctx)

    assert not issues
    evidence = ctx.state["fabric_quality_evidence"]
    assert evidence["schema_version"] == "fabric.quality.evidence.v1"
    assert evidence["dataset_id"] == "worldbank.wdi.generic"
    assert evidence["quality_indicators"]["metric_id"] == "worldbank.wdi.generic"
    assert evidence["acceptable"] is True
    assert ctx.state["fabric_quality_evidence_by_dataset"]["worldbank.wdi.generic"] == evidence


def test_lineage_answers_origin_and_impact_for_decision_bearing_fields() -> None:
    tracker = FabricLineageTracker("graph.phase4.decision")
    tracker.register_source_dataset(
        connector_id="worldbank.wdi",
        dataset_id="NY.GDP.MKTP.CD",
        fields=["gdp_local"],
        schema_id="worldbank.wdi.generic",
        evidence_ref="evidence.phase4",
    )
    _activity, outputs = tracker.record_transform_stage(
        stage_name="normalize",
        started_at=datetime(2026, 4, 27, tzinfo=UTC),
        completed_at=datetime(2026, 4, 27, 0, 0, 1, tzinfo=UTC),
        input_columns=["gdp_local"],
        output_columns=["decision_gdp_usd"],
        parameters={"field_mappings": {"gdp_local": "decision_gdp_usd"}},
        evidence_refs=["evidence.phase4"],
    )
    claim = tracker.record_claim_field(
        claim_id="policy-claim-1",
        field_name="decision_value",
        source_columns=["decision_gdp_usd"],
        evidence_ref="evidence.phase4",
        world_event_id="event.phase4",
    )
    query = tracker.record_query_result_field(
        query_id="decision-query-1",
        field_name="decision_gdp_usd",
        source_nodes=[claim, outputs["decision_gdp_usd"]],
        query_hash="phase4-query",
    )

    trace = trace_claim_origin(tracker.graph, "policy-claim-1", field="decision_value")
    downstream = impact_analysis(tracker.graph, "worldbank.wdi.generic", "gdp_local")

    assert any(node.kind == "source_field" for node in trace.nodes)
    assert any(node.kind == "evidence_bundle" for node in trace.nodes)
    assert claim in downstream.claim_fields
    assert query in downstream.query_result_fields
