from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.compiler.report import CompileReport, put_compile_report, put_link_report
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.contracts.lex import ChangeProposalRef, LegalReportRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.abm_bridge import (
    ABMAlignmentReport,
    AlignmentResult,
    AlignmentStatus,
    MacroMicroMapping,
    persist_abm_alignment_report,
)
from polisyos.ir.analytics.backtest import BacktestReport, BacktestScenario, persist_backtest_report
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    RefutationResult,
    RefutationTestType,
    persist_causal_effect_report,
)
from polisyos.ir.analytics.causal_ensemble import (
    CausalModelEnsemble,
    EnsembleMember,
    persist_causal_model_ensemble,
)
from polisyos.ir.analytics.hte import (
    HTEResult,
    PolicyRecommendation,
    TargetingRule,
    persist_hte_result,
    persist_policy_recommendation,
)
from polisyos.ir.analytics.sensitivity import SensitivityResult, persist_sensitivity_result
from polisyos.ir.analytics.transportability import (
    TransportabilityResult,
    TransportabilityStatus,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.ir.linker import LinkIssue, LinkIssueCode, LinkReport, LinkSeverity
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.governance.report import GovernanceReport, GovernanceReportLinks
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
    ARTIFACT_BACKTEST_REPORT_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_HTE_RESULT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_POLICY_RECOMMENDATION_REF,
    ARTIFACT_SENSITIVITY_RESULT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_CHANGE_PROPOSAL_REF,
    REPORT_COMPILE_REPORT_REF,
    REPORT_GOVERNANCE_REPORT_REF,
    REPORT_LEGAL_REPORT_REF,
    REPORT_LINK_REPORT_REF,
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

    assert payload["schema_version"] == "3.2"
    assert payload["seed"] == 123
    assert payload["policy_summary"] == "Policy data attached"
    assert payload["replay"]["strategy_hint"] == "scientist"
    assert payload["replay"]["why_partial"] == ["missing_optional_inputs"]
    assert "input_bindings_ref" in payload["replay"]["missing_refs"]
    assert payload["uncertainty"]["envelope_count"] == 0
    assert payload["diagnostics_summary"]["replay_readiness"] == "partial"
    assert payload["diagnostics_summary"]["transport_status"] == "not_run"
    assert payload["analysis_limits"]["partial_replay_readiness"] is True
    assert payload["analysis_limits"]["missing_uncertainty_artifact"] is True
    assert payload["inputs"]["trinity_bundle_ref"] == str(trinity_ref.artifact_id)
    assert payload["artifacts"]["metrics_ref"] == str(metrics_ref.artifact_id)
    assert payload["artifacts"]["governance_report_ref"] == str(governance_ref.artifact_id)
    assert "input.trinity_bundle_ref" in roles
    assert "input.registry_bundle_ref" in roles
    assert "input.data_snapshot_ref" in roles
    assert "artifact.metrics_ref" in roles
    assert "artifact.governance_report_ref" in roles


def test_build_decision_packet_surfaces_legal_links_and_contract_warnings(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_diag")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = store.put_json(
        {"policy_spec": {"interventions": []}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    data_snapshot_ref = store.put_json(
        {"data_ref": None},
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    legal_report_artifact = store.put_json(
        {"summary": {"compliance_grade": "pass"}},
        PutOptions(kind="lex.legal_report", media_type="application/json"),
    )
    change_proposal_artifact = store.put_json(
        {"actions": []},
        PutOptions(kind="lex.change_proposal", media_type="application/json"),
    )
    legal_report_ref = LegalReportRef(artifact_id=legal_report_artifact.artifact_id)
    change_proposal_ref = ChangeProposalRef(artifact_id=change_proposal_artifact.artifact_id)
    governance_ref = store.put_json(
        GovernanceReport(
            verdict="human_gate",
            issues=[],
            links=GovernanceReportLinks(
                legal_report_ref=legal_report_ref,
                change_proposal_ref=change_proposal_ref,
            ),
        ),
        PutOptions(kind="scientist.governance_report", media_type="application/json"),
    )
    link_report_ref = put_link_report(
        store,
        LinkReport(
            ok=True,
            issues=[
                LinkIssue(
                    severity=LinkSeverity.WARNING,
                    code=LinkIssueCode.DEPRECATED_MECHANISM_BINDINGS,
                    message="ignored",
                    path=["policy_spec", "mechanism_bindings"],
                ),
                LinkIssue(
                    severity=LinkSeverity.WARNING,
                    code=LinkIssueCode.MODEL_FIDELITY_LEVEL_IGNORED,
                    message="ignored",
                    path=["model_spec", "fidelity_level"],
                ),
            ],
        ),
    )
    compile_report_ref = put_compile_report(
        store,
        CompileReport(
            ok=False,
            link_report_ref=link_report_ref,
            notes=[
                "link_warning:deprecated_mechanism_bindings",
                "link_warning:model_fidelity_level_ignored",
                "missing_runtime_mechanism_support:custom_subsidy",
            ],
        ),
    )

    state = ExperimentState(
        run_id="R_packet_diag",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        reports_index={
            REPORT_GOVERNANCE_REPORT_REF: governance_ref,
            REPORT_LEGAL_REPORT_REF: legal_report_ref,
            REPORT_CHANGE_PROPOSAL_REF: change_proposal_ref,
            REPORT_LINK_REPORT_REF: link_report_ref,
            REPORT_COMPILE_REPORT_REF: compile_report_ref,
        },
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["governance"]["links"]["legal_report_ref"]["artifact_id"] == str(
        legal_report_artifact.artifact_id
    )
    assert payload["governance"]["links"]["change_proposal_ref"]["artifact_id"] == str(
        change_proposal_artifact.artifact_id
    )
    assert payload["artifacts"]["legal_report_ref"] == str(legal_report_artifact.artifact_id)
    assert payload["artifacts"]["change_proposal_ref"] == str(
        change_proposal_artifact.artifact_id
    )
    assert payload["diagnostics_summary"]["contract_warnings"] == [
        "deprecated_mechanism_bindings",
        "model_fidelity_level_ignored",
        "missing_runtime_mechanism_support:custom_subsidy",
    ]
    assert payload["analysis_limits"]["deprecated_mechanism_bindings"] is True
    assert payload["analysis_limits"]["model_fidelity_level_ignored"] is True
    assert payload["analysis_limits"]["missing_runtime_mechanism_support"] is True


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
            refutation_results=[
                RefutationResult(
                    test_type=RefutationTestType.PLACEBO_TREATMENT,
                    original_estimate=2.5,
                    refuted_estimate=2.45,
                    p_value=0.31,
                    passed=True,
                    effect_ratio=0.98,
                    details={},
                ),
                RefutationResult(
                    test_type=RefutationTestType.RANDOM_COMMON_CAUSE,
                    original_estimate=2.5,
                    refuted_estimate=2.0,
                    p_value=0.02,
                    passed=False,
                    effect_ratio=0.8,
                    details={},
                ),
            ],
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
    assert payload["causal"]["refutation_tests_total"] == 2
    assert payload["causal"]["refutation_tests_passed"] == 1
    assert payload["causal"]["refutation_robust"] is False
    assert len(payload["causal"]["refutation_results"]) == 2
    assert payload["uncertainty_bounds"]["causal_effect_point"] == 2.5


def test_build_decision_packet_includes_abm_alignment_section(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_abm",
    )
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
    abm_ref = persist_abm_alignment_report(
        store,
        ABMAlignmentReport(
            mappings=[
                MacroMicroMapping(
                    macro_variable="income_level",
                    abm_aggregation="mean(agent.income)",
                    aggregation_function="mean",
                    agent_property="income",
                    tolerance_method="adaptive",
                )
            ],
            alignment_results={
                "income_level": AlignmentResult(
                    scm_effect=1.0,
                    abm_effect=0.98,
                    status=AlignmentStatus.CONSISTENT,
                    tolerance_used=0.1,
                    delta=0.02,
                    n_runs=5,
                )
            },
            overall_consistent=True,
            phase_transitions=[],
            warnings=["income_level: wide_tolerance_consistent_warning"],
        ),
    )

    state = ExperimentState(
        run_id="R_packet_abm",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_ABM_ALIGNMENT_REPORT_REF: abm_ref,
        },
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    manifest = store.get_manifest(packet_ref.artifact_id)
    roles = {item.role for item in manifest.inputs}

    assert payload["abm_alignment"]["report_ref"] == str(abm_ref.artifact_id)
    assert payload["abm_alignment"]["overall_consistent"] is True
    assert payload["abm_alignment"]["status_counts"] == {"consistent": 1}
    assert payload["abm_alignment"]["warnings"] == [
        "income_level: wide_tolerance_consistent_warning"
    ]
    assert payload["artifacts"]["abm_alignment_report_ref"] == str(abm_ref.artifact_id)
    assert "abm_alignment.report_ref" in roles


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


def test_build_decision_packet_includes_sensitivity_section(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_sensitivity",
    )
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
    sensitivity_ref = persist_sensitivity_result(
        store,
        SensitivityResult(
            e_value=1.8,
            e_value_ci_lower=1.3,
            conversion_method="ate_to_rr_log",
            robustness_value=0.08,
            partial_r2_treatment=0.05,
            rosenbaum_gamma=1.4,
            rosenbaum_p_value=0.07,
            is_robust=True,
            interpretation="synthetic sensitivity summary",
        ),
    )

    state = ExperimentState(
        run_id="R_packet_sensitivity",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_SENSITIVITY_RESULT_REF: sensitivity_ref},
    )
    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["sensitivity"]["ref"] == str(sensitivity_ref.artifact_id)
    assert payload["sensitivity"]["content"]["e_value"] == 1.8
    assert payload["sensitivity"]["content"]["is_robust"] is True


def test_build_decision_packet_includes_transportability_summary(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_transport",
    )
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
            method=CausalMethod.DOWHY_BACKDOOR,
            status=EstimationStatus.SUCCESS,
            estimand="ATE",
            point_estimate=1.0,
            confidence_interval=(0.8, 1.2),
            inference_method="backdoor.linear_regression",
            sample_size=120,
            n_treated=60,
            n_control=60,
            pre_periods=0,
            post_periods=0,
            transport_result=TransportabilityResult(
                status=TransportabilityStatus.TRANSPORTABLE,
                query="P*(Y|do(X))",
                final_confidence=0.73,
                feasible=True,
                resolution_rounds=2,
                unsupported_cases=["front-door outside simplified scope"],
                identification_engine="symbolic",
                identification_trace=["symbolic_success:frontdoor:M"],
            ),
        ),
    )

    state = ExperimentState(
        run_id="R_packet_transport",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_CAUSAL_REPORT_REF: report_ref},
    )
    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    summary = payload["causal"]["transportability_summary"]
    assert isinstance(summary, dict)
    assert summary["status"] == "transportable"
    assert summary["final_confidence"] == 0.73
    assert summary["resolution_rounds"] == 2
    assert summary["unsupported_cases_count"] == 1
    assert summary["identification_engine"] == "symbolic"
    assert summary["unsupported_reason"] is None


def test_build_decision_packet_includes_ensemble_summary(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_ensemble",
    )
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
    ensemble_ref = persist_causal_model_ensemble(
        store,
        CausalModelEnsemble(
            members=[
                EnsembleMember(
                    graph_ref="sha256:" + "1" * 64,
                    discovery_method="pc",
                    weight=0.6,
                    bootstrap_stability=0.7,
                ),
                EnsembleMember(
                    graph_ref="sha256:" + "2" * 64,
                    discovery_method="ges",
                    weight=0.4,
                    bootstrap_stability=0.5,
                ),
            ],
            consensus_graph_ref="sha256:" + "c" * 64,
            edge_inclusion_frequency={"X→Y": 1.0},
        ),
    )

    state = ExperimentState(
        run_id="R_packet_ensemble",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_CAUSAL_ENSEMBLE_REF: ensemble_ref},
    )
    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["artifacts"]["causal_ensemble_ref"] == str(ensemble_ref.artifact_id)
    assert payload["causal"]["ensemble_ref"] == str(ensemble_ref.artifact_id)
    assert payload["causal"]["ensemble_member_count"] == 2
    assert payload["causal"]["ensemble_methods"] == ["ges", "pc"]
    assert payload["causal"]["ensemble_consensus_graph_ref"] == "sha256:" + "c" * 64


def test_build_decision_packet_uses_dual_written_ensemble_envelope_for_causal_point(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_ensemble_env",
    )
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

    ensemble_ref = persist_causal_model_ensemble(
        store,
        CausalModelEnsemble(
            members=[
                EnsembleMember(
                    graph_ref="sha256:" + "3" * 64,
                    discovery_method="fci",
                    weight=1.0,
                    bootstrap_stability=0.8,
                )
            ],
            consensus_graph_ref="sha256:" + "4" * 64,
            edge_inclusion_frequency={"X→Y": 1.0},
        ),
    )
    ensemble_envelope_ref = persist_uncertainty_envelope(
        store,
        UncertaintyEnvelope(
            point_estimate=3.14,
            confidence_interval=(2.5, 3.8),
            confidence_level=0.95,
            distribution_family=DistributionFamily.BOOTSTRAP,
            source=UncertaintySource.ENSEMBLE,
            propagation_method=PropagationMethod.MONTE_CARLO,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        ),
    )

    state = ExperimentState(
        run_id="R_packet_ensemble_env",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_CAUSAL_ENSEMBLE_REF: ensemble_ref,
            ARTIFACT_CAUSAL_ENVELOPE_REF: ensemble_envelope_ref,
        },
    )
    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["uncertainty_bounds"]["causal_effect_point"] == 3.14
