from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.compiler.report import CompileReport, put_compile_report, put_link_report
from polisyos.core.contracts.backtest import BacktestReportRef
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.contracts.lex import ChangeProposalRef, LegalReportRef
from polisyos.core.contracts.scientist import (
    GovernanceAccountabilityArtifactRef,
    StressTestReportRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
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
from polisyos.ir.analytics.hte import (
    HTEResult,
    PolicyRecommendation,
    TargetingRule,
    persist_hte_result,
    persist_policy_recommendation,
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
from polisyos.ir.analytics.sensitivity import SensitivityResult, persist_sensitivity_result
from polisyos.ir.analytics.strategic import (
    EquilibriumSelectionSummary,
    EquilibriumSetSummary,
    FiniteStrategicPayoffTable,
    PostAdaptationPolicyValueSummary,
    StrategicClosureSummary,
    StrategicEquilibriumConcept,
    StrategicFallbackMode,
    StrategicResponseBundle,
    StrategicSCM,
    persist_equilibrium_selection_summary,
    persist_equilibrium_set_summary,
    persist_post_adaptation_policy_value_summary,
    persist_strategic_closure_summary,
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
from polisyos.ir.linker import LinkReport
from polisyos.ir.refs import ArtifactRefModel, UncertaintyEnvelopeRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixResult
from polisyos.scientist.governance.calibration_leaderboard import (
    CalibrationLeaderboardEntry,
    CalibrationLeaderboardMetrics,
)
from polisyos.scientist.governance.calibration_validation import (
    CalibrationValidationBundle,
    persist_calibration_validation_bundle,
)
from polisyos.scientist.governance.report import GovernanceReport, GovernanceReportLinks
from polisyos.scientist.governance.stress_scenarios import StressScenarioKind, StressScenarioResult
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
    ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
    ARTIFACT_BACKTEST_REPORT_REF,
    ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF,
    ARTIFACT_HTE_RESULT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
    ARTIFACT_POLICY_RECOMMENDATION_REF,
    ARTIFACT_SENSITIVITY_RESULT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_STRATEGIC_SCM_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_CHANGE_PROPOSAL_REF,
    REPORT_COMPILE_REPORT_REF,
    REPORT_GOVERNANCE_REPORT_REF,
    REPORT_LEGAL_REPORT_REF,
    REPORT_LINK_REPORT_REF,
)


def _artifact_id(ch: str) -> str:
    return f"sha256:{ch * 64}"


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

    assert payload["schema_version"] == "3.4"
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
    assert payload["feedback_loop"]["anchor_at"] is not None
    assert payload["feedback_loop"]["monitoring_contract_ref"] is not None
    assert payload["feedback_loop"]["latest_monitoring_report_ref"] is None
    assert payload["inputs"]["trinity_bundle_ref"] == str(trinity_ref.artifact_id)
    assert payload["artifacts"]["metrics_ref"] == str(metrics_ref.artifact_id)
    assert payload["artifacts"]["governance_report_ref"] == str(governance_ref.artifact_id)
    assert "input.trinity_bundle_ref" in roles
    assert "input.registry_bundle_ref" in roles
    assert "input.data_snapshot_ref" in roles
    assert "artifact.metrics_ref" in roles
    assert "artifact.governance_report_ref" in roles


def test_build_decision_packet_records_degraded_paths_for_invalid_metrics_and_governance(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_degraded")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.degraded"))

    trinity_ref = store.put_json(
        {"trinity": {}},
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
    metrics_ref = store.put_json(
        ["invalid"],
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    governance_ref = store.put_json(
        ["invalid"],
        PutOptions(kind="scientist.governance_report", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_packet_degraded",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_METRICS_REF: metrics_ref},
        reports_index={REPORT_GOVERNANCE_REPORT_REF: governance_ref},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    payload = from_canonical_bytes(store.get_bytes(outcome.artifacts[0].artifact_id))
    degraded_reasons = {item["reason"] for item in payload["degraded_paths"]}

    assert payload["simulation_results"] is None
    assert payload["governance"] is None
    assert degraded_reasons == {
        "decision_basis_data_snapshot_validate_failed",
        "governance_report_load_failed",
        "metrics_load_failed",
        "uncertainty_data_snapshot_load_failed",
    }
    assert payload["diagnostics_summary"]["degraded_path_count"] == 3
    assert payload["diagnostics_summary"]["has_degraded_paths"] is True
    assert payload["analysis_limits"]["decision_packet_degraded"] is True
    assert any(
        note.startswith("metrics_load_failed:") for note in payload["notes"]
    )
    assert any(
        note.startswith("governance_report_load_failed:") for note in payload["notes"]
    )


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
    invalid_quality_ref = store.put_json(
        ["invalid"],
        PutOptions(kind="fabric.quality_report", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        DataSnapshot(
            data_ref=state_snapshot_ref,
            quality_report_ref=invalid_quality_ref,
        ),
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
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
        note.startswith("decision_basis_quality_report_load_failed:")
        for note in payload["notes"]
    )
    assert (
        payload["decision_validity_envelope"]["data_basis"]["summary"]["quality_report_ref"]
        == str(invalid_quality_ref.artifact_id)
    )


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
        "missing_runtime_mechanism_support:custom_subsidy",
    ]
    assert payload["analysis_limits"]["missing_runtime_mechanism_support"] is True


def test_build_decision_packet_includes_tradeoff_certificate_and_normative_validity(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_normative")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.normative"))

    trinity_ref = store.put_json(
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
            "policy_spec": {"schema_version": "1.0", "policy_id": "policy", "interventions": []},
            "model_spec": {
                "schema_version": "1.0",
                "model_id": "model",
                "data_snapshot_ref": "sha256:" + "0" * 64,
                "fidelity_level": "hybrid",
            },
        },
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
    governance_ref = store.put_json(
        GovernanceReport(verdict="approve", issues=[]),
        PutOptions(kind="scientist.governance_report", media_type="application/json"),
    )
    normative_ref = persist_normative_arbitration_result(
        store,
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
        reports_index={REPORT_GOVERNANCE_REPORT_REF: governance_ref},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["artifacts"]["normative_arbitration_result_ref"] == str(normative_ref.artifact_id)
    assert payload["tradeoff_certificate"]["selected_policy"] == "weighted_welfare"
    assert payload["diagnostics_summary"]["normative_model_completeness"] == "partial"
    assert payload["diagnostics_summary"]["normative_residual_dissent_count"] == 1
    assert (
        payload["decision_validity_envelope"]["normative_basis"]["summary"]["normative_selected_policy"]
        == "weighted_welfare"
    )
    assert payload["decision_validity_baseline"]["status"] == "warning"


def test_build_decision_packet_rejects_incomplete_serious_contract(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_serious_fail")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.serious"))

    trinity_ref = store.put_json(
        {"trinity": {}},
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
    governance_ref = store.put_json(
        GovernanceReport(verdict="approve", issues=[]),
        PutOptions(kind="scientist.governance_report", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_packet_serious_fail",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        reports_index={REPORT_GOVERNANCE_REPORT_REF: governance_ref},
        execution_profile="governed",
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.invalid_state"
    assert "capability_manifest_ref" in outcome.error.details["missing_contracts"]
    assert ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF in outcome.error.details["missing_contracts"]
    assert ARTIFACT_TRANSPORTABILITY_RESULT_REF in outcome.error.details["missing_contracts"]
    assert ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF in outcome.error.details["missing_contracts"]


def test_build_decision_packet_records_degraded_paths_for_invalid_normative_arbitration(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
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

    trinity_ref = store.put_json(
        {"trinity": {}},
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
    governance_ref = store.put_json(
        GovernanceReport(verdict="approve", issues=[]),
        PutOptions(kind="scientist.governance_report", media_type="application/json"),
    )
    invalid_normative_ref = store.put_json(
        ["invalid"],
        PutOptions(kind="ir.normative_arbitration_result", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_packet_invalid_normative",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF: invalid_normative_ref},
        reports_index={REPORT_GOVERNANCE_REPORT_REF: governance_ref},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    payload = from_canonical_bytes(store.get_bytes(outcome.artifacts[0].artifact_id))
    degraded_reasons = {item["reason"] for item in payload["degraded_paths"]}

    assert payload["tradeoff_certificate"] is None
    assert "normative_arbitration_load_failed" in degraded_reasons
    assert payload["diagnostics_summary"]["degraded_path_count"] >= 1
    assert any(
        note.startswith("normative_arbitration_load_failed:")
        for note in payload["notes"]
    )


def test_build_decision_packet_accepts_complete_serious_contract(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_serious_ok")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.serious.ok"))

    trinity_ref = store.put_json(
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
            "policy_spec": {"schema_version": "1.0", "policy_id": "policy", "interventions": []},
            "model_spec": {
                "schema_version": "1.0",
                "model_id": "model",
                "data_snapshot_ref": "sha256:" + "0" * 64,
                "fidelity_level": "hybrid",
            },
        },
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
    metrics_ref = store.put_json(
        Metrics(values={"policy_cost": 100.0, "applied_nodes": 1}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    governance_ref = store.put_json(
        GovernanceReport(verdict="approve", issues=[]),
        PutOptions(kind="scientist.governance_report", media_type="application/json"),
    )
    normative_ref = persist_normative_arbitration_result(
        store,
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
        store,
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
        reports_index={REPORT_GOVERNANCE_REPORT_REF: governance_ref},
        execution_profile="governed",
        capability_manifest_ref=capability_manifest_ref,
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)

    assert outcome.status == "ok"
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    assert payload["runtime_contracts"]["execution_profile"] == "governed"
    assert payload["runtime_contracts"]["capability_manifest_ref"] == str(
        capability_manifest_ref.artifact_id
    )
    assert payload["artifacts"]["cross_graph_evidence_profile_ref"] == str(cross_graph_ref.artifact_id)
    assert payload["artifacts"]["transportability_result_ref"] == str(transport_ref.artifact_id)
    assert payload["feedback_loop"]["monitoring_contract_ref"] is not None


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
    assert "uncertainty_output_envelope_load_failed" in degraded_reasons
    assert any(
        note.startswith("uncertainty_output_envelope_load_failed:")
        for note in payload["notes"]
    )


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
    abstraction_map_ref = persist_finite_state_abstraction_map(
        store,
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
        store,
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


def test_build_decision_packet_includes_calibration_validation_summary(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_c5b",
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
    data_snapshot_ref = store.put_json(
        {"data_ref": {"artifact_id": "sha256:" + "1" * 64}},
        PutOptions(kind="foundry.data_snapshot", media_type="application/json"),
    )
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
    assert payload["calibration_validation"]["summary"]["composite_score"] == 0.82
    assert payload["calibration_validation"]["summary"]["worst_backtest_kind"] == "distress"
    assert payload["calibration_validation"]["governance_accountability_summary"]["risk_weighted_verdict"] == "human_gate"
    assert payload["calibration_validation"]["governance_accountability_ref"] == "sha256:" + "5" * 64


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

    trinity_ref = store.put_json(
        {"trinity": {}},
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


def test_build_decision_packet_surfaces_strategic_runtime_artifacts(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_strategic")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.strategic"))

    trinity_ref = store.put_json(
        {"trinity": {}},
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
    base_graph_ref = store.put_json(
        {"graph": {}},
        PutOptions(kind="ir.causal_graph", media_type="application/json"),
    )
    policy_rule_ref = store.put_json(
        {"policy_rule": {}},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
    )
    leader_table_ref = persist_strategic_payoff_table(
        store,
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
        store,
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
        store,
        StrategicSCM(
            base_graph_ref=ArtifactRefModel.model_validate(base_graph_ref.model_dump(mode="json")),
            strategic_agents=("leader", "follower"),
            utility_refs={
                "leader": leader_table_ref,
                "follower": follower_table_ref,
            },
            policy_rule_ref=ArtifactRefModel.model_validate(policy_rule_ref.model_dump(mode="json")),
            equilibrium_concept=StrategicEquilibriumConcept.STACKELBERG,
        ),
    )
    strategic_closure_ref = persist_strategic_closure_summary(
        store,
        StrategicClosureSummary(
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
            equilibrium_concept=StrategicEquilibriumConcept.STACKELBERG,
            equilibrium_selection_dependence="follower_best_response_tie_breaking",
            profile_count=4,
            equilibrium_count=2,
        ),
    )
    equilibrium_set_ref = persist_equilibrium_set_summary(
        store,
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
        store,
        EquilibriumSelectionSummary(
            selected_equilibrium={"leader": "A", "follower": "X"},
            equilibrium_selection_dependence="follower_best_response_tie_breaking",
        ),
    )
    post_value_ref = persist_post_adaptation_policy_value_summary(
        store,
        PostAdaptationPolicyValueSummary(
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
            baseline_policy_value=1.0,
            point_value=1.3,
        ),
    )
    strategic_bundle_ref = persist_strategic_response_bundle(
        store,
        StrategicResponseBundle(
            causal_component_ref=ArtifactRefModel.model_validate(policy_rule_ref.model_dump(mode="json")),
            strategic_closure_ref=strategic_closure_ref,
            equilibrium_selection_dependence="follower_best_response_tie_breaking",
            equilibrium_set_ref=equilibrium_set_ref,
            selected_equilibrium_ref=selected_equilibrium_ref,
            multiplicity_note="multiple_stackelberg_equilibria",
            post_adaptation_policy_value_ref=post_value_ref,
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
    assert payload["strategic"]["equilibrium_selection_dependence"] == (
        "follower_best_response_tie_breaking"
    )
    assert payload["strategic"]["strategic_scm_ref"] == str(strategic_scm_ref.artifact_id)
    assert payload["strategic"]["strategic_response_bundle_ref"] == str(
        strategic_bundle_ref.artifact_id
    )
    assert payload["strategic"]["post_adaptation_policy_value"] == 1.3


def test_build_decision_packet_falls_back_to_blocked_strategic_summary_without_bundle(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_strategic_blocked")
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.packet.strategic.blocked"),
    )

    trinity_ref = store.put_json(
        {"trinity": {}},
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
    base_graph_ref = store.put_json(
        {"graph": {}},
        PutOptions(kind="ir.causal_graph", media_type="application/json"),
    )
    policy_rule_ref = store.put_json(
        {"policy_rule": {}},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
    )
    leader_table_ref = persist_strategic_payoff_table(
        store,
        FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=("leader", "follower"),
            action_spaces={"leader": ("A",), "follower": ("X",)},
            payoffs={"leader=A|follower=X": 1.0},
        ),
    )
    follower_table_ref = persist_strategic_payoff_table(
        store,
        FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=("leader", "follower"),
            action_spaces={"leader": ("A",), "follower": ("X",)},
            payoffs={"leader=A|follower=X": 1.0},
        ),
    )
    strategic_scm_ref = persist_strategic_scm(
        store,
        StrategicSCM(
            base_graph_ref=ArtifactRefModel.model_validate(base_graph_ref.model_dump(mode="json")),
            strategic_agents=("leader", "follower"),
            utility_refs={
                "leader": leader_table_ref,
                "follower": follower_table_ref,
            },
            policy_rule_ref=ArtifactRefModel.model_validate(policy_rule_ref.model_dump(mode="json")),
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
