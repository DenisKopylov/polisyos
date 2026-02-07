from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.backtest import BacktestReport, BacktestScenario, persist_backtest_report
from polisyos.ir.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    persist_causal_effect_report,
)
from polisyos.ir.hte import (
    HTEResult,
    PolicyRecommendation,
    TargetingRule,
    persist_hte_result,
    persist_policy_recommendation,
)
from polisyos.ir.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_BACKTEST_REPORT_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_HTE_RESULT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_POLICY_RECOMMENDATION_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)


def test_build_decision_packet_node_emits_v3_payload_and_manifest_inputs(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_v3")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = store.put_json(
        {"trinity": {}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        {
            "data_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.state_snapshot",
                "media_type": "application/json",
            }
        },
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"applied_nodes": 1, "status": "ok"}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    governance_ref = store.put_json(
        GovernanceReport(verdict="approve", issues=[]),
        PutOptions(kind="scientist.governance_report", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_packet_v3",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_METRICS_REF: metrics_ref},
        reports_index={REPORT_GOVERNANCE_REPORT_REF: governance_ref},
        params={"random_seed": 123},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    manifest = store.get_manifest(packet_ref.artifact_id)
    roles = {item.role for item in manifest.inputs}

    assert payload["schema_version"] == "3.1"
    assert payload["seed"] == 123
    assert payload["replay"]["strategy_hint"] == "scientist"
    assert payload["uncertainty"]["envelope_count"] == 0
    assert payload["inputs"]["trinity_bundle_ref"] == str(trinity_ref.artifact_id)
    assert payload["artifacts"]["metrics_ref"] == str(metrics_ref.artifact_id)
    assert payload["artifacts"]["governance_report_ref"] == str(governance_ref.artifact_id)
    assert "input.trinity_bundle_ref" in roles
    assert "input.registry_bundle_ref" in roles
    assert "input.data_snapshot_ref" in roles
    assert "artifact.metrics_ref" in roles
    assert "artifact.governance_report_ref" in roles


def test_build_decision_packet_node_accepts_float_uncertainty_bounds(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_unc")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = store.put_json(
        {"trinity": {}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        {
            "data_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.state_snapshot",
                "media_type": "application/json",
            }
        },
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"applied_nodes": 1, "step_latency_ms": 12}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    env_ref = persist_uncertainty_envelope(
        store,
        UncertaintyEnvelope(
            point_estimate=12.0,
            confidence_interval=(10.0, 15.0),
            confidence_level=0.95,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.ENSEMBLE,
            propagation_method=PropagationMethod.DELTA_METHOD,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        ),
    )
    sim_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
            uncertainty_envelopes={"step_latency_ms": env_ref},
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_packet_unc",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_METRICS_REF: metrics_ref,
            ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref,
        },
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    bounds = payload["uncertainty_bounds"]

    assert isinstance(bounds, dict)
    assert bounds["step_latency_ms_lower"] == 10.0
    assert bounds["step_latency_ms_upper"] == 15.0


def test_build_decision_packet_includes_causal_section(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_causal")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = store.put_json(
        {"trinity": {}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        {
            "data_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.state_snapshot",
                "media_type": "application/json",
            }
        },
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    report_ref = persist_causal_effect_report(
        store,
        CausalEffectReport(
            method=CausalMethod.SYNTHETIC_CONTROL,
            status=EstimationStatus.SUCCESS,
            estimand="ATT",
            point_estimate=2.5,
            confidence_interval=(1.0, 4.0),
            confidence_level=0.95,
            inference_method="bootstrap",
            sample_size=120,
            n_treated=1,
            n_control=12,
            pre_periods=10,
            post_periods=5,
        ),
    )
    envelope_ref = persist_uncertainty_envelope(
        store,
        UncertaintyEnvelope(
            point_estimate=2.5,
            confidence_interval=(1.0, 4.0),
            confidence_level=0.95,
            distribution_family=DistributionFamily.BOOTSTRAP,
            source=UncertaintySource.CAUSAL,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        ),
    )

    state = ExperimentState(
        run_id="R_packet_causal",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_CAUSAL_REPORT_REF: report_ref,
            ARTIFACT_CAUSAL_ENVELOPE_REF: envelope_ref,
        },
    )
    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["causal"]["status"] == "success"
    assert payload["causal"]["method"] == "synthetic_control"
    assert payload["uncertainty_bounds"]["causal_effect_point"] == 2.5


def test_build_decision_packet_includes_hte_and_backtest_sections(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_hte_bt")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = store.put_json(
        {"trinity": {}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        {
            "data_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.state_snapshot",
                "media_type": "application/json",
            }
        },
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )

    hte_ref = persist_hte_result(
        store,
        HTEResult(
            method=CausalMethod.CAUSAL_FOREST,
            ate=0.2,
            ate_ci_lower=0.1,
            ate_ci_upper=0.3,
            cate_values=[0.2, 0.3],
            n_samples=2,
            n_treated=1,
            n_control=1,
            n_features=1,
            feature_names=["income"],
        ),
    )
    recommendation_ref = persist_policy_recommendation(
        store,
        PolicyRecommendation(
            budget_constraint=10.0,
            targeting_rules=[
                TargetingRule(
                    rule_id="rule_1",
                    predicate="income < 50k",
                    priority=1,
                    expected_cate=0.3,
                    expected_cost_per_unit=1.0,
                    n_eligible_units=1,
                    cumulative_budget_share=1.0,
                )
            ],
            total_expected_effect=0.3,
            total_cost=1.0,
            n_targeted_units=1,
            n_total_units=2,
        ),
    )
    backtest_ref = persist_backtest_report(
        store,
        BacktestReport(
            report_id="BT_1",
            scenarios=[BacktestScenario(scenario_id="s1", scenario_label="s1")],
            n_scenarios=1,
            n_metrics_evaluated=0,
            trust_score=0.72,
            trust_grade="B",
        ),
    )

    state = ExperimentState(
        run_id="R_packet_hte_bt",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_HTE_RESULT_REF: hte_ref,
            ARTIFACT_POLICY_RECOMMENDATION_REF: recommendation_ref,
            ARTIFACT_BACKTEST_REPORT_REF: backtest_ref,
        },
    )
    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["hte"]["result_ref"] == str(hte_ref.artifact_id)
    assert payload["targeting"]["recommendation_ref"] == str(recommendation_ref.artifact_id)
    assert payload["backtest"]["report_ref"] == str(backtest_ref.artifact_id)
    assert payload["trust_profile"]["backtest_trust_grade"] == "B"
