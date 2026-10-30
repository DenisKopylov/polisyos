from __future__ import annotations

import logging

from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts import (
    input_ref_from_artifact_ref,
    profile_bound_ref,
)
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    SchemaInfo,
)
from polisyos.core.artifacts.manifest import (
    InputRef as CoreInputRef,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.compiler.report import CompileReport, put_compile_report, put_link_report
from polisyos.core.contracts.backtest import BacktestReportRef
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    Metrics,
    MetricsRef,
    SimulationResult,
    StateSnapshotRef,
)
from polisyos.core.contracts.lex import ChangeProposalRef, LegalReportRef
from polisyos.core.contracts.scientist import (
    GovernanceAccountabilityArtifactRef,
    StressTestReportRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir.analytics.abm_bridge import (
    ABMAlignmentReport,
    AlignmentResult,
    AlignmentStatus,
    MacroMicroMapping,
    persist_abm_alignment_report,
)
from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    AbstractionPreservationType,
    FiniteStateAbstractionMap,
    VariableStateAbstraction,
    persist_abstraction_certificate,
    persist_finite_state_abstraction_map,
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
from polisyos.ir.analytics.causal_queries import InterventionSpec
from polisyos.ir.analytics.hte import (
    HTEResult,
    PolicyRecommendation,
    TargetingRule,
    persist_hte_result,
    persist_policy_recommendation,
)
from polisyos.ir.analytics.metric_validation_report import (
    FamilyAdjustment,
    MetricComparisonResult,
    MetricValidationReport,
    SignificanceRecord,
    persist_metric_validation_report,
)
from polisyos.ir.analytics.normative_arbitration import (
    ArbitrationOption,
    NormativeArbitrationResult,
    NormativeModelCompleteness,
    OptionOutcomeMatrix,
    PolicyOutcome,
    ResidualDissent,
    TradeoffCertificate,
    persist_normative_arbitration_result,
)
from polisyos.ir.analytics.partial_identification import BoundsBundle, persist_bounds_bundle
from polisyos.ir.analytics.sensitivity import SensitivityResult, persist_sensitivity_result
from polisyos.ir.analytics.strategic import (
    EquilibriumSelectionSummary,
    EquilibriumSetSummary,
    FiniteStrategicPayoffTable,
    MeanFieldEquilibriumCertificate,
    MeanFieldMacroSimulationConfig,
    PerformativeLoopAnalysisScope,
    PerformativeLoopProofFamily,
    PerformativeLoopRecommendedAction,
    PerformativeLoopStabilityStatus,
    PerformativeLoopWitnessStrength,
    PerformativeShiftSummary,
    PostAdaptationPolicyValueSummary,
    StrategicClosureSummary,
    StrategicDecompositionFailureCard,
    StrategicDecompositionStatus,
    StrategicEquilibriumConcept,
    StrategicFallbackMode,
    StrategicResponseBundle,
    StrategicSCM,
    compile_intervention_spec_to_mean_field_perturbation,
    persist_equilibrium_selection_summary,
    persist_equilibrium_set_summary,
    persist_mean_field_equilibrium_certificate,
    persist_mean_field_macro_simulation_config,
    persist_mean_field_perturbation_spec,
    persist_performative_shift_summary,
    persist_post_adaptation_policy_value_summary,
    persist_strategic_closure_summary,
    persist_strategic_decomposition_failure_card,
    persist_strategic_payoff_table,
    persist_strategic_response_bundle,
    persist_strategic_scm,
)
from polisyos.ir.analytics.transportability import (
    TransportabilityResult,
    TransportabilityStatus,
    persist_transportability_result,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ConstraintSpec, ProblemFrame
from polisyos.ir.linker import LinkReport
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.registry.refs import ArtifactRefModel, UncertaintyEnvelopeRef
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.trinity.loaders import persist_trinity_bundle_artifact
from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixResult
from polisyos.scientist.governance.calibration_leaderboard import (
    CalibrationLeaderboardEntry,
    CalibrationLeaderboardMetrics,
)
from polisyos.scientist.governance.calibration_validation import (
    CalibrationValidationBundle,
    persist_calibration_validation_bundle,
)
from polisyos.scientist.governance.continuous.incident import (
    build_withdrawal_record,
    persist_withdrawal_record,
)
from polisyos.scientist.governance.continuous.monitors import (
    DecisionValidityStatus as ContinuousDecisionValidityStatus,
)
from polisyos.scientist.governance.continuous.monitors import (
    build_drift_monitor_event,
)
from polisyos.scientist.governance.continuous.reissue import (
    build_reissue_packet,
    persist_reissue_packet,
)
from polisyos.scientist.governance.continuous.reports import (
    build_validity_report,
    persist_validity_report,
)
from polisyos.scientist.governance.human_review.audit import signature_for_decision
from polisyos.scientist.governance.human_review.decisions import persist_review_decision
from polisyos.scientist.governance.human_review.models import HumanReviewDecision, ReviewAction
from polisyos.scientist.governance.human_review.packets import (
    build_review_packet,
    persist_review_packet,
)
from polisyos.scientist.governance.stress_scenarios import StressScenarioKind, StressScenarioResult
from polisyos.scientist.methods.search.readiness import (
    DecisionReadiness,
    DecisionReadinessContract,
    persist_decision_readiness_contract,
)
from polisyos.scientist.methods.search.voi_models import (
    VOIDecisionRecord,
    VOIDecisionType,
    VOIRunReport,
)
from polisyos.scientist.methods.search.voi_scheduler import persist_voi_run_report
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
    ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
    ARTIFACT_BACKTEST_REPORT_REF,
    ARTIFACT_BOUNDS_BUNDLE_REF,
    ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
    ARTIFACT_CLAIM_LEDGER_V2_REF,
    ARTIFACT_CLAIMS_REF,
    ARTIFACT_CONTINUOUS_GOVERNANCE_REPORT_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_DECISION_READINESS_CONTRACT_REF,
    ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF,
    ARTIFACT_HTE_RESULT_REF,
    ARTIFACT_HUMAN_REVIEW_DECISION_REF,
    ARTIFACT_HUMAN_REVIEW_PACKET_REF,
    ARTIFACT_METRIC_VALIDATION_REPORT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
    ARTIFACT_POLICY_RECOMMENDATION_REF,
    ARTIFACT_REISSUE_PACKET_REF,
    ARTIFACT_RESEARCH_DAG_REF,
    ARTIFACT_SENSITIVITY_RESULT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_STRATEGIC_SCM_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
    ARTIFACT_VERIFIED_POLICY_REPORT_REF,
    ARTIFACT_VOI_RUN_REPORT_REF,
    ARTIFACT_WITHDRAWAL_RECORD_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_CHANGE_PROPOSAL_REF,
    REPORT_COMPILE_REPORT_REF,
    REPORT_GOVERNANCE_REPORT_REF,
    REPORT_LEGAL_REPORT_REF,
    REPORT_LINK_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.policy_verified.models import (
    VerifiedPolicyReport,
    persist_verified_policy_report,
)


def _persist_trinity_bundle(store, payload: object | None = None):
    """Persist a valid Trinity fixture through its declared owner."""
    base = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="decision_packet_fixture_problem",
            domain="social",
            hard_constraints=[
                ConstraintSpec(
                    constraint_id="fixture_budget_cap",
                    value=1,
                    slot_id="budget",
                )
            ],
        ),
        policy_spec=PolicySpec(policy_id="decision_packet_fixture_policy"),
        model_spec=ModelSpec(
            model_id="decision_packet_fixture_model",
            data_snapshot_ref="sha256:" + "0" * 64,
        ),
    )
    if (
        isinstance(payload, dict)
        and {
            "problem_frame",
            "policy_spec",
            "model_spec",
        }
        <= payload.keys()
    ):
        bundle = TrinityBundle.model_validate(payload)
    elif isinstance(payload, dict) and "policy_spec" in payload:
        policy_payload = {
            **base.policy_spec.model_dump(mode="python"),
            **payload["policy_spec"],
        }
        bundle = base.model_copy(update={"policy_spec": PolicySpec.model_validate(policy_payload)})
    else:
        bundle = base
    return persist_trinity_bundle_artifact(_ensure_ir_artifact_store(store), bundle)


def _persist_state_snapshot(store: FileSystemCAS) -> StateSnapshotRef:
    """Persist a real selected Foundry state snapshot for source-bound fixtures."""
    snapshot_ref = put_state_snapshot(
        store,
        state=GlobalState.empty(n_agents=2, n_firms=1),
        step=0,
        return_selected_profile=True,
    )
    assert snapshot_ref.manifest_profile_sha256 is not None
    assert store.get_manifest(snapshot_ref).artifact_schema == SchemaInfo(
        name="polisyos.core.StateSnapshot",
        version="2.2.0",
    )
    return snapshot_ref


def _persist_data_snapshot(
    store: FileSystemCAS,
    *,
    data_ref: ArtifactRef | None = None,
    quality_report_ref: ArtifactRef | None = None,
) -> DataSnapshotRef:
    """Persist a selected DataSnapshot with a profile-bound source edge."""
    source_ref = (
        _persist_state_snapshot(store) if data_ref is None else profile_bound_ref(store, data_ref)
    )
    selected_quality_ref = (
        None if quality_report_ref is None else profile_bound_ref(store, quality_report_ref)
    )
    inputs = [input_ref_from_artifact_ref(source_ref, role="data_ref")]
    if selected_quality_ref is not None:
        inputs.append(input_ref_from_artifact_ref(selected_quality_ref, role="quality_report_ref"))
    ref = store.put_json(
        DataSnapshot(data_ref=source_ref, quality_report_ref=selected_quality_ref),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    snapshot_ref = DataSnapshotRef.model_validate(ref.model_dump(mode="python"))
    assert snapshot_ref.manifest_profile_sha256 is not None
    assert store.get_manifest(snapshot_ref).artifact_schema == SchemaInfo(
        name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
        version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
    )
    return snapshot_ref


def _artifact_id(ch: str) -> str:
    return f"sha256:{ch * 64}"


def _execute_current_governance_and_packet(ctx, state):
    """Run the real selected governance producer into the packet consumer."""
    from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.workflows.policy_design import (
        policy_design_workflow_spec,
    )

    registry = NodeRegistry()
    registry.register(RunGovernanceNode())
    registry.register(BuildDecisionPacketNode())
    selected = policy_design_workflow_spec()
    invocations = {item.alias: item for item in selected.nodes}
    workflow = selected.model_copy(
        update={
            "nodes": [
                invocations["run_governance"].model_copy(update={"depends_on": []}),
                invocations["build_decision_packet"].model_copy(
                    update={"depends_on": ["run_governance"]}
                ),
            ],
            "required_binds": ["run_id"],
        }
    )
    return WorkflowExecutor(ctx, registry).execute(workflow, state)


def _packet_record(workflow_result):
    return next(
        record for record in workflow_result.report.nodes if record.alias == "build_decision_packet"
    )


def test_build_decision_packet_node_emits_v3_payload_and_manifest_inputs(
    tmp_path, monkeypatch
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_v3")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = _persist_trinity_bundle(store)
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)
    metrics_ref = store.put_json(
        Metrics(values={"applied_nodes": 1, "status": "ok"}),
        PutOptions(
            kind=Metrics.ARTIFACT_KIND,
            media_type=Metrics.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=Metrics.ARTIFACT_SCHEMA_NAME,
                version=Metrics.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    research_dag_ref = store.put_json(
        {
            "schema_version": "1.0",
            "run_id": "R_packet_v3",
            "workflow_id": "scientist_policy_design",
            "nodes": [],
            "edges": [],
        },
        PutOptions(kind="scientist.research_dag", media_type="application/json"),
    )
    voi_report_ref = persist_voi_run_report(
        store,
        VOIRunReport(
            run_id="R_packet_v3",
            decisions=[
                VOIDecisionRecord(
                    decision_id="voi_decision_stop",
                    run_id="R_packet_v3",
                    decision_type=VOIDecisionType.STOP_SEARCH,
                    recommended_action="stop_search",
                    expected_value=0.0,
                    expected_cost=0.0,
                    expected_risk_reduction=0.0,
                    explanation="Stop search because marginal VOI is below cost.",
                )
            ],
            total_expected_cost=0.0,
            calibration_status="shadow",
        ),
    )
    prior_packet_ref = ArtifactRef(
        artifact_id=_artifact_id("9"),
        kind="scientist.decision_packet",
        media_type="application/json",
    )
    original_claim_ledger_ref = ArtifactRef(
        artifact_id=_artifact_id("8"),
        kind="scientist.claim_ledger_v2",
        media_type="application/json",
    )
    new_packet_ref = ArtifactRef(
        artifact_id=_artifact_id("7"),
        kind="scientist.decision_packet",
        media_type="application/json",
    )
    new_claim_ledger_ref = ArtifactRef(
        artifact_id=_artifact_id("6"),
        kind="scientist.claim_ledger_v2",
        media_type="application/json",
    )
    monitor_event_ref = ArtifactRef(
        artifact_id=_artifact_id("5"),
        kind="scientist.governance_monitor_event",
        media_type="application/json",
    )
    audit_event_ref = ArtifactRef(
        artifact_id=_artifact_id("4"),
        kind="scientist.audit_event",
        media_type="application/json",
    )
    reissue_packet_ref = persist_reissue_packet(
        store,
        build_reissue_packet(
            original_decision_packet_ref=prior_packet_ref,
            original_claim_ledger_ref=original_claim_ledger_ref,
            new_decision_packet_ref=new_packet_ref,
            new_claim_ledger_ref=new_claim_ledger_ref,
            status=ContinuousDecisionValidityStatus.REISSUED,
            monitor_event_refs=[monitor_event_ref],
            reason="Reissued after continuous governance drift review.",
        ),
    )
    withdrawal_record_ref = persist_withdrawal_record(
        store,
        build_withdrawal_record(
            withdrawal_id="withdrawal_packet_fixture",
            decision_packet_ref=prior_packet_ref,
            actor_id="reviewer_1",
            reason="Auditable withdrawal record fixture.",
            audit_event_ref=audit_event_ref,
            monitor_event_refs=[monitor_event_ref],
        ),
    )
    governance_event = build_drift_monitor_event(
        decision_packet_ref=prior_packet_ref,
        event_type="fairness_drift",
        severity="warning",
        reason="Fairness drift requires reviewer triage.",
        affected_claim_ids=["claim_1"],
    )
    continuous_governance_report_ref = persist_validity_report(
        store,
        build_validity_report(
            decision_packet_ref=prior_packet_ref,
            monitor_events=[governance_event],
            reissue_packet_ref=reissue_packet_ref,
            withdrawal_ref=withdrawal_record_ref,
        ),
    )

    state = ExperimentState(
        run_id="R_packet_v3",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_METRICS_REF: metrics_ref,
            ARTIFACT_RESEARCH_DAG_REF: research_dag_ref,
            ARTIFACT_VOI_RUN_REPORT_REF: voi_report_ref,
            ARTIFACT_CONTINUOUS_GOVERNANCE_REPORT_REF: continuous_governance_report_ref,
            ARTIFACT_REISSUE_PACKET_REF: reissue_packet_ref,
            ARTIFACT_WITHDRAWAL_RECORD_REF: withdrawal_record_ref,
        },
        params={
            "random_seed": 123,
            "scientist.best_in_class.wave2.phase2_1.claim_ledger_v2": True,
        },
    )

    workflow_result = _execute_current_governance_and_packet(ctx, state)
    packet_record = _packet_record(workflow_result)
    assert packet_record.status == "ok"
    packet_ref = workflow_result.state.artifacts_index["decision_packet_ref"]
    governance_ref = workflow_result.state.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    manifest = store.get_manifest(packet_ref.artifact_id)
    roles = {item.role for item in manifest.inputs}

    assert payload["schema_version"] == "3.4"
    assert payload["seed"] == 123
    assert payload["policy_summary"] == "Policy with 0 intervention(s)"
    assert payload["replay"]["strategy_hint"] == "scientist"
    assert payload["replay"]["why_partial"] == ["missing_optional_inputs"]
    assert "input_bindings_ref" in payload["replay"]["missing_refs"]
    assert payload["uncertainty"]["envelope_count"] == 0
    assert payload["diagnostics_summary"]["replay_readiness"] == "partial"
    assert payload["diagnostics_summary"]["transport_status"] == "not_run"
    assert payload["analysis_limits"]["partial_replay_readiness"] is True
    assert payload["analysis_limits"]["missing_uncertainty_artifact"] is True
    assert "claims_ref" not in payload
    assert payload["artifacts"][ARTIFACT_CLAIMS_REF] is None
    assert payload["claim_ledger_status"] == "not_established"
    assert payload["claim_ledger_limitation_code"] == ("claim_ledger_owner_not_established")
    assert "claim_ledger_v2_ref" not in payload
    assert ARTIFACT_CLAIM_LEDGER_V2_REF not in payload["artifacts"]
    assert "blocked_claim_summary" not in payload
    assert payload["research_dag_ref"] == payload["artifacts"][ARTIFACT_RESEARCH_DAG_REF]
    assert payload["research_dag_status"] == "available"
    assert payload["voi_report_ref"] == payload["artifacts"][ARTIFACT_VOI_RUN_REPORT_REF]
    assert payload["voi_report_status"] == "available"
    assert payload["voi"]["status"] == "available"
    assert payload["voi"]["decision_count"] == 1
    assert payload["voi"]["decision_type_counts"]["stop_search"] == 1
    assert (
        payload["continuous_governance_report_ref"]
        == payload["artifacts"][ARTIFACT_CONTINUOUS_GOVERNANCE_REPORT_REF]
    )
    assert payload["reissue_packet_ref"] == payload["artifacts"][ARTIFACT_REISSUE_PACKET_REF]
    assert payload["withdrawal_record_ref"] == payload["artifacts"][ARTIFACT_WITHDRAWAL_RECORD_REF]
    assert payload["continuous_governance"]["status"] == "review_required"
    assert payload["continuous_governance"]["event_count"] == 1
    assert payload["continuous_governance"]["recommendation_count"] == 1
    assert payload["continuous_governance"]["affected_claim_ids"] == ["claim_1"]
    assert payload["continuous_governance"]["recommended_actions"] == ["human_review"]
    assert payload["continuous_governance"]["has_reissue_packet"] is True
    assert payload["continuous_governance"]["has_withdrawal_record"] is True
    assert ARTIFACT_CLAIMS_REF not in workflow_result.state.artifacts_index
    assert payload["feedback_loop"]["anchor_at"] is not None
    assert payload["feedback_loop"]["monitoring_contract_ref"] is not None
    assert payload["feedback_loop"]["latest_monitoring_report_ref"] is None
    assert payload["inputs"]["trinity_bundle_ref"] == str(trinity_ref.artifact_id)
    assert payload["artifacts"]["metrics_ref"] == str(metrics_ref.artifact_id)
    assert payload["artifacts"][ARTIFACT_VOI_RUN_REPORT_REF] == str(voi_report_ref.artifact_id)
    assert payload["artifacts"][ARTIFACT_CONTINUOUS_GOVERNANCE_REPORT_REF] == str(
        continuous_governance_report_ref.artifact_id
    )
    assert payload["artifacts"]["governance_report_ref"] == str(governance_ref.artifact_id)
    assert "input.trinity_bundle_ref" in roles
    assert "input.registry_bundle_ref" in roles
    assert "input.data_snapshot_ref" in roles
    assert "artifact.metrics_ref" in roles
    assert "artifact.governance_report_ref" in roles
    assert "claims" not in roles
    assert "voi.voi_run_report_ref" in roles
    assert "continuous_governance.continuous_governance_report_ref" in roles
    from dataclasses import replace

    from polisyos.scientist.governance.report_currentness import (
        GOVERNANCE_REPORT_SOURCE_BASIS_ID,
        resolve_current_governance_report,
    )
    from polisyos.scientist.orchestration.engine.context import (
        _EngineInvocationBinding,
        _load_engine_owned_invocation_input_state,
    )

    attempts = run.read_runtime_invocation_attempts()
    packet_attempt = next(
        item for item in attempts if item.basis.node_alias == "build_decision_packet"
    )
    packet_input_ctx = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id=packet_attempt.basis.run_id,
            attempt_id=packet_attempt.basis.attempt_id,
            basis_ref=packet_attempt.basis_ref,
            require_successful_completion=True,
        ),
    )
    packet_input_state = _load_engine_owned_invocation_input_state(
        packet_input_ctx,
        workflow_result.state,
    )
    assert packet_input_state is not None
    assert "decision_packet_ref" not in packet_input_state.artifacts_index

    admission = resolve_current_governance_report(ctx, packet_input_state, governance_ref)
    assert admission.is_current, admission.reason_code
    assert admission.reason_code == "governance_report_source_current"
    assert admission.report is not None
    binding = admission.report.invocation_binding
    assert binding is not None
    governance_attempt = next(
        item for item in attempts if item.basis.node_alias == "run_governance"
    )
    assert governance_attempt.outcome is not None
    assert governance_attempt.outcome.status == "ok"
    assert binding.run_id == packet_input_state.run_id
    assert binding.node_alias == "run_governance"
    assert binding.component_id == governance_attempt.basis.component_id
    assert binding.attempt_basis_ref == governance_attempt.basis_ref
    assert binding.workflow_spec_ref == governance_attempt.basis.workflow_spec_ref
    assert binding.input_state_ref == governance_attempt.basis.input_state_ref
    assert binding.source_basis_id == GOVERNANCE_REPORT_SOURCE_BASIS_ID
    assert all(
        ref.manifest_profile_sha256 is not None
        for ref in (
            binding.attempt_basis_ref,
            binding.workflow_spec_ref,
            binding.input_state_ref,
        )
    )
    assert any(
        output_ref.artifact_id == governance_ref.artifact_id
        and output_ref.manifest_profile_sha256 == governance_ref.manifest_profile_sha256
        for output_ref in governance_attempt.outcome.output_refs
    )
    assert payload["governance"]["currentness"] == "current"

    # Keep the selected report and producer markers intact, but falsify the
    # source-projected params map. Both the resolver and packet consumer must refuse.
    changed_state = packet_input_state.model_copy(deep=True)
    changed_state.params["random_seed"] = 124
    changed_selector = changed_state.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    assert changed_selector.artifact_id == governance_ref.artifact_id
    assert changed_selector.manifest_profile_sha256 == governance_ref.manifest_profile_sha256
    changed_admission = resolve_current_governance_report(ctx, changed_state, governance_ref)
    assert changed_admission.status == "stale"
    assert changed_admission.reason_code == "producer_source_projection_changed"

    packet_put_kinds: list[str] = []
    original_put_json = ctx.store.put_json

    def track_packet_put(obj, options, *args, **kwargs):
        if options.kind == "scientist.decision_packet":
            packet_put_kinds.append(options.kind)
        return original_put_json(obj, options, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(ctx.store, "put_json", track_packet_put)
        stale_packet = BuildDecisionPacketNode().execute(ctx, changed_state)
    assert stale_packet.status == "fail"
    assert stale_packet.error is not None
    assert stale_packet.error.code == "governance_report_not_established"
    assert (
        stale_packet.error.details["governance_report_refusal_code"]
        == "producer_source_projection_changed"
    )
    assert packet_put_kinds == []


def test_build_decision_packet_blocks_naked_recommendation_when_claim_gate_enabled(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_naked_claim_gate",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.packet.naked_claim_gate"),
    )

    trinity_ref = _persist_trinity_bundle(store)
    data_snapshot_ref = _persist_data_snapshot(store)
    verified_policy_ref = persist_verified_policy_report(
        store,
        VerifiedPolicyReport(
            request_id="request_naked_claim_gate",
            executive_summary="Adopt the candidate policy.",
        ),
    )

    state = ExperimentState(
        run_id="R_packet_naked_claim_gate",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_VERIFIED_POLICY_REPORT_REF: verified_policy_ref},
        params={
            "workflow_id": "scientist_policy_design",
            "scientist.best_in_class.wave1.phase1_1.claim_spine": False,
            "scientist.best_in_class.wave1.phase1_1.fail_on_naked_claims": True,
        },
    )

    workflow_result = _execute_current_governance_and_packet(ctx, state)
    packet_record = _packet_record(workflow_result)

    assert packet_record.status == "fail"
    assert packet_record.error is not None
    assert packet_record.error.code == "claim_spine_validation_failed"
    assert packet_record.error.details["claim_ledger_status"] == "legacy_missing"
    assert packet_record.error.details["violations"] == [
        "missing_claims_ref_for_decision_bearing_payload"
    ]


def test_build_decision_packet_includes_metric_validation_projection(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_metric_validation",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.packet.metric_validation"),
    )

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)
    metrics_ref = store.put_json(
        Metrics(values={"accuracy": 0.76}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    metric_validation_ref = persist_metric_validation_report(
        _ensure_ir_artifact_store(store),
        MetricValidationReport(
            report_id="mvr_packet",
            dataset_id="holdout_v1",
            task="binary",
            checked_at="2026-04-21T12:00:00Z",
            family_adjustment=FamilyAdjustment(
                method="holm",
                alpha=0.05,
                hypotheses_total=1,
                error_rate_target="FWER",
                dependency_assumption="arbitrary",
            ),
            comparisons=(
                MetricComparisonResult(
                    metric_id="accuracy",
                    metric_direction="higher_is_better",
                    baseline_model_id="baseline",
                    candidate_model_id="candidate",
                    baseline_value=0.71,
                    candidate_value=0.76,
                    delta_value=0.05,
                    significance=SignificanceRecord(
                        test_id="mcnemar_exact",
                        null_hypothesis="Accuracy(candidate) - Accuracy(baseline) = 0",
                        alternative="greater",
                        p_value_raw=0.02,
                        p_value_adj=0.02,
                        alpha=0.05,
                        reject_null_raw=True,
                        reject_null_adj=True,
                    ),
                    family_id="holdout_v1:baseline_vs_candidate",
                    family_scope="per_candidate",
                ),
            ),
        ),
    )

    state = ExperimentState(
        run_id="R_packet_metric_validation",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_METRICS_REF: metrics_ref,
            ARTIFACT_METRIC_VALIDATION_REPORT_REF: metric_validation_ref,
        },
        params={"random_seed": 123},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    payload = from_canonical_bytes(store.get_bytes(outcome.artifacts[0].artifact_id))

    assert payload["metric_validation_report_ref"] == str(metric_validation_ref.artifact_id)
    assert payload["artifacts"]["metric_validation_report_ref"] == str(
        metric_validation_ref.artifact_id
    )
    assert payload["metric_significance"]["accuracy"]["test_label"] == "McNemar exact"
    assert payload["metric_significance"]["accuracy"]["significant"] is True
    assert payload["metric_validation_family_adjustment"] == {
        "alpha": 0.05,
        "dependency_assumption": "arbitrary",
        "error_rate_target": "FWER",
        "hypotheses_total": 1,
        "method": "holm",
    }
    assert payload["metric_validation_comparisons"] == [
        {
            "alpha": 0.05,
            "assumption_warnings": [],
            "baseline_model_id": "baseline",
            "baseline_value": 0.71,
            "calibration_warnings": [],
            "candidate_model_id": "candidate",
            "candidate_value": 0.76,
            "ci_high": None,
            "ci_level": None,
            "ci_low": None,
            "delta_value": 0.05,
            "effect_size": None,
            "family_id": "holdout_v1:baseline_vs_candidate",
            "family_scope": "per_candidate",
            "metric_direction": "higher_is_better",
            "metric_id": "accuracy",
            "p_adj": 0.02,
            "p_value": 0.02,
            "resampling_method": None,
            "sample_size_effective": None,
            "significant": True,
            "statistic": None,
            "test_id": "mcnemar_exact",
            "test_label": "McNemar exact",
        }
    ]
    assert payload["metric_significance_summary"]["comparison_count"] == 1
    assert payload["metric_significance_summary"]["significant_improvements"] == [
        {
            "baseline_model_id": "baseline",
            "candidate_model_id": "candidate",
            "metric_id": "accuracy",
            "delta_value": 0.05,
            "p_value": 0.02,
            "p_adj": 0.02,
            "test_label": "McNemar exact",
        }
    ]


def test_build_decision_packet_records_degraded_paths_for_invalid_metrics(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_degraded")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.degraded"))

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    data_snapshot_ref = store.put_json(
        {"data_ref": None},
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        ["invalid"],
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    state = ExperimentState(
        run_id="R_packet_degraded",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_METRICS_REF: metrics_ref},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    payload = from_canonical_bytes(store.get_bytes(outcome.artifacts[0].artifact_id))
    degraded_reasons = {item["reason"] for item in payload["degraded_paths"]}

    assert payload["simulation_results"] is None
    assert payload["governance"] is None
    assert degraded_reasons == {
        "decision_basis_data_snapshot_validate_failed",
        "metrics_load_failed",
        "uncertainty_data_snapshot_load_failed",
    }
    assert payload["diagnostics_summary"]["degraded_path_count"] == 2
    assert payload["diagnostics_summary"]["has_degraded_paths"] is True
    assert payload["analysis_limits"]["decision_packet_degraded"] is True
    assert any(note.startswith("metrics_load_failed:") for note in payload["notes"])


def test_build_decision_packet_records_degraded_paths_for_invalid_decision_basis_quality_report(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_invalid_quality_basis",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.packet.invalid_quality_basis"),
    )

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    invalid_quality_ref = store.put_json(
        ["invalid"],
        PutOptions(kind="fabric.quality_report", media_type="application/json"),
    )
    data_snapshot_ref = _persist_data_snapshot(
        store, data_ref=state_snapshot_ref, quality_report_ref=invalid_quality_ref
    )

    state = ExperimentState(
        run_id="R_packet_invalid_quality_basis",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    payload = from_canonical_bytes(store.get_bytes(outcome.artifacts[0].artifact_id))
    degraded_reasons = {item["reason"] for item in payload["degraded_paths"]}

    assert "decision_basis_quality_report_load_failed" in degraded_reasons
    assert any(
        note.startswith("decision_basis_quality_report_load_failed:") for note in payload["notes"]
    )
    assert payload["decision_validity_envelope"]["data_basis"]["summary"][
        "quality_report_ref"
    ] == str(invalid_quality_ref.artifact_id)


def test_build_decision_packet_surfaces_legal_links_and_contract_warnings(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_diag")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = _persist_trinity_bundle(store, {"policy_spec": {"interventions": []}})
    data_snapshot_ref = _persist_data_snapshot(store)
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
    link_report_ref = put_link_report(
        store,
        LinkReport(
            ok=True,
            issues=[],
        ),
    )
    compile_report_ref = put_compile_report(
        store,
        CompileReport(
            ok=False,
            link_report_ref=link_report_ref,
            notes=[
                "missing_runtime_mechanism_support:custom_subsidy",
            ],
        ),
    )
    review_packet = build_review_packet(
        run_id="R_packet_diag",
        decision_payload={"policy_summary": {"title": "diagnostics fixture"}},
    )
    review_packet_ref = persist_review_packet(store, review_packet)
    review_decision_ref = persist_review_decision(
        store,
        HumanReviewDecision(
            decision_id="decision_packet_diag",
            packet_id=review_packet.packet_id,
            run_id="R_packet_diag",
            reviewer_id="reviewer_diag",
            action=ReviewAction.APPROVE,
            rationale="Reviewed legal diagnostic packet.",
            signature=signature_for_decision(
                reviewer_id="reviewer_diag",
                attestation="I reviewed the packet.",
            ),
            packet_ref=review_packet_ref,
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
            REPORT_LEGAL_REPORT_REF: legal_report_ref,
            REPORT_CHANGE_PROPOSAL_REF: change_proposal_ref,
            REPORT_LINK_REPORT_REF: link_report_ref,
            REPORT_COMPILE_REPORT_REF: compile_report_ref,
        },
        artifacts_index={
            ARTIFACT_HUMAN_REVIEW_PACKET_REF: review_packet_ref,
            ARTIFACT_HUMAN_REVIEW_DECISION_REF: review_decision_ref,
        },
    )

    workflow_result = _execute_current_governance_and_packet(ctx, state)
    packet_record = _packet_record(workflow_result)
    assert packet_record.status == "ok"
    packet_ref = workflow_result.state.artifacts_index["decision_packet_ref"]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["governance"]["links"]["legal_report_ref"]["artifact_id"] == str(
        legal_report_artifact.artifact_id
    )
    assert payload["governance"]["links"]["change_proposal_ref"]["artifact_id"] == str(
        change_proposal_artifact.artifact_id
    )
    assert payload["artifacts"]["legal_report_ref"] == str(legal_report_artifact.artifact_id)
    assert payload["artifacts"]["change_proposal_ref"] == str(change_proposal_artifact.artifact_id)
    assert payload["diagnostics_summary"]["contract_warnings"] == [
        "missing_runtime_mechanism_support:custom_subsidy",
    ]
    assert payload["analysis_limits"]["missing_runtime_mechanism_support"] is True


def test_build_decision_packet_includes_tradeoff_certificate_and_normative_validity(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(
        store=store, registry_bundle=registry_bundle, run_id="R_packet_normative"
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.normative"))

    trinity_ref = _persist_trinity_bundle(
        store,
        TrinityBundle.model_validate(
            {
                "schema_version": "1.0",
                "problem_frame": {
                    "schema_version": "1.0",
                    "problem_id": "normative_problem",
                    "domain": "social",
                    "normative_frame": {
                        "comparison_mode": "proposal_vs_baseline",
                        "default_policy": "weighted_welfare",
                        "enabled_policies": ["weighted_welfare"],
                        "stakeholder_bindings": [],
                        "utility_terms": [],
                        "rights_catalog": [],
                        "hard_constraint_refs": [],
                    },
                },
                "policy_spec": {
                    "schema_version": "1.0",
                    "policy_id": "policy",
                    "interventions": [],
                },
                "model_spec": {
                    "schema_version": "1.0",
                    "model_id": "model",
                    "data_snapshot_ref": "sha256:" + "0" * 64,
                    "fidelity_level": "hybrid",
                },
            }
        ),
    )
    data_snapshot_ref = _persist_data_snapshot(store)
    normative_ref = persist_normative_arbitration_result(
        _ensure_ir_artifact_store(store),
        NormativeArbitrationResult(
            model_completeness=NormativeModelCompleteness.PARTIAL,
            option_matrix=[
                OptionOutcomeMatrix(
                    option=ArbitrationOption.BASELINE,
                    binding_values={"workers": 0.0},
                ),
                OptionOutcomeMatrix(
                    option=ArbitrationOption.PROPOSAL,
                    binding_values={"workers": 1.0},
                ),
            ],
            per_stakeholder_utility=[],
            rights_audit=[],
            hard_constraint_audit=[],
            policy_outcomes=[
                PolicyOutcome(
                    policy="weighted_welfare",
                    selected_option=ArbitrationOption.PROPOSAL,
                    rationale="aggregate welfare positive",
                )
            ],
            selected_policy="weighted_welfare",
            selected_option=ArbitrationOption.PROPOSAL,
            residual_dissent=[
                ResidualDissent(
                    policy="pareto_filter",
                    preferred_option=ArbitrationOption.INDETERMINATE,
                    rationale="neutral proposal",
                )
            ],
            tradeoff_certificate=TradeoffCertificate(
                selected_policy="weighted_welfare",
                selected_option=ArbitrationOption.PROPOSAL,
                winners=["workers"],
                losers=[],
                residual_dissent=[
                    ResidualDissent(
                        policy="pareto_filter",
                        preferred_option=ArbitrationOption.INDETERMINATE,
                        rationale="neutral proposal",
                    )
                ],
                notes=["partial_model"],
            ),
            metadata={"model_source": "declared"},
        ),
    )

    state = ExperimentState(
        run_id="R_packet_normative",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF: normative_ref},
    )

    workflow_result = _execute_current_governance_and_packet(ctx, state)
    packet_record = _packet_record(workflow_result)
    assert packet_record.status == "ok"
    packet_ref = workflow_result.state.artifacts_index["decision_packet_ref"]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["artifacts"]["normative_arbitration_result_ref"] == str(
        normative_ref.artifact_id
    )
    assert payload["tradeoff_certificate"]["selected_policy"] == "weighted_welfare"
    assert payload["diagnostics_summary"]["normative_model_completeness"] == "partial"
    assert payload["diagnostics_summary"]["normative_residual_dissent_count"] == 1
    assert (
        payload["decision_validity_envelope"]["normative_basis"]["summary"][
            "normative_selected_policy"
        ]
        == "weighted_welfare"
    )
    assert payload["decision_validity_baseline"]["status"] == "warning"


def test_build_decision_packet_rejects_incomplete_serious_contract(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(
        store=store, registry_bundle=registry_bundle, run_id="R_packet_serious_fail"
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.serious"))

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    data_snapshot_ref = _persist_data_snapshot(store)

    state = ExperimentState(
        run_id="R_packet_serious_fail",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        execution_profile="governed",
    )

    workflow_result = _execute_current_governance_and_packet(ctx, state)
    packet_record = _packet_record(workflow_result)

    assert packet_record.status == "fail"
    assert packet_record.error is not None
    assert packet_record.error.code == "node.invalid_state"
    assert packet_record.error.details["missing_contracts"] == [
        "capability_manifest_ref",
        ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
        ARTIFACT_TRANSPORTABILITY_RESULT_REF,
        ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
        "monitoring_contract_ref",
    ]


def test_build_decision_packet_records_degraded_paths_for_invalid_normative_arbitration(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_invalid_normative",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.packet.invalid_normative"),
    )

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    data_snapshot_ref = _persist_data_snapshot(store)
    invalid_normative_ref = store.put_json(
        {"schema_version": "1.0"},
        PutOptions(
            kind="ir.normative_arbitration_result",
            media_type="application/json",
            schema=SchemaInfo(name="ir.normative_arbitration_result", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )

    state = ExperimentState(
        run_id="R_packet_invalid_normative",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF: invalid_normative_ref},
    )

    workflow_result = _execute_current_governance_and_packet(ctx, state)
    packet_record = _packet_record(workflow_result)
    assert packet_record.status == "ok"
    packet_ref = workflow_result.state.artifacts_index["decision_packet_ref"]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    degraded_reasons = {item["reason"] for item in payload["degraded_paths"]}

    assert payload["tradeoff_certificate"] is None
    assert "normative_arbitration_load_failed" in degraded_reasons
    assert payload["diagnostics_summary"]["degraded_path_count"] >= 1
    assert any(note.startswith("normative_arbitration_load_failed:") for note in payload["notes"])


def test_build_decision_packet_accepts_complete_serious_contract(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(
        store=store, registry_bundle=registry_bundle, run_id="R_packet_serious_ok"
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.serious.ok"))

    trinity_ref = _persist_trinity_bundle(
        store,
        TrinityBundle.model_validate(
            {
                "schema_version": "1.0",
                "problem_frame": {
                    "schema_version": "1.0",
                    "problem_id": "serious_problem",
                    "domain": "social",
                    "normative_frame": {
                        "comparison_mode": "proposal_vs_baseline",
                        "default_policy": "weighted_welfare",
                        "enabled_policies": ["weighted_welfare"],
                        "stakeholder_bindings": [],
                        "utility_terms": [],
                        "rights_catalog": [],
                        "hard_constraint_refs": [],
                    },
                },
                "policy_spec": {
                    "schema_version": "1.0",
                    "policy_id": "policy",
                    "interventions": [],
                },
                "model_spec": {
                    "schema_version": "1.0",
                    "model_id": "model",
                    "data_snapshot_ref": "sha256:" + "0" * 64,
                    "fidelity_level": "hybrid",
                },
            }
        ),
    )
    data_snapshot_ref = _persist_data_snapshot(store)
    metrics_ref = store.put_json(
        Metrics(values={"policy_cost": 100.0, "applied_nodes": 1}),
        PutOptions(
            kind=Metrics.ARTIFACT_KIND,
            media_type=Metrics.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=Metrics.ARTIFACT_SCHEMA_NAME,
                version=Metrics.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    normative_ref = persist_normative_arbitration_result(
        _ensure_ir_artifact_store(store),
        NormativeArbitrationResult(
            model_completeness=NormativeModelCompleteness.PARTIAL,
            option_matrix=[
                OptionOutcomeMatrix(
                    option=ArbitrationOption.BASELINE,
                    binding_values={"workers": 0.0},
                ),
                OptionOutcomeMatrix(
                    option=ArbitrationOption.PROPOSAL,
                    binding_values={"workers": 1.0},
                ),
            ],
            per_stakeholder_utility=[],
            rights_audit=[],
            hard_constraint_audit=[],
            policy_outcomes=[
                PolicyOutcome(
                    policy="weighted_welfare",
                    selected_option=ArbitrationOption.PROPOSAL,
                    rationale="aggregate welfare positive",
                )
            ],
            selected_policy="weighted_welfare",
            selected_option=ArbitrationOption.PROPOSAL,
            residual_dissent=[],
            tradeoff_certificate=TradeoffCertificate(
                selected_policy="weighted_welfare",
                selected_option=ArbitrationOption.PROPOSAL,
                winners=["workers"],
                losers=[],
                residual_dissent=[],
                notes=[],
            ),
            metadata={"model_source": "declared"},
        ),
    )
    transport_ref = persist_transportability_result(
        _ensure_ir_artifact_store(store),
        TransportabilityResult(
            query="P*(Y|do(X))",
            status=TransportabilityStatus.IDENTIFIED,
            final_confidence=0.9,
            source_context_id="DE",
            target_context_id="UA",
        ),
    )
    cross_graph_ref = store.put_json(
        {
            "schema_version": "2.0",
            "summary": {"status": "ok", "total_needs": 1},
            "needs": [],
            "diagnostics": [],
            "ontology_snapshot": [],
            "bridges": [],
            "source_refs": {},
            "notes": [],
        },
        PutOptions(kind="ir.cross_graph_evidence_profile", media_type="application/json"),
    )
    capability_manifest_ref = store.put_json(
        {
            "schema_version": "1.0",
            "job_id": "job-serious",
            "execution_profile": "governed",
        },
        PutOptions(kind="runtime.capability_manifest", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_packet_serious_ok",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_METRICS_REF: metrics_ref,
            ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF: normative_ref,
            ARTIFACT_TRANSPORTABILITY_RESULT_REF: transport_ref,
            ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF: cross_graph_ref,
        },
        execution_profile="governed",
        capability_manifest_ref=capability_manifest_ref,
    )

    workflow_result = _execute_current_governance_and_packet(ctx, state)
    packet_record = _packet_record(workflow_result)
    assert packet_record.status == "ok"
    packet_ref = workflow_result.state.artifacts_index["decision_packet_ref"]

    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    assert payload["runtime_contracts"]["execution_profile"] == "governed"
    assert payload["runtime_contracts"]["capability_manifest_ref"] == str(
        capability_manifest_ref.artifact_id
    )
    assert payload["artifacts"]["cross_graph_evidence_profile_ref"] == str(
        cross_graph_ref.artifact_id
    )
    assert payload["artifacts"]["transportability_result_ref"] == str(transport_ref.artifact_id)
    assert payload["feedback_loop"]["monitoring_contract_ref"] is not None


def test_build_decision_packet_node_accepts_float_uncertainty_bounds(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_unc")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)
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
        _ensure_ir_artifact_store(store),
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
    simulation_payload = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
        metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        uncertainty_envelopes={"step_latency_ms": env_ref},
    )
    default_sim_result_ref = store.put_json(
        simulation_payload,
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    sim_result_ref = store.put_json(
        simulation_payload,
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            inputs=[
                CoreInputRef(
                    artifact_id="sha256:" + "d" * 64,
                    role="selected_view_witness",
                )
            ],
        ),
    )
    assert sim_result_ref.artifact_id == default_sim_result_ref.artifact_id
    assert sim_result_ref.manifest_profile_sha256 is not None

    observed_simulation_reads: list[object] = []
    get_bytes = store.get_bytes

    def record_simulation_read(selector: object) -> bytes:
        selector_id = getattr(selector, "artifact_id", selector)
        if str(selector_id) == str(sim_result_ref.artifact_id):
            observed_simulation_reads.append(selector)
        return get_bytes(selector)

    monkeypatch.setattr(store, "get_bytes", record_simulation_read)

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

    assert bounds is None
    assert payload["uncertainty"]["simulation_result_ref"] == str(sim_result_ref.artifact_id)
    assert payload["uncertainty"]["simulation_result_selector_ref"] == {
        "artifact_id": str(sim_result_ref.artifact_id),
        "kind": sim_result_ref.kind,
        "media_type": sim_result_ref.media_type,
        "manifest_profile_sha256": sim_result_ref.manifest_profile_sha256,
    }
    assert observed_simulation_reads
    assert all(
        getattr(selector, "manifest_profile_sha256", None) == sim_result_ref.manifest_profile_sha256
        for selector in observed_simulation_reads
    )
    uncertainty_warnings = payload["uncertainty"]["warnings"]
    assert any(
        warning.startswith("uncertainty_output_admission_limited:step_latency_ms:")
        for warning in uncertainty_warnings
    )
    degraded_reasons = {item["reason"] for item in payload["degraded_paths"]}
    assert "uncertainty_output_admission_limited" in degraded_reasons


def test_build_decision_packet_records_degraded_paths_for_invalid_uncertainty_output_envelope(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_invalid_uncertainty_output",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.packet.invalid_uncertainty_output"),
    )

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)
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
    invalid_envelope_ref = store.put_json(
        ["invalid"],
        PutOptions(kind="ir.uncertainty_envelope", media_type="application/json"),
    )
    sim_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
            uncertainty_envelopes={
                "step_latency_ms": UncertaintyEnvelopeRef(
                    artifact_id=invalid_envelope_ref.artifact_id
                )
            },
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_packet_invalid_uncertainty_output",
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
    payload = from_canonical_bytes(store.get_bytes(outcome.artifacts[0].artifact_id))
    degraded_reasons = {item["reason"] for item in payload["degraded_paths"]}

    assert payload["uncertainty_bounds"] is None
    assert "uncertainty_output_admission_limited" in degraded_reasons
    assert any(
        note.startswith("uncertainty_output_admission_limited:") for note in payload["notes"]
    )


def test_build_decision_packet_includes_causal_section(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_causal")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)
    report_ref = persist_causal_effect_report(
        _ensure_ir_artifact_store(store),
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
        _ensure_ir_artifact_store(store),
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


def test_build_decision_packet_surfaces_dp_status_from_readiness_and_bounds(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_dp_status",
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.dp"))

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)
    readiness_ref = persist_decision_readiness_contract(
        store,
        DecisionReadinessContract(
            readiness_level=DecisionReadiness.ANALYST_ADVISORY,
            required_judges_passed=["structural", "statistical"],
            required_uncertainty_bounds={},
            mandatory_human_gate=False,
            assumptions_must_be_surfaced=[],
            expiry_conditions=[],
            evidence_depth_required="single_study",
            metadata={
                "readiness_cap": "analyst_advisory",
                "data_readiness_decision": "warn",
                "dp_effective_status": "bounded",
                "dp_block_reason": None,
                "dp_distortion_radius": 0.021,
                "dp_mechanism_family": "laplace",
                "dp_effect_interval": [-0.12, -0.03],
                "dp_robustness": {
                    "effective_status": "bounded",
                    "reason": "DP distortion exceeds the point-estimate tolerance.",
                    "distortion_radius": 0.021,
                    "mechanism_family": "laplace",
                    "effect_interval": [-0.12, -0.03],
                },
            },
        ),
    )
    bounds_ref = persist_bounds_bundle(
        _ensure_ir_artifact_store(store),
        BoundsBundle(
            estimand_type="ate",
            point_identified=False,
            lower_bound=-0.12,
            upper_bound=-0.03,
            consensus_lower=-0.12,
            consensus_upper=-0.03,
            sharpness_status="outer_approx",
            warnings=["dp_bounds_only"],
            metadata={
                "dp_effective_status": "bounded",
                "dp_distortion_radius": 0.021,
                "dp_mechanism_family": "laplace",
            },
        ),
    )

    state = ExperimentState(
        run_id="R_packet_dp_status",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_DECISION_READINESS_CONTRACT_REF: ArtifactRef.model_validate(
                readiness_ref.model_dump(mode="json")
            ),
            ARTIFACT_BOUNDS_BUNDLE_REF: ArtifactRef.model_validate(
                bounds_ref.model_dump(mode="json")
            ),
        },
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["artifacts"]["decision_readiness_contract_ref"] == str(readiness_ref.artifact_id)
    assert payload["artifacts"]["bounds_bundle_ref"] == str(bounds_ref.artifact_id)
    assert payload["causal"]["decision_readiness_contract_ref"] == str(readiness_ref.artifact_id)
    assert payload["causal"]["bounds_ref"] == str(bounds_ref.artifact_id)
    assert payload["causal"]["dp_effective_status"] == "bounded"
    assert payload["causal"]["dp_distortion_radius"] == 0.021
    assert payload["causal"]["dp_mechanism_family"] == "laplace"
    assert payload["causal"]["dp_effect_interval"] == [-0.12, -0.03]
    assert payload["causal"]["bounds_interval"] == [-0.12, -0.03]
    assert payload["causal"]["data_readiness_decision"] == "warn"


def test_build_decision_packet_includes_abm_alignment_section(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_abm",
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)
    abm_ref = persist_abm_alignment_report(
        _ensure_ir_artifact_store(store),
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
    abstraction_map_ref = persist_finite_state_abstraction_map(
        _ensure_ir_artifact_store(store),
        FiniteStateAbstractionMap(
            variable_maps=(
                VariableStateAbstraction(
                    micro_variable="X_m",
                    macro_variable="X",
                    state_map={"0": "0", "1": "1"},
                ),
            )
        ),
    )
    abstraction_certificate_ref = persist_abstraction_certificate(
        _ensure_ir_artifact_store(store),
        AbstractionCertificate(
            micro_graph_ref={
                "artifact_id": _artifact_id("a"),
                "kind": "ir.causal_graph_model",
                "media_type": "application/json",
            },
            macro_graph_ref={
                "artifact_id": _artifact_id("b"),
                "kind": "ir.causal_graph_model",
                "media_type": "application/json",
            },
            abstraction_map_ref=abstraction_map_ref,
            preservation_type=AbstractionPreservationType.EXACT,
            preserved_queries=("observational", "interventional"),
            error_bound=None,
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
            ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF: abstraction_map_ref,
            ARTIFACT_ABSTRACTION_CERTIFICATE_REF: abstraction_certificate_ref,
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
    assert payload["abstraction_certificate"]["certificate_ref"] == str(
        abstraction_certificate_ref.artifact_id
    )
    assert payload["abstraction_certificate"]["abstraction_map_ref"] == str(
        abstraction_map_ref.artifact_id
    )
    assert payload["abstraction_certificate"]["preservation_type"] == "exact"
    assert payload["artifacts"]["abm_alignment_report_ref"] == str(abm_ref.artifact_id)
    assert payload["artifacts"]["abstraction_certificate_ref"] == str(
        abstraction_certificate_ref.artifact_id
    )
    assert "abm_alignment.report_ref" in roles
    assert "abstraction_certificate.certificate_ref" in roles


def test_build_decision_packet_includes_approximate_abstraction_metadata(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_abm_approx",
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)
    abstraction_map_ref = persist_finite_state_abstraction_map(
        _ensure_ir_artifact_store(store),
        FiniteStateAbstractionMap(
            variable_maps=(
                VariableStateAbstraction(
                    micro_variable="X_m",
                    macro_variable="X",
                    state_map={"0": "0", "1": "1"},
                ),
            )
        ),
    )
    abstraction_certificate_ref = persist_abstraction_certificate(
        _ensure_ir_artifact_store(store),
        AbstractionCertificate(
            micro_graph_ref={
                "artifact_id": _artifact_id("c"),
                "kind": "ir.causal_graph_model",
                "media_type": "application/json",
            },
            macro_graph_ref={
                "artifact_id": _artifact_id("d"),
                "kind": "ir.causal_graph_model",
                "media_type": "application/json",
            },
            abstraction_map_ref=abstraction_map_ref,
            preservation_type=AbstractionPreservationType.APPROXIMATE,
            preserved_queries=(
                "mean_potential_outcome:type_mean",
                "policy_value:weighted_type_mean",
            ),
            error_bound=0.05,
            metadata={
                "abstraction_family": "type_mean_affine",
                "allowed_intervention_family": "type_symmetric",
                "intervention_family_verified": True,
                "proof_obligations_satisfied": [
                    "within_type_exchangeability",
                    "mean_closure",
                ],
                "estimand_error_bounds": {
                    "mean_potential_outcome:type_mean": 0.03,
                    "policy_value:weighted_type_mean": 0.02,
                },
                "diagnostics": {"within_type_dispersion": {"max": 0.1}},
                "non_preserved_queries": ["unit_level_potential_outcome"],
            },
        ),
    )

    state = ExperimentState(
        run_id="R_packet_abm_approx",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF: abstraction_map_ref,
            ARTIFACT_ABSTRACTION_CERTIFICATE_REF: abstraction_certificate_ref,
        },
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["abstraction_certificate"]["preservation_type"] == "approximate"
    assert payload["abstraction_certificate"]["error_bound"] == 0.05
    assert payload["abstraction_certificate"]["metadata"]["abstraction_family"] == (
        "type_mean_affine"
    )
    assert payload["abstraction_certificate"]["metadata"]["intervention_family_verified"] is True
    assert payload["abstraction_certificate"]["metadata"]["estimand_error_bounds"] == {
        "mean_potential_outcome:type_mean": 0.03,
        "policy_value:weighted_type_mean": 0.02,
    }


def test_build_decision_packet_includes_hte_and_backtest_sections(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_hte_bt")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)

    hte_ref = persist_hte_result(
        _ensure_ir_artifact_store(store),
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
        _ensure_ir_artifact_store(store),
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
        _ensure_ir_artifact_store(store),
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
    assert payload["backtest"]["trust_score_status"] == "unavailable"
    assert payload["backtest"]["trust_eligible"] is False
    assert payload["trust_profile"]["backtest_trust_score"] is None
    assert payload["trust_profile"]["backtest_trust_grade"] is None


def test_requested_completed_hte_source_never_falls_back_to_legacy_result(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_hte_followup_missing",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.packet.hte_followup"),
    )
    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)
    legacy_hte_ref = persist_hte_result(
        _ensure_ir_artifact_store(store),
        HTEResult(
            method=CausalMethod.CAUSAL_FOREST,
            ate=0.2,
            ate_ci_lower=0.1,
            ate_ci_upper=0.3,
            cate_values=[0.2, 0.2],
            n_samples=2,
            n_treated=1,
            n_control=1,
            n_features=1,
            feature_names=["income"],
        ),
    )
    state = ExperimentState(
        run_id="R_packet_hte_followup_missing",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_HTE_RESULT_REF: legacy_hte_ref},
        params={"completed_hte_source_run_id": "R_unowned_or_missing"},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    roles = {item.role for item in store.get_manifest(packet_ref.artifact_id).inputs}

    assert payload["hte"] is None
    hte_basis = payload["decision_validity_envelope"]["data_basis"]["summary"]
    assert hte_basis["completed_hte_request_status"] == "requested"
    assert hte_basis["completed_hte_source_status"] == "verification_missing"
    assert hte_basis["completed_hte_requested_source_run_id"] == "R_unowned_or_missing"
    assert hte_basis["completed_hte_limitation_code"] == (
        "completed_hte_selection_owner_not_established"
    )
    assert hte_basis["completed_hte_publication_authorization"] == "not_established"
    assert ARTIFACT_HTE_RESULT_REF not in payload["artifacts"]
    assert "artifact.hte_result_ref" not in roles
    assert payload["decision_validity_baseline"]["status"] == "warning"


def test_build_decision_packet_includes_calibration_validation_summary(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_c5b",
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    data_snapshot_ref = _persist_data_snapshot(store)
    candidate_ref = ArtifactRef(
        artifact_id="sha256:" + "2" * 64,
        kind="scientist.test",
        media_type="application/json",
    )
    calibration_validation_ref = persist_calibration_validation_bundle(
        store,
        CalibrationValidationBundle(
            run_id="R_packet_c5b",
            candidate_ref=candidate_ref,
            governance_verdict="approve",
            status="completed",
            backtest_matrix=BacktestMatrixResult(
                report_id="BTM_packet",
                backtest_report_ref=BacktestReportRef(artifact_id="sha256:" + "3" * 64),
                composite_score=0.81,
                worst_kind=BacktestKind.DISTRESS,
            ),
            stress_scenarios=StressScenarioResult(
                report_id="stress_packet",
                stress_test_report_ref=StressTestReportRef(artifact_id="sha256:" + "4" * 64),
                robustness_score=0.74,
                worst_scenario=StressScenarioKind.TRADE_DISRUPTION,
            ),
            leaderboard_entry=CalibrationLeaderboardEntry(
                entry_id="leaderboard_packet",
                run_id="R_packet_c5b",
                candidate_ref=candidate_ref,
                metrics=CalibrationLeaderboardMetrics(
                    calibration_fit_score=0.9,
                    backtest_matrix_score=0.81,
                    stress_robustness_score=0.74,
                    specification_curve_robustness=0.7,
                    transportability_score=0.8,
                    interference_fit=0.85,
                    strategic_response_plausibility=0.9,
                    governance_verdict="approve",
                    adversarial_passed=True,
                    eligible_for_promotion=True,
                    composite_score=0.82,
                ),
                worst_backtest_kind=BacktestKind.DISTRESS,
                worst_stress_scenario=StressScenarioKind.TRADE_DISRUPTION,
            ),
            governance_accountability_ref=GovernanceAccountabilityArtifactRef(
                artifact_id="sha256:" + "5" * 64
            ),
            governance_accountability_summary={
                "risk_weighted_verdict": "human_gate",
                "requires_human_review": True,
                "selected_threshold": 0.55,
            },
        ),
    )

    state = ExperimentState(
        run_id="R_packet_c5b",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF: calibration_validation_ref,
        },
    )
    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["calibration_validation"]["status"] == "completed"
    summary = payload["calibration_validation"]["summary"]
    assert summary["composite_score"] is None
    assert summary["worst_backtest_kind"] is None
    assert summary["eligible_for_promotion"] is False
    assert "backtest_matrix_report_not_established" in summary["gap_flags"]
    assert (
        payload["calibration_validation"]["governance_accountability_summary"][
            "risk_weighted_verdict"
        ]
        == "human_gate"
    )
    assert (
        payload["calibration_validation"]["governance_accountability_ref"] == "sha256:" + "5" * 64
    )


def test_build_decision_packet_includes_sensitivity_section(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_sensitivity",
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)
    sensitivity_ref = persist_sensitivity_result(
        _ensure_ir_artifact_store(store),
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
    assert payload["sensitivity"]["content"]["summary"]["status"] == "robust"


def test_build_decision_packet_records_degraded_paths_for_invalid_sensitivity_artifact(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_invalid_sensitivity",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.packet.invalid_sensitivity"),
    )

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    data_snapshot_ref = _persist_data_snapshot(store)
    invalid_sensitivity_ref = store.put_json(
        ["invalid"],
        PutOptions(kind="ir.sensitivity_result", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_packet_invalid_sensitivity",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_SENSITIVITY_RESULT_REF: invalid_sensitivity_ref},
    )
    outcome = BuildDecisionPacketNode().execute(ctx, state)
    payload = from_canonical_bytes(store.get_bytes(outcome.artifacts[0].artifact_id))
    degraded_reasons = {item["reason"] for item in payload["degraded_paths"]}

    assert payload["sensitivity"]["ref"] == str(invalid_sensitivity_ref.artifact_id)
    assert payload["sensitivity"]["parse_warning"] == "sensitivity_parse_failed"
    assert "sensitivity_result_load_failed" in degraded_reasons


def test_build_decision_packet_includes_causal_validity_section(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_causal_validity",
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)
    validity_ref = store.put_json(
        {
            "schema_version": "1.0",
            "confidence": {
                "confidence_interval_present": True,
                "honest_hte": {"enabled": True},
            },
            "checks": {
                "icp_invariance": {"status": "success"},
                "proximal_bridge": {"status": "success"},
                "recoverability": {"status": "skipped", "reason": "missing_mgraph"},
                "pag_refinement": {"status": "success"},
            },
            "capability_matrix": {"icp_invariance": "available"},
        },
        PutOptions(kind="scientist.causal_validity_bundle", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_packet_causal_validity",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF: validity_ref},
    )
    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["causal_validity"]["ref"] == str(validity_ref.artifact_id)
    assert payload["causal_validity"]["content"]["checks"]["icp_invariance"]["status"] == "success"
    assert payload["diagnostics_summary"]["icp_status"] == "success"
    assert payload["diagnostics_summary"]["pag_refinement_status"] == "success"


def test_build_decision_packet_includes_transportability_summary(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_transport",
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)

    report_ref = persist_causal_effect_report(
        _ensure_ir_artifact_store(store),
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
                status=TransportabilityStatus.IDENTIFIED,
                query="P*(Y|do(X))",
                final_confidence=0.73,
                feasible=True,
                resolution_rounds=2,
                unsupported_cases=["front-door outside simplified scope"],
                identification_engine="y0",
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
    assert summary["status"] == "identified"
    assert summary["final_confidence"] == 0.73
    assert summary["resolution_rounds"] == 2
    assert summary["unsupported_cases_count"] == 1
    assert summary["identification_engine"] == "y0"
    assert summary["unsupported_reason"] is None
    assert summary["proof_review_grade"] == "unknown"
    assert summary["proof_purpose"] == "conditional_graph_mathematics"
    assert summary["proof_status"] == "identified"
    assert summary["proof_stratum"] == "A1_extended"
    assert summary["proof_completeness"] == "sound_incomplete"
    assert summary["source_data_authority"] == "not_established"


def test_build_decision_packet_includes_ensemble_summary(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_ensemble",
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)
    ensemble_ref = persist_causal_model_ensemble(
        _ensure_ir_artifact_store(store),
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

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    state_snapshot_ref = _persist_state_snapshot(store)
    data_snapshot_ref = _persist_data_snapshot(store, data_ref=state_snapshot_ref)

    ensemble_ref = persist_causal_model_ensemble(
        _ensure_ir_artifact_store(store),
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
        _ensure_ir_artifact_store(store),
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


def test_build_decision_packet_surfaces_strategic_runtime_artifacts(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store, registry_bundle=registry_bundle, run_id="R_packet_strategic"
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.strategic"))

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    data_snapshot_ref = _persist_data_snapshot(store)
    base_graph_ref = store.put_json(
        {"graph": {}},
        PutOptions(kind="ir.causal_graph", media_type="application/json"),
    )
    policy_rule_ref = store.put_json(
        {"policy_rule": {}},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
    )
    leader_table_ref = persist_strategic_payoff_table(
        _ensure_ir_artifact_store(store),
        FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=("leader", "follower"),
            action_spaces={"leader": ("A", "B"), "follower": ("X", "Y")},
            payoffs={
                "leader=A|follower=X": 2.0,
                "leader=A|follower=Y": 1.0,
                "leader=B|follower=X": 0.0,
                "leader=B|follower=Y": 0.5,
            },
        ),
    )
    follower_table_ref = persist_strategic_payoff_table(
        _ensure_ir_artifact_store(store),
        FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=("leader", "follower"),
            action_spaces={"leader": ("A", "B"), "follower": ("X", "Y")},
            payoffs={
                "leader=A|follower=X": 1.0,
                "leader=A|follower=Y": 1.0,
                "leader=B|follower=X": 0.5,
                "leader=B|follower=Y": 0.25,
            },
        ),
    )
    strategic_scm_ref = persist_strategic_scm(
        _ensure_ir_artifact_store(store),
        StrategicSCM(
            base_graph_ref=ArtifactRefModel.model_validate(base_graph_ref.model_dump(mode="json")),
            strategic_agents=("leader", "follower"),
            utility_refs={
                "leader": leader_table_ref,
                "follower": follower_table_ref,
            },
            policy_rule_ref=ArtifactRefModel.model_validate(
                policy_rule_ref.model_dump(mode="json")
            ),
            equilibrium_concept=StrategicEquilibriumConcept.STACKELBERG,
        ),
    )
    strategic_closure_ref = persist_strategic_closure_summary(
        _ensure_ir_artifact_store(store),
        StrategicClosureSummary(
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
            equilibrium_concept=StrategicEquilibriumConcept.STACKELBERG,
            equilibrium_selection_dependence="follower_best_response_tie_breaking",
            profile_count=4,
            equilibrium_count=2,
        ),
    )
    equilibrium_set_ref = persist_equilibrium_set_summary(
        _ensure_ir_artifact_store(store),
        EquilibriumSetSummary(
            equilibrium_profiles=(
                {"leader": "A", "follower": "X"},
                {"leader": "A", "follower": "Y"},
            ),
            equilibrium_count=2,
            multiplicity_note="multiple_stackelberg_equilibria",
        ),
    )
    selected_equilibrium_ref = persist_equilibrium_selection_summary(
        _ensure_ir_artifact_store(store),
        EquilibriumSelectionSummary(
            selected_equilibrium={"leader": "A", "follower": "X"},
            equilibrium_selection_dependence="follower_best_response_tie_breaking",
        ),
    )
    post_value_ref = persist_post_adaptation_policy_value_summary(
        _ensure_ir_artifact_store(store),
        PostAdaptationPolicyValueSummary(
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
            baseline_policy_value=1.0,
            point_value=1.3,
        ),
    )
    performative_shift_ref = persist_performative_shift_summary(
        _ensure_ir_artifact_store(store),
        PerformativeShiftSummary(
            performative_shift=0.3,
            baseline_policy_value=1.0,
            post_adaptation_policy_value=1.3,
            analysis_scope=PerformativeLoopAnalysisScope.ITERATED_LOOP,
            proof_family=PerformativeLoopProofFamily.STATEFUL_LIPSCHITZ,
            stability_status=PerformativeLoopStabilityStatus.CERTIFIED_CONVERGENT,
            contraction_upper_bound=0.8,
            convergence_rate_upper=0.8,
            witness_strength=PerformativeLoopWitnessStrength.THEOREM,
            recommended_action=PerformativeLoopRecommendedAction.ALLOW_AUTO_ITERATION,
            human_summary="Closed-loop contraction is certified below one.",
        ),
    )
    mfg_perturbation_ref = persist_mean_field_perturbation_spec(
        _ensure_ir_artifact_store(store),
        compile_intervention_spec_to_mean_field_perturbation(
            InterventionSpec(type="stochastic", distribution="benefit_assignment_kernel"),
            source_intervention_ref=ArtifactRefModel(
                artifact_id=policy_rule_ref.artifact_id,
                kind="ir.intervention_certificate",
                media_type="application/json",
            ),
            baseline_policy_ref=ArtifactRefModel.model_validate(
                policy_rule_ref.model_dump(mode="json")
            ),
        ),
    )
    mfg_numerics_ref = persist_mean_field_macro_simulation_config(
        _ensure_ir_artifact_store(store),
        MeanFieldMacroSimulationConfig(
            population_measure_snapshot_ref=ArtifactRefModel(
                artifact_id=policy_rule_ref.artifact_id,
                kind="ir.population_measure_snapshot",
                media_type="application/json",
            ),
            coefficient_field_ref=ArtifactRefModel(
                artifact_id=policy_rule_ref.artifact_id,
                kind="ir.coefficient_field_estimate",
                media_type="application/json",
            ),
            policy_kernel_ref=ArtifactRefModel(
                artifact_id=policy_rule_ref.artifact_id,
                kind="ir.policy_kernel_estimate",
                media_type="application/json",
            ),
            numerics_scheme="semi_implicit_finite_difference",
            fixed_point_method="forward_backward_sweep",
            runtime_mode="replay",
            time_horizon=8.0,
            time_steps=64,
            state_grid_shape=(32, 16),
        ),
    )
    mfg_equilibrium_ref = persist_mean_field_equilibrium_certificate(
        _ensure_ir_artifact_store(store),
        MeanFieldEquilibriumCertificate(
            intervention_kind="distributional",
            baseline_policy_ref=ArtifactRefModel.model_validate(
                policy_rule_ref.model_dump(mode="json")
            ),
            intervention_spec_ref=mfg_perturbation_ref,
            mean_field_model_class="second_order",
            well_posedness={
                "scm_solvability_ref": ArtifactRefModel(
                    artifact_id=policy_rule_ref.artifact_id,
                    kind="ir.proof_bundle",
                    media_type="application/json",
                ),
                "monotonicity_type": "lasry_lions",
                "convexity_verified": True,
                "regularity_scope": "Lipschitz_in_measure",
                "uniqueness_status": "local_stable_branch",
            },
            identification={
                "graph_semantics": "sigma_separation",
                "positivity_status": "verified",
                "selection_rule": "stable_branch",
                "identified_estimands": ("welfare",),
            },
            stability={
                "bound_type": "ergodic_exponential",
                "constant_C": 1.0,
                "decay_rate": 0.2,
                "metric": "W1",
            },
            equilibrium_solution={
                "solver_residual_ref": ArtifactRefModel(
                    artifact_id=policy_rule_ref.artifact_id,
                    kind="ir.solver_residual",
                    media_type="application/json",
                ),
                "mass_conservation_ref": ArtifactRefModel(
                    artifact_id=policy_rule_ref.artifact_id,
                    kind="ir.mass_conservation_report",
                    media_type="application/json",
                ),
            },
            provenance={
                "numerics_config_ref": mfg_numerics_ref,
            },
        ),
    )
    strategic_bundle_ref = persist_strategic_response_bundle(
        _ensure_ir_artifact_store(store),
        StrategicResponseBundle(
            causal_component_ref=ArtifactRefModel.model_validate(
                policy_rule_ref.model_dump(mode="json")
            ),
            strategic_closure_ref=strategic_closure_ref,
            equilibrium_selection_dependence="follower_best_response_tie_breaking",
            equilibrium_set_ref=equilibrium_set_ref,
            multiplicity_note="multiple_stackelberg_equilibria",
            mfg_equilibrium_ref=mfg_equilibrium_ref,
            performative_shift_ref=performative_shift_ref,
            post_adaptation_policy_value_ref=post_value_ref,
            decomposition_status=StrategicDecompositionStatus.EXACT,
            decomposition_certificate_ref=ArtifactRefModel(
                artifact_id=policy_rule_ref.artifact_id,
                kind="ir.strategic_decomposition_certificate",
                media_type="application/json",
            ),
            anchor_equilibrium_ref=selected_equilibrium_ref,
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
        ),
    )

    state = ExperimentState(
        run_id="R_packet_strategic",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_STRATEGIC_SCM_REF: strategic_scm_ref,
            ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF: strategic_bundle_ref,
        },
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["artifacts"]["strategic_scm_ref"] == str(strategic_scm_ref.artifact_id)
    assert payload["artifacts"]["strategic_response_bundle_ref"] == str(
        strategic_bundle_ref.artifact_id
    )
    assert payload["strategic"]["fallback_mode"] == "exact_equilibrium"
    assert payload["strategic"]["decomposition_status"] == "exact"
    assert payload["strategic"]["equilibrium_selection_dependence"] == (
        "follower_best_response_tie_breaking"
    )
    assert payload["strategic"]["strategic_scm_ref"] == str(strategic_scm_ref.artifact_id)
    assert payload["strategic"]["strategic_response_bundle_ref"] == str(
        strategic_bundle_ref.artifact_id
    )
    assert payload["strategic"]["post_adaptation_policy_value"] == 1.3
    assert payload["strategic"]["performative_shift_ref"] == str(performative_shift_ref.artifact_id)
    assert payload["strategic"]["performative_shift"] == 0.3
    assert payload["strategic"]["performative_loop"]["stability_status"] == ("certified_convergent")
    assert payload["strategic"]["mfg_equilibrium_ref"] == str(mfg_equilibrium_ref.artifact_id)
    assert payload["strategic"]["mfg_numerics_config_ref"] == str(mfg_numerics_ref.artifact_id)
    assert payload["strategic"]["mfg_uniqueness_status"] == "local_stable_branch"
    assert payload["strategic"]["mfg_selection_rule"] == "stable_branch"
    assert payload["strategic"]["mfg_numerics_scheme"] == "semi_implicit_finite_difference"
    assert payload["strategic"]["mfg_fixed_point_method"] == "forward_backward_sweep"
    assert payload["strategic"]["mfg_population_channels"] == [
        "policy_kernel",
        "initial_distribution",
    ]
    assert payload["strategic"]["mfg_policy_kernel_overlap_required"] is True


def test_build_decision_packet_includes_blocked_decomposition_failure_card(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_strategic_decomposition_blocked",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.packet.strategic.decomposition_blocked"),
    )

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    data_snapshot_ref = _persist_data_snapshot(store)
    base_graph_ref = store.put_json(
        {"graph": {}},
        PutOptions(kind="ir.causal_graph", media_type="application/json"),
    )
    policy_rule_ref = store.put_json(
        {"policy_rule": {}},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
    )
    leader_table_ref = persist_strategic_payoff_table(
        _ensure_ir_artifact_store(store),
        FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=("leader", "follower"),
            action_spaces={"leader": ("A",), "follower": ("X",)},
            payoffs={"leader=A|follower=X": 1.0},
        ),
    )
    follower_table_ref = persist_strategic_payoff_table(
        _ensure_ir_artifact_store(store),
        FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=("leader", "follower"),
            action_spaces={"leader": ("A",), "follower": ("X",)},
            payoffs={"leader=A|follower=X": 1.0},
        ),
    )
    strategic_scm_ref = persist_strategic_scm(
        _ensure_ir_artifact_store(store),
        StrategicSCM(
            base_graph_ref=ArtifactRefModel.model_validate(base_graph_ref.model_dump(mode="json")),
            strategic_agents=("leader", "follower"),
            utility_refs={
                "leader": leader_table_ref,
                "follower": follower_table_ref,
            },
            policy_rule_ref=ArtifactRefModel.model_validate(
                policy_rule_ref.model_dump(mode="json")
            ),
            equilibrium_concept=StrategicEquilibriumConcept.STACKELBERG,
        ),
    )
    strategic_closure_ref = persist_strategic_closure_summary(
        _ensure_ir_artifact_store(store),
        StrategicClosureSummary(
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
            equilibrium_concept=StrategicEquilibriumConcept.STACKELBERG,
            equilibrium_selection_dependence="deterministic",
            profile_count=1,
            equilibrium_count=1,
        ),
    )
    equilibrium_set_ref = persist_equilibrium_set_summary(
        _ensure_ir_artifact_store(store),
        EquilibriumSetSummary(
            equilibrium_profiles=({"leader": "A", "follower": "X"},),
            equilibrium_count=1,
        ),
    )
    selected_equilibrium_ref = persist_equilibrium_selection_summary(
        _ensure_ir_artifact_store(store),
        EquilibriumSelectionSummary(
            selected_equilibrium={"leader": "A", "follower": "X"},
            equilibrium_selection_dependence="deterministic",
        ),
    )
    post_value_ref = persist_post_adaptation_policy_value_summary(
        _ensure_ir_artifact_store(store),
        PostAdaptationPolicyValueSummary(
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
            baseline_policy_value=1.0,
            point_value=1.2,
        ),
    )
    failure_card_ref = persist_strategic_decomposition_failure_card(
        _ensure_ir_artifact_store(store),
        StrategicDecompositionFailureCard(
            failure_code="decomposition_cross_world_anchor_undefined",
            message=(
                "Point decomposition requires an explicit frozen-baseline strategy anchor; "
                "the current runtime only solves the post-policy equilibrium."
            ),
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
            equilibrium_selection_dependence="deterministic",
        ),
    )
    strategic_bundle_ref = persist_strategic_response_bundle(
        _ensure_ir_artifact_store(store),
        StrategicResponseBundle(
            causal_component_ref=ArtifactRefModel.model_validate(
                policy_rule_ref.model_dump(mode="json")
            ),
            strategic_closure_ref=strategic_closure_ref,
            equilibrium_selection_dependence="deterministic",
            equilibrium_set_ref=equilibrium_set_ref,
            selected_equilibrium_ref=selected_equilibrium_ref,
            post_adaptation_policy_value_ref=post_value_ref,
            decomposition_status=StrategicDecompositionStatus.BLOCKED,
            decomposition_failure_card_ref=failure_card_ref,
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
        ),
    )

    state = ExperimentState(
        run_id="R_packet_strategic_decomposition_blocked",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_STRATEGIC_SCM_REF: strategic_scm_ref,
            ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF: strategic_bundle_ref,
        },
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["strategic"]["fallback_mode"] == "exact_equilibrium"
    assert payload["strategic"]["decomposition_status"] == "blocked"
    assert payload["strategic"]["decomposition_failure_code"] == (
        "decomposition_cross_world_anchor_undefined"
    )
    assert "frozen-baseline strategy anchor" in payload["strategic"]["decomposition_message"]


def test_build_decision_packet_falls_back_to_blocked_strategic_summary_without_bundle(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store, registry_bundle=registry_bundle, run_id="R_packet_strategic_blocked"
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.packet.strategic.blocked"),
    )

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    data_snapshot_ref = _persist_data_snapshot(store)
    base_graph_ref = store.put_json(
        {"graph": {}},
        PutOptions(kind="ir.causal_graph", media_type="application/json"),
    )
    policy_rule_ref = store.put_json(
        {"policy_rule": {}},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
    )
    leader_table_ref = persist_strategic_payoff_table(
        _ensure_ir_artifact_store(store),
        FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=("leader", "follower"),
            action_spaces={"leader": ("A",), "follower": ("X",)},
            payoffs={"leader=A|follower=X": 1.0},
        ),
    )
    follower_table_ref = persist_strategic_payoff_table(
        _ensure_ir_artifact_store(store),
        FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=("leader", "follower"),
            action_spaces={"leader": ("A",), "follower": ("X",)},
            payoffs={"leader=A|follower=X": 1.0},
        ),
    )
    strategic_scm_ref = persist_strategic_scm(
        _ensure_ir_artifact_store(store),
        StrategicSCM(
            base_graph_ref=ArtifactRefModel.model_validate(base_graph_ref.model_dump(mode="json")),
            strategic_agents=("leader", "follower"),
            utility_refs={
                "leader": leader_table_ref,
                "follower": follower_table_ref,
            },
            policy_rule_ref=ArtifactRefModel.model_validate(
                policy_rule_ref.model_dump(mode="json")
            ),
            equilibrium_concept=StrategicEquilibriumConcept.STACKELBERG,
        ),
    )

    state = ExperimentState(
        run_id="R_packet_strategic_blocked",
        params={
            "strategic_response": {
                "fallback_mode": "blocked",
                "equilibrium_selection_dependence": "runtime_precondition_blocked",
                "blocked_reason": "missing_causal_report_for_strategic_decomposition",
            }
        },
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_STRATEGIC_SCM_REF: strategic_scm_ref,
        },
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["strategic"]["strategic_scm_ref"] == str(strategic_scm_ref.artifact_id)
    assert payload["strategic"]["strategic_response_bundle_ref"] is None
    assert payload["strategic"]["fallback_mode"] == "blocked"
    assert payload["strategic"]["blocked_reason"] == (
        "missing_causal_report_for_strategic_decomposition"
    )


def test_s1_nested_backtest_diagnostic_surfaces_after_fresh_decision_packet_read(tmp_path) -> None:
    import hashlib
    import json
    from collections import Counter

    import pytest

    from polisyos.data_forge.domains.ukraine.manifests import HouseholdDiagnosticPanelBasis
    from polisyos.data_forge.read_api.ukraine import read_ukraine_json_snapshot
    from polisyos.ir.analytics.backtest import load_backtest_report
    from polisyos.scientist.governance.backtest_matrix import BacktestMatrixResult
    from polisyos.scientist.governance.calibration_validation import (
        CalibrationValidationBundle,
        load_calibration_validation_bundle,
        persist_calibration_validation_bundle,
    )
    from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
    from polisyos.scientist.methods.backtesting.plan import (
        HistoricalValidationPlan,
        PredictionSource,
    )
    from polisyos.scientist.nodes.builtins.decide.decision_packet.outcome_sections import (
        _build_calibration_validation_section,
    )

    store = FileSystemCAS(tmp_path / "s1-cas")
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="s1-nested")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.s1"))

    selected_training_role = "fixture_training"
    selected_validation_role = "fixture_validation"
    selected_holdout_role = "fixture_holdout"
    history_path = tmp_path / "nested-history.json"
    history_path.write_text(json.dumps({"observed_value": [100.0, 100.0, 100.0]}), encoding="utf-8")
    plan = HistoricalValidationPlan(
        plan_id="s1-nested-scenario",
        plan_label="controlled nested diagnostic fixture",
        historical_data_path=str(history_path),
        ground_truth_outcomes={"observed_value": [100.0, 100.0, 100.0]},
        target_metrics=["observed_value"],
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"observed_value": [110.0, 110.0, 110.0]},
        selected_training_role=selected_training_role,
        selected_validation_role=selected_validation_role,
        selected_holdout_role=selected_holdout_role,
        metadata={
            "holdout_windows": ["test_2025"],
            "selected_training_role": selected_training_role,
            "selected_validation_role": selected_validation_role,
            "selected_holdout_role": selected_holdout_role,
        },
    )
    source_json_snapshot_reads = {}
    source_refs = []
    source_contract_by_role = {
        "household_source_basis": "scientist.d3.household_candidate_basis",
        "selected_split_manifest": "scientist.d4.calibration_splits",
    }
    source_model_by_contract = {
        "scientist.d3.household_candidate_basis": HouseholdDiagnosticPanelBasis,
        "scientist.d4.calibration_splits": dict[str, dict[str, str]],
    }
    source_payload_by_contract = {
        "scientist.d3.household_candidate_basis": HouseholdDiagnosticPanelBasis(
            status="complete",
            source_row_count=1,
            panel_artifact={
                "path": "controlled-panel.parquet",
                "sha256": "a" * 64,
                "size_bytes": 1,
            },
        ).model_dump(mode="json"),
        "scientist.d4.calibration_splits": {
            "fixture_training": {"start": "2023-01-01", "end": "2023-12-31"},
            "fixture_validation": {"start": "2024-01-01", "end": "2024-12-31"},
            "fixture_holdout": {"start": "2025-01-01", "end": "2025-12-31"},
        },
    }
    controlled_extension_variants = iter(("source_a", "source_b"))
    for role in (
        "household_candidate_panel",
        "household_source_basis",
        "selected_split_manifest",
        "controlled_extension_source",
        "backtest_report",
        "controlled_extension_source",
    ):
        contract = source_contract_by_role.get(role)
        payload_value = (
            source_payload_by_contract[contract] if contract is not None else {"source_role": role}
        )
        if role == "controlled_extension_source":
            payload_value = {
                "source_role": role,
                "fixture_variant": next(controlled_extension_variants),
            }
        payload = json.dumps(payload_value, separators=(",", ":")).encode("utf-8")
        source_ref = store.put_bytes(
            payload,
            PutOptions(
                kind="data_forge.ukraine.stage_output_snapshot",
                media_type="application/json",
            ),
            return_selected_profile=True,
        )
        source_refs.append(
            CoreInputRef(
                artifact_id=source_ref.artifact_id,
                role=role,
                manifest_profile_sha256=source_ref.manifest_profile_sha256,
            )
        )
        if contract is not None:
            read = read_ukraine_json_snapshot(
                store,
                source_ref,
                raw_payload_bytes=payload,
                expected_sha256=hashlib.sha256(payload).hexdigest(),
                expected_size_bytes=len(payload),
                expected_kind="data_forge.ukraine.stage_output_snapshot",
                consumer_contract=contract,
                model_type=source_model_by_contract[contract],
            )
            source_json_snapshot_reads[contract] = read.provenance
    controlled_extension_source_edges = [
        item for item in source_refs if item.role == "controlled_extension_source"
    ]
    assert len(controlled_extension_source_edges) == 2
    assert len({str(item.artifact_id) for item in controlled_extension_source_edges}) == 2
    candidate_ref = store.put_json(
        {"candidate": "test-owned"},
        PutOptions(kind="scientist.calibration_candidate", media_type="application/json"),
        return_selected_profile=True,
    )
    candidate_artifact_ref = ArtifactRef.model_validate(candidate_ref.model_dump(mode="python"))
    candidate_input_ref = CoreInputRef(
        artifact_id=candidate_ref.artifact_id,
        role="candidate",
        manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
    )
    report, report_ref = BacktestOrchestrator(cas=store).run_with_ref(
        [plan],
        report_id="s1-nested-report",
        inputs=[candidate_input_ref, *source_refs],
        metadata={
            "purpose": "candidate_diagnostic",
            "selected_split_roles": {
                "training": selected_training_role,
                "validation": selected_validation_role,
                "holdout": selected_holdout_role,
            },
        },
    )
    assert [item.y_pred - item.y_true for item in report.scenarios[0].outcome_comparisons] == [
        10.0,
        10.0,
        10.0,
    ]
    producer_diagnostic = next(
        item for item in report.metric_diagnostics if item.metric_name == "observed_value"
    )
    assert (
        producer_diagnostic.status == "not_computable"
        and producer_diagnostic.reason == "zero_variance"
        and producer_diagnostic.n == 3
        and producer_diagnostic.mean_residual == 10.0
        and producer_diagnostic.method_id is None
        and producer_diagnostic.backend_id is None
        and producer_diagnostic.backend_version is None
        and producer_diagnostic.statistic is None
        and producer_diagnostic.p_value is None
    )
    assert report.trust_eligible is False and report.trust_score is None
    # Profile-only variants must reuse the exact payload emitted by the producer.
    report = load_backtest_report(_ensure_ir_artifact_store(store), report_ref)
    core_report_ref = ArtifactRef.model_validate(report_ref.model_dump(mode="python"))
    bundle = CalibrationValidationBundle(
        schema_version="1.1",
        run_id="s1-nested",
        candidate_ref=candidate_artifact_ref,
        governance_verdict="human_gate",
        status="candidate_diagnostic",
        purpose="candidate_diagnostic",
        selected_training_role="fixture_training",
        selected_validation_role="fixture_validation",
        selected_holdout_role="fixture_holdout",
        source_json_snapshot_reads=source_json_snapshot_reads,
        backtest_matrix=BacktestMatrixResult(
            report_id="s1-nested-report",
            backtest_report_ref=report_ref,
        ),
    )
    bundle_ref = persist_calibration_validation_bundle(
        store,
        bundle,
        inputs=[candidate_input_ref, *source_refs],
    )
    store_manifest = store.get_manifest(bundle_ref)
    assert store_manifest.artifact_schema is not None
    assert store_manifest.artifact_schema.version == "1.1"
    expected_report_identity = (
        "backtest_report",
        str(report_ref.artifact_id),
        report_ref.manifest_profile_sha256,
    )
    structural_report_edges = [
        item
        for item in store_manifest.inputs
        if (item.role, str(item.artifact_id), item.manifest_profile_sha256)
        == expected_report_identity
    ]
    assert len(structural_report_edges) == 1
    assert sum(item.role == "backtest_report" for item in store_manifest.inputs) == 2
    assert sum(item.role == "controlled_extension_source" for item in store_manifest.inputs) == 2
    outer_source_inputs = list(store_manifest.inputs)
    outer_source_inputs.remove(structural_report_edges[0])
    report_source_inputs = list(store.get_manifest(core_report_ref).inputs)

    def edge_identity(item):
        return item.role, str(item.artifact_id), item.manifest_profile_sha256

    def replace_input_edge(inputs, original_edge, replacement_edge):
        original_identity = edge_identity(original_edge)
        matching_indices = [
            index for index, item in enumerate(inputs) if edge_identity(item) == original_identity
        ]
        assert len(matching_indices) == 1
        index = matching_indices[0]
        untouched_before = Counter(
            edge_identity(item) for position, item in enumerate(inputs) if position != index
        )
        altered = list(inputs)
        altered[index] = replacement_edge
        untouched_after = Counter(
            edge_identity(item) for position, item in enumerate(altered) if position != index
        )
        assert untouched_before == untouched_after
        assert edge_identity(replacement_edge) != original_identity
        return altered

    def replace_input_profile(inputs, original_edge, selected_profile):
        replacement = original_edge.model_copy(update={"manifest_profile_sha256": selected_profile})
        return replace_input_edge(inputs, original_edge, replacement)

    def replace_role_profiles(inputs, role, selected_profile):
        role_edges = [item for item in inputs if item.role == role]
        assert role_edges
        altered = list(inputs)
        for role_edge in role_edges:
            altered = replace_input_profile(altered, role_edge, selected_profile)
        return altered

    assert Counter(map(edge_identity, outer_source_inputs)) == Counter(
        map(edge_identity, report_source_inputs)
    )
    c5b_candidate_edges = [item for item in store_manifest.inputs if item.role == "candidate"]
    report_candidate_edges = [
        item for item in store.get_manifest(core_report_ref).inputs if item.role == "candidate"
    ]
    assert len(c5b_candidate_edges) == len(report_candidate_edges) == 1
    expected_candidate_identity = (
        str(candidate_artifact_ref.artifact_id),
        candidate_artifact_ref.manifest_profile_sha256,
    )
    assert (
        str(c5b_candidate_edges[0].artifact_id),
        c5b_candidate_edges[0].manifest_profile_sha256,
    ) == expected_candidate_identity
    assert (
        str(report_candidate_edges[0].artifact_id),
        report_candidate_edges[0].manifest_profile_sha256,
    ) == expected_candidate_identity
    assert (
        store.get_manifest_by_profile(*expected_candidate_identity).artifact_id
        == candidate_artifact_ref.artifact_id
    )
    assert store_manifest.kind == "scientist.calibration_validation_bundle"
    assert store_manifest.media_type == "application/json"
    fresh = load_calibration_validation_bundle(store, bundle_ref)
    section = _build_calibration_validation_section(
        ctx,
        {ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF: bundle_ref},
    )
    assert section is not None
    assert section["status"] == section["purpose"] == "candidate_diagnostic"
    assert section["backtest_report_ref"] == str(report_ref.artifact_id)
    assert section["backtest_metric_diagnostics"][0]["reason"] == "zero_variance"
    assert section["summary"]["eligible_for_promotion"] is False
    assert section["source_json_snapshot_binding_status"] == "available"
    assert fresh.readout_summary()["source_json_snapshot_binding_status"] == "available"
    assert "controlled_extension_source" in {item.role for item in store_manifest.inputs}
    for contract in source_contract_by_role.values():
        assert section["source_json_snapshot_reads"][contract]["profile_status"] == (
            "profile_absent_raw_snapshot_candidate"
        )
        assert (
            section["summary"]["source_json_snapshot_reads"][contract]
            == (section["source_json_snapshot_reads"][contract])
        )

    trinity_ref = _persist_trinity_bundle(store, {"trinity": {}})
    data_snapshot_ref = _persist_data_snapshot(store)
    outer_inputs = list(store_manifest.inputs)
    structural_index = next(
        i
        for i, item in enumerate(outer_inputs)
        if (item.role, str(item.artifact_id), item.manifest_profile_sha256)
        == expected_report_identity
    )
    source_inputs = [item for i, item in enumerate(outer_inputs) if i != structural_index]

    def packet_for_bundle(candidate_bundle_ref, candidate_report_ref=report_ref):
        candidate_bundle_artifact_ref = ArtifactRef(
            artifact_id=candidate_bundle_ref.artifact_id,
            kind="scientist.calibration_validation_bundle",
            media_type="application/json",
            manifest_profile_sha256=candidate_bundle_ref.manifest_profile_sha256,
        )
        candidate_report_artifact_ref = ArtifactRef(
            artifact_id=candidate_report_ref.artifact_id,
            kind="ir.backtest_report",
            media_type="application/json",
            manifest_profile_sha256=candidate_report_ref.manifest_profile_sha256,
        )
        candidate_state = ExperimentState(
            run_id="s1-nested",
            inputs={
                INPUT_TRINITY_BUNDLE_REF: trinity_ref,
                INPUT_REGISTRY_BUNDLE_REF: registry,
                INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
            },
            artifacts_index={
                ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF: candidate_bundle_artifact_ref,
                ARTIFACT_BACKTEST_REPORT_REF: candidate_report_artifact_ref,
            },
        )
        packet_ref = BuildDecisionPacketNode().execute(ctx, candidate_state).artifacts[0]
        return from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    def assert_calibration_bundle_parse_refused(label, *, reads, expected_error):
        malformed_bundle = fresh.model_copy(
            update={
                "run_id": f"s1-nested-{label}",
                "source_json_snapshot_reads": reads,
            }
        )
        malformed_ref = persist_calibration_validation_bundle(
            store,
            malformed_bundle,
            inputs=source_inputs,
        )
        with pytest.raises(ValueError, match=expected_error):
            load_calibration_validation_bundle(store, malformed_ref)
        assert _build_calibration_validation_section(
            ctx,
            {ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF: malformed_ref},
        ) == {
            "ref": str(malformed_ref.artifact_id),
            "parse_warning": "calibration_validation_bundle_parse_failed",
        }
        packet = packet_for_bundle(malformed_ref)
        assert packet["calibration_validation"]["parse_warning"] == (
            "calibration_validation_bundle_parse_failed"
        )
        assert "summary" not in packet["calibration_validation"]
        assert packet["backtest"]["backtest_report_status"] == "available"
        assert packet["backtest"]["metric_diagnostics_status"] == "computed"
        assert packet["backtest"]["metric_diagnostics"]
        assert packet["backtest"]["trust_eligible"] is False

    def assert_binding_refused(
        label,
        *,
        reads=None,
        inputs=None,
        expected_status="unavailable",
        expected_reason=None,
        candidate_report_ref=report_ref,
        candidate_ref_for_bundle=candidate_artifact_ref,
        expected_backtest_status="available",
    ):
        candidate_bundle = fresh.model_copy(
            update={
                "run_id": f"s1-nested-{label}",
                "candidate_ref": candidate_ref_for_bundle,
                "source_json_snapshot_reads": (
                    dict(fresh.source_json_snapshot_reads) if reads is None else reads
                ),
                "backtest_matrix": fresh.backtest_matrix.model_copy(
                    update={"backtest_report_ref": candidate_report_ref}
                ),
            }
        )
        variant_ref = persist_calibration_validation_bundle(
            store,
            candidate_bundle,
            inputs=source_inputs if inputs is None else inputs,
        )
        variant = load_calibration_validation_bundle(store, variant_ref)
        summary = variant.readout_summary()
        assert summary["source_json_snapshot_binding_status"] == expected_status
        if expected_reason is not None:
            assert summary["source_json_snapshot_binding_reason"] == expected_reason
        assert summary["backtest_report_status"] == expected_backtest_status
        assert summary["backtest_report_ref"] == str(candidate_report_ref.artifact_id)
        assert summary["backtest_metric_diagnostics_status"] == "unavailable"
        assert summary["backtest_metric_diagnostics"] is None
        assert summary["eligible_for_promotion"] is False
        direct_section = _build_calibration_validation_section(
            ctx,
            {ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF: variant_ref},
        )
        assert direct_section is not None
        assert direct_section["source_json_snapshot_binding_status"] == expected_status
        assert direct_section["backtest_metric_diagnostics_status"] == "unavailable"
        assert direct_section["backtest_metric_diagnostics"] is None
        packet = packet_for_bundle(variant_ref, candidate_report_ref)
        direct = packet["backtest"]
        nested = packet["calibration_validation"]
        assert direct["report_ref"] == str(candidate_report_ref.artifact_id)
        assert direct["backtest_report_status"] == expected_backtest_status
        assert direct["metric_diagnostics_status"] == "unavailable"
        assert direct["metric_diagnostics"] is None
        assert direct["trust_eligible"] is False
        assert nested["backtest_report_ref"] == str(candidate_report_ref.artifact_id)
        assert nested["backtest_report_status"] == expected_backtest_status
        assert nested["backtest_metric_diagnostics_status"] == "unavailable"
        assert nested["backtest_metric_diagnostics"] is None
        assert nested["source_json_snapshot_binding_status"] == expected_status
        assert nested["summary"]["source_json_snapshot_binding_status"] == expected_status
        assert nested["summary"]["eligible_for_promotion"] is False

    assert_binding_refused("provenance-removed", reads={}, expected_status="not_established")
    assert_calibration_bundle_parse_refused(
        "provenance-partial",
        reads={
            "scientist.d3.household_candidate_basis": source_json_snapshot_reads[
                "scientist.d3.household_candidate_basis"
            ]
        },
        expected_error="source JSON profile reads do not match the purpose contract set",
    )
    source_basis_edge = next(
        item for item in source_inputs if item.role == "household_source_basis"
    )
    split_edge = next(item for item in source_inputs if item.role == "selected_split_manifest")
    panel_edge = next(item for item in source_inputs if item.role == "household_candidate_panel")
    candidate_edge = next(item for item in source_inputs if item.role == "candidate")
    candidate_free_report_ref = persist_backtest_report(
        _ensure_ir_artifact_store(store),
        report,
        inputs=source_refs,
    )
    candidate_free_inputs = [item for item in source_inputs if item.role != "candidate"]
    assert_binding_refused(
        "candidate-edge-missing-on-both-manifests",
        inputs=candidate_free_inputs,
        candidate_report_ref=candidate_free_report_ref,
        expected_status="not_established",
        expected_reason="candidate_source_candidate_edge_not_selected",
    )
    assert_binding_refused(
        "candidate-edge-duplicate",
        inputs=[*source_inputs, candidate_edge],
        expected_reason="candidate_source_input_edge_mismatch:candidate",
        expected_backtest_status="unavailable",
    )
    assert_binding_refused(
        "input-edge-removed",
        inputs=[item for item in source_inputs if item.role != "household_source_basis"],
        expected_backtest_status="unavailable",
    )
    assert_binding_refused(
        "input-edge-mismatched",
        inputs=replace_input_edge(
            source_inputs,
            source_basis_edge,
            source_basis_edge.model_copy(update={"artifact_id": panel_edge.artifact_id}),
        ),
        expected_backtest_status="unavailable",
    )
    assert_binding_refused(
        "input-edge-duplicated",
        inputs=[*source_inputs, source_basis_edge],
        expected_backtest_status="unavailable",
    )
    basis_provenance = source_json_snapshot_reads["scientist.d3.household_candidate_basis"]
    missing_source_id = "sha256:" + "f" * 64
    missing_profile_id = "sha256:" + "e" * 64
    missing_source_ref = basis_provenance.artifact_ref.model_copy(
        update={
            "artifact_id": missing_source_id,
            "manifest_profile_sha256": missing_profile_id,
        }
    )
    missing_source_reads = dict(source_json_snapshot_reads)
    missing_source_reads["scientist.d3.household_candidate_basis"] = basis_provenance.model_copy(
        update={
            "artifact_ref": missing_source_ref,
            "selected_artifact_id": missing_source_id,
            "selected_manifest_profile_sha256": missing_profile_id,
            "content_sha256": "f" * 64,
        }
    )
    assert_binding_refused(
        "source-artifact-removed",
        reads=missing_source_reads,
        inputs=replace_input_edge(
            source_inputs,
            source_basis_edge,
            source_basis_edge.model_copy(
                update={
                    "artifact_id": missing_source_ref.artifact_id,
                    "manifest_profile_sha256": missing_profile_id,
                }
            ),
        ),
        expected_backtest_status="unavailable",
    )
    foreign_profile_ref = store.put_bytes(
        store.get_bytes(basis_provenance.artifact_ref),
        PutOptions(
            kind=basis_provenance.artifact_kind,
            media_type="application/json",
            schema=SchemaInfo(name="test.foreign_source_profile", version="1.0"),
        ),
        return_selected_profile=True,
    )
    assert foreign_profile_ref.artifact_id == source_basis_edge.artifact_id
    assert (
        foreign_profile_ref.manifest_profile_sha256
        != basis_provenance.selected_manifest_profile_sha256
    )
    assert_binding_refused(
        "input-edge-foreign-profile",
        inputs=replace_input_profile(
            source_inputs,
            source_basis_edge,
            foreign_profile_ref.manifest_profile_sha256,
        ),
        expected_backtest_status="unavailable",
    )
    assert (
        split_edge.manifest_profile_sha256
        == source_json_snapshot_reads[
            "scientist.d4.calibration_splits"
        ].selected_manifest_profile_sha256
    )
    foreign_contract_reads = dict(source_json_snapshot_reads)
    foreign_contract_reads["scientist.d3.household_candidate_basis"] = basis_provenance.model_copy(
        update={"consumer_contract": "scientist.d4.governance_request"}
    )
    assert_calibration_bundle_parse_refused(
        "provenance-foreign-contract",
        reads=foreign_contract_reads,
        expected_error="source JSON profile key differs from its consumer contract",
    )
    foreign_profile_reads = dict(source_json_snapshot_reads)
    foreign_profile_reads["scientist.d3.household_candidate_basis"] = basis_provenance.model_copy(
        update={
            "artifact_ref": foreign_profile_ref,
            "selected_manifest_profile_sha256": foreign_profile_ref.manifest_profile_sha256,
        }
    )
    assert_binding_refused("provenance-foreign-profile", reads=foreign_profile_reads)
    unknown_profile_reads = dict(source_json_snapshot_reads)
    unknown_profile_reads["scientist.d3.household_candidate_basis"] = basis_provenance.model_copy(
        update={
            "profile_status": "declared_unknown_candidate",
            "schema_validation_provenance": "not_evaluated",
            "source_materialization": "raw_only_candidate",
        }
    )
    assert_calibration_bundle_parse_refused(
        "provenance-unknown-profile",
        reads=unknown_profile_reads,
        expected_error="unknown-profile JSON remains raw-only and cannot feed C5b",
    )

    candidate_b_ref = store.put_json(
        {"candidate": "test-owned-B"},
        PutOptions(kind="scientist.calibration_candidate", media_type="application/json"),
        return_selected_profile=True,
    )
    candidate_b_artifact_ref = ArtifactRef.model_validate(candidate_b_ref.model_dump(mode="python"))
    candidate_b_input_ref = CoreInputRef(
        artifact_id=candidate_b_ref.artifact_id,
        role="candidate",
        manifest_profile_sha256=candidate_b_ref.manifest_profile_sha256,
    )
    report_for_candidate_b_ref = persist_backtest_report(
        _ensure_ir_artifact_store(store),
        report,
        inputs=[candidate_b_input_ref, *source_refs],
    )
    assert report_for_candidate_b_ref.artifact_id == report_ref.artifact_id
    assert report_for_candidate_b_ref.manifest_profile_sha256 != report_ref.manifest_profile_sha256
    core_report_for_candidate_b_ref = ArtifactRef.model_validate(
        report_for_candidate_b_ref.model_dump(mode="python")
    )
    assert store.get_bytes(core_report_for_candidate_b_ref) == store.get_bytes(core_report_ref)
    candidate_b_inputs = list(source_inputs)
    assert_binding_refused(
        "typed-candidate-A-report-candidate-B",
        inputs=candidate_b_inputs,
        candidate_report_ref=report_for_candidate_b_ref,
        expected_reason="candidate_source_input_edge_mismatch:candidate",
        expected_backtest_status="unavailable",
    )
    assert_binding_refused(
        "typed-candidate-B-both-edges-A",
        inputs=source_inputs,
        candidate_report_ref=report_ref,
        candidate_ref_for_bundle=candidate_b_artifact_ref,
        expected_reason="candidate_source_candidate_reference_mismatch",
        expected_backtest_status="unavailable",
    )

    nonexistent_candidate_profile = "sha256:" + "c" * 64
    candidate_ref_with_nonexistent_profile = candidate_artifact_ref.model_copy(
        update={"manifest_profile_sha256": nonexistent_candidate_profile}
    )
    candidate_edge_with_nonexistent_profile = candidate_edge.model_copy(
        update={"manifest_profile_sha256": nonexistent_candidate_profile}
    )
    report_with_nonexistent_candidate_profile_ref = persist_backtest_report(
        _ensure_ir_artifact_store(store),
        report,
        inputs=[candidate_edge_with_nonexistent_profile, *source_refs],
    )
    assert report_with_nonexistent_candidate_profile_ref.artifact_id == report_ref.artifact_id
    core_report_with_nonexistent_candidate_profile_ref = ArtifactRef.model_validate(
        report_with_nonexistent_candidate_profile_ref.model_dump(mode="python")
    )
    assert (
        core_report_with_nonexistent_candidate_profile_ref.manifest_profile_sha256
        == report_with_nonexistent_candidate_profile_ref.manifest_profile_sha256
    )
    assert store.get_bytes(core_report_with_nonexistent_candidate_profile_ref) == store.get_bytes(
        core_report_ref
    )
    assert_binding_refused(
        "candidate-same-id-nonexistent-profile",
        inputs=replace_input_profile(
            source_inputs,
            candidate_edge,
            nonexistent_candidate_profile,
        ),
        candidate_report_ref=report_with_nonexistent_candidate_profile_ref,
        candidate_ref_for_bundle=candidate_ref_with_nonexistent_profile,
        expected_reason="candidate_source_manifest_profile_unavailable:candidate",
        expected_backtest_status="unavailable",
    )

    foreign_report_refs = []

    def assert_report_source_profile_refused(source_role):
        source_input = next(item for item in source_refs if item.role == source_role)
        source_bytes = store.get_bytes(source_input.artifact_id)
        foreign_source_ref = store.put_bytes(
            source_bytes,
            PutOptions(
                kind="data_forge.ukraine.stage_output_snapshot",
                media_type="application/json",
                schema=SchemaInfo(name=f"test.foreign_{source_role}_view", version="1.0"),
            ),
            return_selected_profile=True,
        )
        assert foreign_source_ref.artifact_id == source_input.artifact_id
        assert foreign_source_ref.manifest_profile_sha256 != source_input.manifest_profile_sha256
        altered_report_inputs = replace_input_profile(
            [candidate_input_ref, *source_refs],
            source_input,
            foreign_source_ref.manifest_profile_sha256,
        )
        altered_report_ref = persist_backtest_report(
            _ensure_ir_artifact_store(store),
            report,
            inputs=altered_report_inputs,
        )
        assert altered_report_ref.artifact_id == report_ref.artifact_id
        assert altered_report_ref.manifest_profile_sha256 != report_ref.manifest_profile_sha256
        foreign_report_refs.append(altered_report_ref)
        core_altered_report_ref = ArtifactRef.model_validate(
            altered_report_ref.model_dump(mode="python")
        )
        assert store.get_bytes(core_altered_report_ref) == store.get_bytes(core_report_ref)
        assert (
            store.get_manifest(core_altered_report_ref).artifact_schema
            == store.get_manifest(core_report_ref).artifact_schema
        )

        altered_bundle = fresh.model_copy(
            update={
                "run_id": f"s1-nested-report-edge-{source_role}",
                "backtest_matrix": fresh.backtest_matrix.model_copy(
                    update={"backtest_report_ref": altered_report_ref}
                ),
            }
        )
        altered_inputs = list(source_inputs)
        altered_bundle_ref = persist_calibration_validation_bundle(
            store,
            altered_bundle,
            inputs=altered_inputs,
        )
        altered_fresh = load_calibration_validation_bundle(store, altered_bundle_ref)
        altered_summary = altered_fresh.readout_summary()
        assert altered_summary["source_json_snapshot_binding_status"] == "unavailable"
        assert altered_summary["source_json_snapshot_binding_reason"] == (
            f"candidate_source_input_edge_mismatch:{source_role}"
        )
        assert altered_summary["backtest_report_status"] == "unavailable"
        assert altered_summary["backtest_report_ref"] == str(report_ref.artifact_id)
        assert altered_summary["backtest_metric_diagnostics_status"] == "unavailable"
        assert altered_summary["backtest_metric_diagnostics"] is None
        assert altered_summary["eligible_for_promotion"] is False

        direct_section = _build_calibration_validation_section(
            ctx,
            {
                ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF: ArtifactRef(
                    artifact_id=altered_bundle_ref.artifact_id,
                    kind="scientist.calibration_validation_bundle",
                    media_type="application/json",
                    manifest_profile_sha256=altered_bundle_ref.manifest_profile_sha256,
                ),
                ARTIFACT_BACKTEST_REPORT_REF: ArtifactRef(
                    artifact_id=altered_report_ref.artifact_id,
                    kind="ir.backtest_report",
                    media_type="application/json",
                    manifest_profile_sha256=altered_report_ref.manifest_profile_sha256,
                ),
            },
        )
        assert direct_section is not None
        assert direct_section["source_json_snapshot_binding_status"] == "unavailable"
        assert direct_section["backtest_report_status"] == "unavailable"
        assert direct_section["backtest_metric_diagnostics_status"] == "unavailable"
        assert direct_section["backtest_metric_diagnostics"] is None
        assert direct_section["summary"]["eligible_for_promotion"] is False

        packet = packet_for_bundle(altered_bundle_ref, altered_report_ref)
        direct = packet["backtest"]
        nested = packet["calibration_validation"]
        assert direct["report_ref"] == str(report_ref.artifact_id)
        assert direct["backtest_report_status"] == "unavailable"
        assert direct["metric_diagnostics_status"] == "unavailable"
        assert direct["metric_diagnostics"] is None
        assert direct["source_json_snapshot_binding_status"] == "unavailable"
        assert direct["trust_eligible"] is False
        assert nested["backtest_report_status"] == "unavailable"
        assert nested["source_json_snapshot_binding_status"] == "unavailable"
        assert nested["backtest_metric_diagnostics_status"] == "unavailable"
        assert nested["backtest_metric_diagnostics"] is None
        assert nested["summary"]["eligible_for_promotion"] is False

    for source_role in (
        "household_candidate_panel",
        "household_source_basis",
        "selected_split_manifest",
        "controlled_extension_source",
    ):
        assert_report_source_profile_refused(source_role)

    duplicate_source_edges = controlled_extension_source_edges
    assert len(duplicate_source_edges) == 2
    duplicate_source, untouched_duplicate_source = duplicate_source_edges
    assert duplicate_source.artifact_id != untouched_duplicate_source.artifact_id
    foreign_duplicate_profile = store.put_bytes(
        store.get_bytes(duplicate_source.artifact_id),
        PutOptions(
            kind="data_forge.ukraine.stage_output_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="test.foreign_single_duplicate_view", version="1.0"),
        ),
        return_selected_profile=True,
    )
    assert foreign_duplicate_profile.artifact_id == duplicate_source.artifact_id
    assert (
        foreign_duplicate_profile.manifest_profile_sha256
        != duplicate_source.manifest_profile_sha256
    )
    base_duplicate_report_inputs = [candidate_input_ref, *source_refs]
    altered_duplicate_report_inputs = replace_input_profile(
        base_duplicate_report_inputs,
        duplicate_source,
        foreign_duplicate_profile.manifest_profile_sha256,
    )
    altered_duplicate_source_edges = [
        item
        for item in altered_duplicate_report_inputs
        if item.role == "controlled_extension_source"
    ]
    assert len(altered_duplicate_source_edges) == 2
    assert (
        sum(
            item.artifact_id == duplicate_source.artifact_id
            and item.manifest_profile_sha256 == foreign_duplicate_profile.manifest_profile_sha256
            for item in altered_duplicate_source_edges
        )
        == 1
    )
    assert (
        sum(
            item.artifact_id == untouched_duplicate_source.artifact_id
            and item.manifest_profile_sha256 == untouched_duplicate_source.manifest_profile_sha256
            for item in altered_duplicate_source_edges
        )
        == 1
    )
    altered_duplicate_report_ref = persist_backtest_report(
        _ensure_ir_artifact_store(store), report, inputs=altered_duplicate_report_inputs
    )
    assert altered_duplicate_report_ref.artifact_id == report_ref.artifact_id
    core_altered_duplicate_report_ref = ArtifactRef.model_validate(
        altered_duplicate_report_ref.model_dump(mode="python")
    )
    assert store.get_bytes(core_altered_duplicate_report_ref) == store.get_bytes(core_report_ref)
    assert_binding_refused(
        "one-position-in-repeated-role",
        inputs=source_inputs,
        candidate_report_ref=altered_duplicate_report_ref,
        expected_reason="candidate_source_input_edge_mismatch:controlled_extension_source",
        expected_backtest_status="unavailable",
    )

    # Matching profile strings on both persisted edges are still only declarations
    # until the selected CAS view resolves for that exact artifact ID.
    extension_edge = next(
        item for item in source_refs if item.role == "controlled_extension_source"
    )
    nonexistent_profile = "sha256:" + "d" * 64
    assert nonexistent_profile != extension_edge.manifest_profile_sha256
    falsely_profiled_report_inputs = replace_role_profiles(
        [candidate_input_ref, *source_refs],
        "controlled_extension_source",
        nonexistent_profile,
    )
    falsely_profiled_report_ref = persist_backtest_report(
        _ensure_ir_artifact_store(store),
        report,
        inputs=falsely_profiled_report_inputs,
    )
    assert falsely_profiled_report_ref.artifact_id == report_ref.artifact_id
    falsely_profiled_c5b_inputs = replace_role_profiles(
        source_inputs,
        "controlled_extension_source",
        nonexistent_profile,
    )
    assert_binding_refused(
        "same-nonexistent-profile-on-both-edges",
        inputs=falsely_profiled_c5b_inputs,
        expected_reason=(
            "candidate_source_manifest_profile_unavailable:controlled_extension_source"
        ),
        candidate_report_ref=falsely_profiled_report_ref,
        expected_backtest_status="unavailable",
    )

    direct_profile_mismatch_packet = packet_for_bundle(bundle_ref, foreign_report_refs[0])
    mismatched_direct = direct_profile_mismatch_packet["backtest"]
    mismatched_nested = direct_profile_mismatch_packet["calibration_validation"]
    assert mismatched_direct["backtest_report_status"] == "unavailable"
    assert mismatched_direct["metric_diagnostics_status"] == "unavailable"
    assert mismatched_direct["metric_diagnostics"] is None
    assert mismatched_direct["trust_eligible"] is False
    assert mismatched_nested["backtest_report_status"] == "unavailable"
    assert mismatched_nested["backtest_metric_diagnostics_status"] == "unavailable"
    assert mismatched_nested["backtest_metric_diagnostics"] is None
    assert mismatched_nested["source_json_snapshot_binding_status"] == "unavailable"
    assert mismatched_nested["summary"]["eligible_for_promotion"] is False

    # The provenance producer can recompute a caller-selected generic model.
    # C5b must re-run each registered source model over the selected CAS bytes.
    for source_role, contract in source_contract_by_role.items():
        wrong_payload = json.dumps({"source_role": source_role}, separators=(",", ":")).encode(
            "utf-8"
        )
        wrong_ref = store.put_bytes(
            wrong_payload,
            PutOptions(
                kind="data_forge.ukraine.stage_output_snapshot",
                media_type="application/json",
            ),
            return_selected_profile=True,
        )
        caller_selected_read = read_ukraine_json_snapshot(
            store,
            wrong_ref,
            raw_payload_bytes=wrong_payload,
            expected_sha256=hashlib.sha256(wrong_payload).hexdigest(),
            expected_size_bytes=len(wrong_payload),
            expected_kind="data_forge.ukraine.stage_output_snapshot",
            consumer_contract=contract,
            model_type=dict[str, str],
        )
        assert caller_selected_read.provenance.schema_validation_provenance == "recomputed"
        assert (
            caller_selected_read.provenance.profile_status
            == "profile_absent_raw_snapshot_candidate"
        )
        wrong_edge = CoreInputRef(
            artifact_id=wrong_ref.artifact_id,
            role=source_role,
            manifest_profile_sha256=wrong_ref.manifest_profile_sha256,
        )
        source_input = next(item for item in source_refs if item.role == source_role)
        wrong_source_refs = replace_input_edge(source_refs, source_input, wrong_edge)
        wrong_report_ref = persist_backtest_report(
            _ensure_ir_artifact_store(store),
            report,
            inputs=[candidate_input_ref, *wrong_source_refs],
        )
        wrong_reads = dict(source_json_snapshot_reads)
        wrong_reads[contract] = caller_selected_read.provenance
        bundle_source_input = next(item for item in source_inputs if item.role == source_role)
        wrong_c5b_inputs = replace_input_edge(source_inputs, bundle_source_input, wrong_edge)
        assert_binding_refused(
            f"source-contract-shape-mismatch-{source_role}",
            reads=wrong_reads,
            inputs=wrong_c5b_inputs,
            candidate_report_ref=wrong_report_ref,
            expected_reason=f"source_json_snapshot_contract_validation_failed:{contract}",
        )

    unregistered_reads = dict(source_json_snapshot_reads)
    unregistered_contract = "scientist.d3.unregistered_snapshot_contract"
    unregistered_reads[unregistered_contract] = source_json_snapshot_reads[
        "scientist.d3.household_candidate_basis"
    ].model_copy(update={"consumer_contract": unregistered_contract})
    assert_calibration_bundle_parse_refused(
        "unregistered-source-contract",
        reads=unregistered_reads,
        expected_error="source JSON profile reads do not match the purpose contract set",
    )

    legacy_report = report.model_copy(update={"report_id": "s1-nested-legacy-profileless-report"})
    legacy_report_inputs = [
        candidate_input_ref.model_copy(update={"manifest_profile_sha256": None}),
        *[item.model_copy(update={"manifest_profile_sha256": None}) for item in source_refs],
    ]
    persisted_legacy_report_ref = persist_backtest_report(
        _ensure_ir_artifact_store(store),
        legacy_report,
        inputs=legacy_report_inputs,
    )
    legacy_report_ref = persisted_legacy_report_ref.model_copy(
        update={"manifest_profile_sha256": None}
    )
    legacy_bundle = fresh.model_copy(
        update={
            "run_id": "s1-nested-legacy-profileless-c5b",
            "schema_version": "1.0",
            "candidate_ref": candidate_artifact_ref.model_copy(
                update={"manifest_profile_sha256": None}
            ),
            "source_json_snapshot_reads": {},
            "backtest_matrix": fresh.backtest_matrix.model_copy(
                update={"backtest_report_ref": legacy_report_ref}
            ),
        }
    )
    legacy_inputs = [
        item.model_copy(update={"manifest_profile_sha256": None}) for item in source_inputs
    ]
    legacy_bundle_ref = persist_calibration_validation_bundle(
        store,
        legacy_bundle,
        inputs=legacy_inputs,
    )
    legacy_fresh = load_calibration_validation_bundle(store, legacy_bundle_ref)
    legacy_summary = legacy_fresh.readout_summary()
    assert store.get_manifest(legacy_bundle_ref).artifact_schema.version == "1.0"
    assert legacy_summary["source_json_snapshot_binding_status"] == "not_established"
    assert legacy_summary["backtest_report_status"] == "available"
    assert legacy_summary["backtest_metric_diagnostics_status"] == "unavailable"
    assert legacy_summary["backtest_metric_diagnostics"] is None
    assert legacy_summary["eligible_for_promotion"] is False
    legacy_packet = packet_for_bundle(legacy_bundle_ref, legacy_report_ref)
    assert legacy_packet["backtest"]["source_json_snapshot_binding_status"] == "not_established"
    assert legacy_packet["backtest"]["metric_diagnostics"] is None
    assert (
        legacy_packet["calibration_validation"]["source_json_snapshot_binding_status"]
        == "not_established"
    )
    assert legacy_packet["calibration_validation"]["backtest_metric_diagnostics"] is None
    assert legacy_packet["calibration_validation"]["summary"]["eligible_for_promotion"] is False


def test_s1_c5b_fresh_backtest_binding_reaches_packet_and_rejects_kept_markers(
    tmp_path, monkeypatch
) -> None:
    from collections import Counter

    import pytest

    from polisyos.core.contracts.backtest import BacktestReportRef
    from polisyos.ir.analytics.backtest import load_backtest_report
    from polisyos.ir.artifacts import put_json_artifact
    from polisyos.ir.model_layer.canon import CanonSpec as IRCanonSpec
    from polisyos.ir.observation.bundles import BacktestPlanBundle, ContractCompatibilityTarget
    from polisyos.scientist.governance.calibration import CalibrationGovernanceReport
    from polisyos.scientist.governance.calibration_validation import (
        CalibrationValidationRunner,
        CalibrationValidationRunnerInput,
        load_calibration_validation_bundle,
    )
    from polisyos.scientist.methods.backtesting.plan import (
        HistoricalValidationPlan,
        PredictionSource,
    )

    pytest.importorskip("scipy.stats")
    store = FileSystemCAS(tmp_path / "cas")
    history = tmp_path / "history.json"
    history.write_text('{"metric":[100,100,100,100]}', encoding="utf-8")
    roles = ("fixture_training", "fixture_validation", "fixture_holdout")
    plan = HistoricalValidationPlan(
        plan_id="s1-packet-plan",
        historical_data_path=str(history),
        ground_truth_outcomes={"metric": [99.5, 98.5, 97.5]},
        target_metrics=["metric"],
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"metric": [100, 100, 100]},
        selected_training_role=roles[0],
        selected_validation_role=roles[1],
        selected_holdout_role=roles[2],
        metadata={
            "selected_training_role": roles[0],
            "selected_validation_role": roles[1],
            "selected_holdout_role": roles[2],
        },
    )
    bundle = BacktestPlanBundle(
        contract_target=ContractCompatibilityTarget(
            contract_id="household_bundle", contract_fqn="polisyos.tests.BacktestPlanBundle"
        ),
        required_fields=["metric"],
        holdout_windows=["2025-01-01::2025-12-31"],
        selected_training_role=roles[0],
        selected_validation_role=roles[1],
        selected_holdout_role=roles[2],
        plans=[plan.model_dump(mode="json")],
    )
    candidate = store.put_json(
        {"candidate": "test-owned"},
        PutOptions(kind="scientist.calibration_candidate", media_type="application/json"),
    )
    result = CalibrationValidationRunner(store).run(
        CalibrationValidationRunnerInput(
            run_id="s1-packet",
            candidate_ref=candidate,
            governance_report=CalibrationGovernanceReport(verdict="human_gate", metadata={}),
            backtest_plan_bundles={BacktestKind.HOUSEHOLD: bundle},
            selected_training_role=roles[0],
            selected_validation_role=roles[1],
            selected_holdout_role=roles[2],
        )
    )
    fresh = load_calibration_validation_bundle(store, result.bundle_ref)
    report_ref = fresh.backtest_report_ref
    assert report_ref is not None
    report = load_backtest_report(_ensure_ir_artifact_store(store), report_ref)
    report_manifest = store.get_manifest(report_ref)
    report_schema = report_manifest.artifact_schema
    assert report_manifest.kind == "ir.backtest_report"
    assert report_manifest.media_type == "application/json"
    assert report_schema is not None

    def manifest_input_identity(item):
        return item.role, str(item.artifact_id), item.manifest_profile_sha256

    expected_report_inputs = Counter(map(manifest_input_identity, report_manifest.inputs))

    def persist_report_payload_variant(payload):
        ref_payload = put_json_artifact(
            _ensure_ir_artifact_store(store),
            payload,
            kind=report_manifest.kind,
            schema_name=report_schema.name,
            schema_version=report_schema.version,
            inputs=report_manifest.inputs,
            canon_spec=IRCanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        variant_ref = BacktestReportRef.model_validate(ref_payload)
        assert variant_ref.manifest_profile_sha256 is not None
        variant_manifest = store.get_manifest(variant_ref)
        assert variant_manifest.kind == report_manifest.kind
        assert variant_manifest.media_type == report_manifest.media_type
        assert variant_manifest.artifact_schema == report_schema
        assert (
            Counter(map(manifest_input_identity, variant_manifest.inputs)) == expected_report_inputs
        )
        return variant_ref

    readout = fresh.readout_summary()
    assert (
        readout["backtest_report_status"] == "available"
        and readout["backtest_metric_diagnostics_status"] == "computed"
    )
    assert (
        readout["selected_training_role"] == roles[0]
        and readout["selected_validation_role"] == roles[1]
    )
    assert (
        readout["selected_holdout_role"] == roles[2] and readout["eligible_for_promotion"] is False
    )
    assert report.overall_bias_direction.value == "unknown" and report.trust_eligible is False
    actual_diagnostic = next(
        item for item in report.metric_diagnostics if item.metric_name == "metric"
    )
    assert (
        actual_diagnostic.method_id == "scipy.stats.ttest_1samp"
        and actual_diagnostic.backend_version
    )
    assert actual_diagnostic.p_value == pytest.approx(0.121690, abs=1e-6)
    edges = [
        x
        for x in store.get_manifest(result.bundle_ref.artifact_id).inputs
        if x.role == "backtest_report"
    ]
    assert len(edges) == 1
    assert (
        str(edges[0].artifact_id),
        edges[0].manifest_profile_sha256,
    ) == (
        str(report_ref.artifact_id),
        report_ref.manifest_profile_sha256,
    )
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="s1-packet")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.s1"))
    trinity = _persist_trinity_bundle(store, {"trinity": {}})
    data = _persist_data_snapshot(store)
    c5b = ArtifactRef(
        artifact_id=str(result.bundle_ref.artifact_id),
        kind="scientist.calibration_validation_bundle",
        media_type="application/json",
        manifest_profile_sha256=result.bundle_ref.manifest_profile_sha256,
    )
    btref = ArtifactRef(
        artifact_id=str(report_ref.artifact_id),
        kind="ir.backtest_report",
        media_type="application/json",
        manifest_profile_sha256=report_ref.manifest_profile_sha256,
    )
    state = ExperimentState(
        run_id="s1-packet",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity,
            INPUT_REGISTRY_BUNDLE_REF: registry,
            INPUT_DATA_SNAPSHOT_REF: data,
        },
        artifacts_index={
            ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF: c5b,
            ARTIFACT_BACKTEST_REPORT_REF: btref,
        },
    )
    bundle_manifest = store.get_manifest(result.bundle_ref)
    bundle_schema = bundle_manifest.artifact_schema
    assert bundle_manifest.kind == "scientist.calibration_validation_bundle"
    assert bundle_manifest.media_type == "application/json"
    assert bundle_schema is not None
    base_report_edge_identity = (
        "backtest_report",
        str(report_ref.artifact_id),
        report_ref.manifest_profile_sha256,
    )
    base_report_edges = [
        item
        for item in bundle_manifest.inputs
        if manifest_input_identity(item) == base_report_edge_identity
    ]
    assert len(base_report_edges) == 1
    bundle_source_inputs = list(bundle_manifest.inputs)
    bundle_source_inputs.remove(base_report_edges[0])
    expected_bundle_source_inputs = Counter(map(manifest_input_identity, bundle_source_inputs))

    def persist_bundle_variant(bundle_variant):
        nested_report_ref = bundle_variant.backtest_report_ref
        assert nested_report_ref is not None
        variant_ref = persist_calibration_validation_bundle(
            store,
            bundle_variant,
            inputs=bundle_source_inputs,
        )
        variant_manifest = store.get_manifest(variant_ref)
        assert variant_manifest.kind == bundle_manifest.kind
        assert variant_manifest.media_type == bundle_manifest.media_type
        assert variant_manifest.artifact_schema == bundle_schema
        structural_identity = (
            "backtest_report",
            str(nested_report_ref.artifact_id),
            nested_report_ref.manifest_profile_sha256,
        )
        structural_edges = [
            item
            for item in variant_manifest.inputs
            if manifest_input_identity(item) == structural_identity
        ]
        assert len(structural_edges) == 1
        nonstructural_inputs = list(variant_manifest.inputs)
        nonstructural_inputs.remove(structural_edges[0])
        assert Counter(map(manifest_input_identity, nonstructural_inputs)) == (
            expected_bundle_source_inputs
        )
        return variant_ref

    packet_ref = BuildDecisionPacketNode().execute(ctx, state).artifacts[0]
    packet = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    assert (
        packet["backtest"]["report_ref"] == packet["calibration_validation"]["backtest_report_ref"]
    )
    assert (
        packet["backtest"]["metric_diagnostics"]
        == packet["calibration_validation"]["backtest_metric_diagnostics"]
    )
    assert packet["calibration_validation"]["summary"]["eligible_for_promotion"] is False
    packet_diagnostic = packet["calibration_validation"]["backtest_metric_diagnostics"][0]
    assert packet_diagnostic["method_id"] == "scipy.stats.ttest_1samp" and packet_diagnostic[
        "p_value"
    ] == pytest.approx(0.121690, abs=1e-6)

    def packet_with_report(candidate_report_ref, run_suffix):
        matrix = fresh.backtest_matrix.model_copy(
            update={"backtest_report_ref": candidate_report_ref}
        )
        candidate_bundle = fresh.model_copy(
            update={"run_id": f"s1-packet-{run_suffix}", "backtest_matrix": matrix}
        )
        candidate_bundle_ref = persist_bundle_variant(candidate_bundle)
        candidate_state = state.model_copy(
            update={
                "artifacts_index": {
                    **state.artifacts_index,
                    ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF: ArtifactRef(
                        artifact_id=str(candidate_bundle_ref.artifact_id),
                        kind="scientist.calibration_validation_bundle",
                        media_type="application/json",
                        manifest_profile_sha256=candidate_bundle_ref.manifest_profile_sha256,
                    ),
                    ARTIFACT_BACKTEST_REPORT_REF: ArtifactRef(
                        artifact_id=str(candidate_report_ref.artifact_id),
                        kind="ir.backtest_report",
                        media_type="application/json",
                        manifest_profile_sha256=candidate_report_ref.manifest_profile_sha256,
                    ),
                }
            }
        )
        candidate_packet_ref = BuildDecisionPacketNode().execute(ctx, candidate_state).artifacts[0]
        return from_canonical_bytes(store.get_bytes(candidate_packet_ref.artifact_id))

    def assert_residuals_survive_statistical_refusal(run_suffix, mutate):
        payload = report.model_dump(mode="json")
        mutate(payload)
        mutated_ref = persist_report_payload_variant(payload)
        observed = packet_with_report(mutated_ref, run_suffix)
        direct = observed["backtest"]
        nested = observed["calibration_validation"]
        diagnostic = direct["metric_diagnostics"][0]
        nested_diagnostic = nested["backtest_metric_diagnostics"][0]
        assert direct["backtest_report_status"] == "available"
        assert direct["metric_diagnostics_status"] == "unavailable"
        assert diagnostic["status"] == "unavailable"
        assert diagnostic["mean_residual"] == pytest.approx(1.5)
        assert diagnostic["p_value"] is None
        assert diagnostic["reason"] == "scipy_ttest_1samp_fresh_recompute_mismatch"
        assert nested["backtest_report_status"] == "available"
        assert nested["backtest_metric_diagnostics_status"] == "unavailable"
        assert nested_diagnostic == diagnostic
        assert nested["summary"]["eligible_for_promotion"] is False
        assert direct["trust_eligible"] is False
        assert direct["trust_score"] is None
        assert all(bias["p_value"] is None for bias in direct["detected_biases"])

    assert_residuals_survive_statistical_refusal(
        "p-only-forgery",
        lambda payload: payload["metric_diagnostics"][0].update({"p_value": 0.009375}),
    )
    assert_residuals_survive_statistical_refusal(
        "backend-version-forgery",
        lambda payload: payload["metric_diagnostics"][0].update(
            {"backend_version": "forged-version"}
        ),
    )
    assert_residuals_survive_statistical_refusal(
        "bias-p-only-forgery",
        lambda payload: payload["detected_biases"][0].update({"p_value": 0.009375}),
    )
    assert_residuals_survive_statistical_refusal(
        "bias-row-removed",
        lambda payload: payload.update({"detected_biases": []}),
    )

    from polisyos.scientist.methods.backtesting.orchestrator import (
        BacktestOrchestrator,
        _TTestResult,
    )

    monkeypatch.setattr(
        BacktestOrchestrator,
        "_two_sided_ttest",
        staticmethod(
            lambda errors: _TTestResult(
                p_value=None,
                test_name=None,
                status="unavailable",
                reason="scipy_ttest_1samp_error:ImportError",
            )
        ),
    )
    unavailable_packet = packet_with_report(btref, "fresh-scipy-unavailable")
    unavailable_direct = unavailable_packet["backtest"]
    unavailable_nested = unavailable_packet["calibration_validation"]
    unavailable_diagnostic = unavailable_direct["metric_diagnostics"][0]
    assert unavailable_direct["metric_diagnostics_status"] == "unavailable"
    assert unavailable_diagnostic["status"] == "unavailable"
    assert unavailable_diagnostic["mean_residual"] == pytest.approx(1.5)
    assert unavailable_diagnostic["p_value"] is None
    assert unavailable_nested["backtest_metric_diagnostics_status"] == "unavailable"
    assert unavailable_nested["backtest_metric_diagnostics"][0] == unavailable_diagnostic
    from pydantic import ValidationError

    from polisyos.ir.analytics.backtest import persist_backtest_report

    first_scenario = report.scenarios[0]
    first_comparison = first_scenario.outcome_comparisons[0]
    assert first_comparison.relative_error is not None and first_comparison.relative_error > 0.0
    changed_comparison = first_comparison.model_copy(
        update={"relative_error": first_comparison.relative_error * 2.0}
    )
    source_mismatch_scenario = first_scenario.model_copy(
        update={
            "outcome_comparisons": [changed_comparison, *first_scenario.outcome_comparisons[1:]],
        }
    )
    source_mismatch_report = report.model_copy(
        update={"scenarios": [source_mismatch_scenario, *report.scenarios[1:]]}
    )
    with pytest.raises(
        ValidationError,
        match="source relative_error does not reconcile with outcome rows",
    ):
        persist_backtest_report(_ensure_ir_artifact_store(store), source_mismatch_report)

    assert actual_diagnostic.mean_residual != 0.0
    mismatched_mean = -actual_diagnostic.mean_residual
    mismatched_sign = (
        "positive" if mismatched_mean > 0 else "negative" if mismatched_mean < 0 else "zero"
    )
    mismatched_diagnostics = [
        item.model_copy(
            update={
                "mean_residual": mismatched_mean,
                "magnitude": abs(mismatched_mean),
                "residual_sign": mismatched_sign,
            }
        )
        if item.metric_name == actual_diagnostic.metric_name
        else item
        for item in report.metric_diagnostics
    ]
    stale_diagnostic_report = report.model_copy(
        update={"metric_diagnostics": mismatched_diagnostics}
    )
    with pytest.raises(
        ValidationError,
        match="metric diagnostic does not reconcile source count/mean",
    ):
        persist_backtest_report(_ensure_ir_artifact_store(store), stale_diagnostic_report)

    legacy_ref = persist_report_payload_variant(
        {
            "schema_version": "1.0",
            "report_id": "legacy-unbound-trust-marker",
            "trust_eligible": True,
            "trust_score": 0.99,
            "trust_grade": "A",
            "degraded": False,
            "overall_bias_direction": "neutral",
        }
    )
    legacy_packet = packet_with_report(legacy_ref, "legacy")
    assert legacy_packet["backtest"]["metric_diagnostics_status"] == "unavailable"
    assert legacy_packet["backtest"]["metric_diagnostics"] is None
    assert legacy_packet["backtest"]["trust_eligible"] is False
    assert (
        legacy_packet["backtest"]["trust_score"] is None
        and legacy_packet["backtest"]["trust_grade"] is None
    )
    assert (
        legacy_packet["calibration_validation"]["backtest_metric_diagnostics_status"]
        == "unavailable"
    )
    assert legacy_packet["calibration_validation"]["summary"]["eligible_for_promotion"] is False

    forged_payload = report.model_dump(mode="json")
    for diagnostic in forged_payload["metric_diagnostics"]:
        diagnostic.update(
            {
                "status": "exact_zero",
                "n": len(
                    next(
                        s
                        for s in report.scenarios
                        if any(
                            c.metric_name == diagnostic["metric_name"]
                            for c in s.outcome_comparisons
                        )
                    ).outcome_comparisons
                ),
                "mean_residual": 0.0,
                "magnitude": 0.0,
                "residual_sign": "zero",
                "direction_status": "not_applicable",
                "method_id": None,
                "backend_id": None,
                "backend_version": None,
                "statistic": None,
                "p_value": None,
                "reason": None,
                "unresolved_assumptions": [
                    "residual_independence",
                    "multiplicity_policy",
                    "population_scope",
                ],
            }
        )
    forged_payload.update(
        {
            "overall_bias_direction": "neutral",
            "trust_eligible": True,
            "trust_score": 0.99,
            "trust_grade": "A",
            "degraded": False,
            "degraded_reasons": [],
            "detected_biases": [],
        }
    )
    forged_ref = persist_report_payload_variant(forged_payload)
    forged_packet = packet_with_report(forged_ref, "forged-zero-marker")
    assert forged_packet["backtest"]["backtest_report_status"] == "unavailable"
    assert forged_packet["backtest"]["metric_diagnostics_status"] == "unavailable"
    assert forged_packet["backtest"]["metric_diagnostics"] is None
    assert forged_packet["backtest"]["trust_eligible"] is False
    assert (
        forged_packet["backtest"]["trust_score"] is None
        and forged_packet["backtest"]["trust_grade"] is None
    )
    assert forged_packet["calibration_validation"]["backtest_report_status"] == "unavailable"
    assert (
        forged_packet["calibration_validation"]["backtest_metric_diagnostics_status"]
        == "unavailable"
    )
    assert forged_packet["calibration_validation"]["summary"]["eligible_for_promotion"] is False
    malformed_payload = report.model_dump(mode="json")
    malformed_payload.update(
        {
            "report_id": "malformed-kept-marker",
            "metric_diagnostics": [
                {
                    "metric_name": "metric",
                    "status": "available",
                    "n": 3,
                    "mean_residual": 10.0,
                    "magnitude": 10.0,
                    "residual_sign": "positive",
                    "direction_status": "not_established",
                }
            ],
            "trust_eligible": True,
            "degraded": False,
            "overall_bias_direction": "neutral",
        }
    )
    malformed_ref = persist_report_payload_variant(malformed_payload)
    mismatch_state = state.model_copy(
        update={
            "artifacts_index": {
                **state.artifacts_index,
                ARTIFACT_BACKTEST_REPORT_REF: ArtifactRef(
                    artifact_id=str(malformed_ref.artifact_id),
                    kind="ir.backtest_report",
                    media_type="application/json",
                    manifest_profile_sha256=malformed_ref.manifest_profile_sha256,
                ),
            }
        }
    )
    mismatch_packet_ref = BuildDecisionPacketNode().execute(ctx, mismatch_state).artifacts[0]
    mismatch_packet = from_canonical_bytes(store.get_bytes(mismatch_packet_ref.artifact_id))
    assert mismatch_packet["backtest"]["backtest_report_status"] == "unavailable"
    assert mismatch_packet["backtest"]["parse_warning"] == "backtest_report_binding_mismatch"
    assert mismatch_packet["backtest"]["metric_diagnostics"] is None
    assert mismatch_packet["calibration_validation"]["backtest_report_status"] == "unavailable"
    assert mismatch_packet["calibration_validation"]["summary"]["eligible_for_promotion"] is False
    bad_ref = malformed_ref
    bad_matrix = fresh.backtest_matrix.model_copy(update={"backtest_report_ref": bad_ref})
    marker = fresh.model_copy(
        update={
            "backtest_matrix": bad_matrix,
            "metadata": {
                **fresh.metadata,
                "nested_backtest_report": {
                    "trust_eligible": True,
                    "degraded": False,
                    "metric_diagnostics": [{"status": "available"}],
                },
            },
        }
    )
    bad_c5b = persist_bundle_variant(marker)
    refused = load_calibration_validation_bundle(store, bad_c5b).readout_summary()
    assert (
        refused["backtest_report_status"] == "unavailable"
        and refused["backtest_metric_diagnostics"] is None
    )
    assert refused["eligible_for_promotion"] is False
    badstate = state.model_copy(
        update={
            "artifacts_index": {
                ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF: ArtifactRef(
                    artifact_id=str(bad_c5b.artifact_id),
                    kind="scientist.calibration_validation_bundle",
                    media_type="application/json",
                    manifest_profile_sha256=bad_c5b.manifest_profile_sha256,
                ),
                ARTIFACT_BACKTEST_REPORT_REF: ArtifactRef(
                    artifact_id=str(malformed_ref.artifact_id),
                    kind="ir.backtest_report",
                    media_type="application/json",
                    manifest_profile_sha256=malformed_ref.manifest_profile_sha256,
                ),
            }
        }
    )
    badpacket_ref = BuildDecisionPacketNode().execute(ctx, badstate).artifacts[0]
    badpacket = from_canonical_bytes(store.get_bytes(badpacket_ref.artifact_id))
    assert badpacket["backtest"]["backtest_report_status"] == "unavailable"
    assert badpacket["backtest"].get("parse_warning") == "backtest_report_parse_failed"
    assert badpacket["calibration_validation"]["status"] == "completed"
    assert badpacket["calibration_validation"]["summary"]["eligible_for_promotion"] is False


def test_s1_exact_zero_arithmetic_is_limited_through_cas_c5b_and_packet(tmp_path) -> None:
    from polisyos.core.artifacts.manifest import InputRef as InputRefModel
    from polisyos.ir.analytics.backtest import load_backtest_report
    from polisyos.ir.observation.bundles import BacktestPlanBundle, ContractCompatibilityTarget
    from polisyos.scientist.governance.backtest_matrix import (
        BacktestKind,
        verify_backtest_diagnostic_projection,
        verify_backtest_trust_projection,
    )
    from polisyos.scientist.governance.calibration import CalibrationGovernanceReport
    from polisyos.scientist.governance.calibration_validation import (
        CalibrationValidationRunner,
        CalibrationValidationRunnerInput,
        load_calibration_validation_bundle,
        persist_calibration_validation_bundle,
    )
    from polisyos.scientist.methods.backtesting.plan import (
        HistoricalValidationPlan,
        PredictionSource,
    )

    store = FileSystemCAS(tmp_path / "s1-exact-zero-cas")
    history = tmp_path / "s1-exact-zero-history.json"
    history.write_text('{"metric":[100,100,100,100]}', encoding="utf-8")
    roles = ("fixture_training", "fixture_validation", "fixture_holdout")
    plan = HistoricalValidationPlan(
        plan_id="s1-exact-zero-plan",
        historical_data_path=str(history),
        ground_truth_outcomes={"metric": [100.0, 100.0, 100.0]},
        target_metrics=["metric"],
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"metric": [100.0, 100.0, 100.0]},
        selected_training_role=roles[0],
        selected_validation_role=roles[1],
        selected_holdout_role=roles[2],
        metadata={
            "selected_training_role": roles[0],
            "selected_validation_role": roles[1],
            "selected_holdout_role": roles[2],
        },
    )
    plan_bundle = BacktestPlanBundle(
        contract_target=ContractCompatibilityTarget(
            contract_id="household_bundle", contract_fqn="polisyos.tests.BacktestPlanBundle"
        ),
        required_fields=["metric"],
        holdout_windows=["2025-01-01::2025-12-31"],
        selected_training_role=roles[0],
        selected_validation_role=roles[1],
        selected_holdout_role=roles[2],
        plans=[plan.model_dump(mode="json")],
    )
    candidate = store.put_json(
        {"candidate": "test-owned"},
        PutOptions(kind="scientist.calibration_candidate", media_type="application/json"),
    )
    result = CalibrationValidationRunner(store).run(
        CalibrationValidationRunnerInput(
            run_id="s1-exact-zero",
            candidate_ref=candidate,
            governance_report=CalibrationGovernanceReport(verdict="human_gate", metadata={}),
            backtest_plan_bundles={BacktestKind.HOUSEHOLD: plan_bundle},
            selected_training_role=roles[0],
            selected_validation_role=roles[1],
            selected_holdout_role=roles[2],
        )
    )
    fresh = load_calibration_validation_bundle(store, result.bundle_ref)
    report_ref = fresh.backtest_report_ref
    assert report_ref is not None
    report = load_backtest_report(_ensure_ir_artifact_store(store), report_ref)
    projection = verify_backtest_trust_projection(report)
    diagnostic = verify_backtest_diagnostic_projection(report)
    assert diagnostic.recomputed and diagnostic.status == "computed"
    assert projection.status == "not_established" and not projection.eligible
    assert projection.score is None and projection.grade is None
    readout = fresh.readout_summary()
    assert readout["backtest_trust_status"] == "not_established"
    assert readout["backtest_trust_score"] is None and readout["backtest_trust_grade"] is None

    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="s1-exact-zero")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.s1"))
    trinity = _persist_trinity_bundle(store, {"trinity": {}})
    data = _persist_data_snapshot(store)
    state = ExperimentState(
        run_id="s1-exact-zero",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity,
            INPUT_REGISTRY_BUNDLE_REF: registry,
            INPUT_DATA_SNAPSHOT_REF: data,
        },
        artifacts_index={
            ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF: ArtifactRef(
                artifact_id=str(result.bundle_ref.artifact_id),
                kind="scientist.calibration_validation_bundle",
                media_type="application/json",
                manifest_profile_sha256=result.bundle_ref.manifest_profile_sha256,
            ),
            ARTIFACT_BACKTEST_REPORT_REF: ArtifactRef(
                artifact_id=str(report_ref.artifact_id),
                kind="ir.backtest_report",
                media_type="application/json",
                manifest_profile_sha256=report_ref.manifest_profile_sha256,
            ),
        },
    )
    packet_ref = BuildDecisionPacketNode().execute(ctx, state).artifacts[0]
    packet = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    assert packet["backtest"]["trust_score_status"] == "not_established"
    assert not packet["backtest"]["trust_eligible"]
    assert packet["backtest"]["trust_score"] is None
    assert packet["calibration_validation"]["summary"]["backtest_trust_status"] == "not_established"
    assert packet["calibration_validation"]["summary"]["backtest_source_reconciliation_status"] == (
        "not_established"
    )
    assert packet["calibration_validation"]["summary"]["eligible_for_promotion"] is False

    report_inputs = [
        InputRefModel(
            artifact_id=x.artifact_id,
            role=x.role,
            manifest_profile_sha256=x.manifest_profile_sha256,
        )
        for x in store.get_manifest(report_ref.artifact_id).inputs
    ]
    bundle_inputs = [
        InputRefModel(
            artifact_id=x.artifact_id,
            role=x.role,
            manifest_profile_sha256=x.manifest_profile_sha256,
        )
        for x in store.get_manifest(result.bundle_ref.artifact_id).inputs
        if x.role != "backtest_report"
    ]
    for field, value in (
        ("trust_score", 0.75),
        ("trust_grade", "B" if projection.grade != "B" else "A"),
        ("trust_eligible", True),
    ):
        changed = report.model_copy(update={field: value})
        changed_ref = persist_backtest_report(
            _ensure_ir_artifact_store(store), changed, inputs=report_inputs
        )
        matrix = fresh.backtest_matrix.model_copy(update={"backtest_report_ref": changed_ref})
        bundle = fresh.model_copy(
            update={"run_id": f"s1-exact-zero-{field}", "backtest_matrix": matrix}
        )
        bundle_ref = persist_calibration_validation_bundle(store, bundle, inputs=bundle_inputs)
        changed_readout = load_calibration_validation_bundle(store, bundle_ref).readout_summary()
        assert changed_readout["backtest_trust_status"] == "not_established"
        assert (
            changed_readout["backtest_trust_score"] is None
            and changed_readout["backtest_trust_grade"] is None
        )
        assert changed_readout["eligible_for_promotion"] is False
        changed_state = state.model_copy(
            update={
                "run_id": f"s1-exact-zero-{field}",
                "artifacts_index": {
                    **state.artifacts_index,
                    ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF: ArtifactRef(
                        artifact_id=str(bundle_ref.artifact_id),
                        kind="scientist.calibration_validation_bundle",
                        media_type="application/json",
                    ),
                    ARTIFACT_BACKTEST_REPORT_REF: ArtifactRef(
                        artifact_id=str(changed_ref.artifact_id),
                        kind="ir.backtest_report",
                        media_type="application/json",
                    ),
                },
            }
        )
        changed_packet_ref = BuildDecisionPacketNode().execute(ctx, changed_state).artifacts[0]
        changed_packet = from_canonical_bytes(store.get_bytes(changed_packet_ref.artifact_id))
        assert changed_packet["backtest"]["trust_score_status"] == "not_established"
        assert changed_packet["backtest"]["trust_eligible"] is False
        assert (
            changed_packet["backtest"]["trust_score"] is None
            and changed_packet["backtest"]["trust_grade"] is None
        )
        assert (
            changed_packet["calibration_validation"]["summary"]["backtest_trust_status"]
            == "not_established"
        )
        assert (
            changed_packet["calibration_validation"]["summary"]["eligible_for_promotion"] is False
        )


def test_trinity_candidate_identity_is_independent_of_run_id_and_refuses_invalid_override(
    tmp_path,
) -> None:
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
        _resolve_candidate as resolve_policy_output_candidate,
    )
    from polisyos.scientist.policy_design.phase3 import (
        _resolve_candidate as resolve_phase3_candidate,
    )

    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    trinity_ref = _persist_trinity_bundle(store)

    for run_id in ("R_Candidate.Case-1", "R_candidate_case-2"):
        run = RunContext.start(
            store=store,
            registry_bundle=registry_bundle,
            run_id=run_id,
        )
        ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(run_id))
        state = ExperimentState(
            run_id=run_id,
            inputs={INPUT_TRINITY_BUNDLE_REF: trinity_ref},
        )
        resolved, resolved_ref = resolve_policy_output_candidate(ctx, state)
        phase3_resolved = resolve_phase3_candidate(ctx, state)
        assert resolved is not None and phase3_resolved is not None
        assert resolved.candidate_id == "decision_packet_fixture_policy"
        assert phase3_resolved.candidate_id == resolved.candidate_id
        assert (
            str(resolved_ref.artifact_id),
            resolved_ref.kind,
            resolved_ref.media_type,
            resolved_ref.manifest_profile_sha256,
        ) == (
            str(trinity_ref.artifact_id),
            trinity_ref.kind,
            trinity_ref.media_type,
            trinity_ref.manifest_profile_sha256,
        )

        explicit_state = state.model_copy(
            update={"params": {"policy_candidate_id": "explicit_candidate"}}
        )
        explicit, _ = resolve_policy_output_candidate(ctx, explicit_state)
        explicit_phase3 = resolve_phase3_candidate(ctx, explicit_state)
        assert explicit is not None and explicit_phase3 is not None
        assert explicit.candidate_id == "explicit_candidate"
        assert explicit_phase3.candidate_id == "explicit_candidate"

        for invalid_candidate_id in (None, "", 7):
            invalid_state = state.model_copy(
                update={"params": {"policy_candidate_id": invalid_candidate_id}}
            )
            try:
                resolve_policy_output_candidate(ctx, invalid_state)
            except ValueError as exc:
                assert "policy_candidate_id_invalid" in str(exc)
            else:
                raise AssertionError("an explicit invalid candidate ID must be refused")
            try:
                resolve_phase3_candidate(ctx, invalid_state)
            except CanonicalProfileRefusalError as exc:
                assert exc.code == "phase3_selected_trinity_candidate_unreadable"
            else:
                raise AssertionError("Phase 3 must preserve invalid selected candidate refusal")
