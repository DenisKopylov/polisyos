from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.scientist import GovernanceAccountabilityArtifactRef
from polisyos.ir.analytics.decision_layer import (
    SocialWeightManifestArtifact,
    build_optimization_ambiguity_certificate,
    persist_optimization_ambiguity_certificate,
    persist_social_weight_manifest,
)
from polisyos.ir.analytics.welfare import (
    GEUncertaintyBundle,
    GEUncertaintyRepresentation,
    WelfareBundle,
    WelfareIntervalSemantics,
    WelfareMethod,
    WelfareStatus,
    persist_ge_uncertainty_bundle,
    persist_welfare_bundle,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, ParameterSpec, PolicySpec
from polisyos.ir.governance.problem_frame import (
    ConstraintSpec,
    ConstraintType,
    ObjectiveSpec,
    ProblemDomain,
    ProblemFrame,
)
from polisyos.ir.kernel.values import MoneyValue
from polisyos.ir.model_layer.model_spec import AssumptionSpec, AssumptionType, ModelSpec
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.model_layer.types import OptimizationDirection, SelectorOperator
from polisyos.scientist.orchestration.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixResult
from polisyos.scientist.governance.calibration_leaderboard import (
    CalibrationLeaderboardEntry,
    CalibrationLeaderboardMetrics,
)
from polisyos.scientist.governance.calibration_validation import (
    CalibrationValidationBundle,
    persist_calibration_validation_bundle,
)
from polisyos.scientist.governance.stress_scenarios import StressScenarioKind, StressScenarioResult
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
    BuildPolicyOutputBundleNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CLAIMS_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF,
    ARTIFACT_POLICY_BRIEF_REF,
    ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.policy_design.objectives import (
    ConstraintStatus,
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.output import (
    PolicyBrief,
    load_champion_policy_dossier,
    load_policy_artifact_bundle,
    load_replayable_audit_bundle,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema, TargetPopulationSpec
from polisyos.scientist.policy_design.translator import TranslatorComplianceResult
from polisyos.scientist.methods.search import (
    ActionableSideInformation,
    persist_actionable_side_information,
)
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOutcome
from polisyos.scientist.methods.search.funnel.types import FunnelStageResult, UncertaintyEnvelope
from polisyos.scientist.methods.search.readiness import DecisionReadiness, DecisionReadinessContract


def _passing_judge_verdict() -> dict[str, object]:
    return {
        "per_judge": {
            name: {"judge_name": name, "passed": True, "is_fatal": True}
            for name in (
                "structural",
                "statistical",
                "robustness",
                "governance",
                "reproducibility",
                "compute",
            )
        },
        "composite_decision": "promote",
        "blocking_failures": [],
        "warnings": [],
    }


def _bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_policy",
            domain=ProblemDomain.FISCAL,
            objectives=[
                ObjectiveSpec(
                    objective_id="welfare",
                    metric_id="welfare_metric",
                    direction=OptimizationDirection.MAXIMIZE,
                )
            ],
            hard_constraints=[
                ConstraintSpec(
                    constraint_id="budget_cap",
                    constraint_type=ConstraintType.HARD,
                    value=MoneyValue(amount=Decimal("100"), currency="USD"),
                    operator="<=",
                    notes=["budget ceiling"],
                )
            ],
        ),
        policy_spec=PolicySpec(
            policy_id="policy_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="tax_policy",
                    target={
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    schedule={"start_step": 0, "duration_steps": 2},
                    params={"rate": Decimal("0.1")},
                )
            ],
            parameters=[
                ParameterSpec(
                    param_id="tax_rate",
                    intervention_id="tax_cut",
                    param_path="rate",
                    default_value=Decimal("0.1"),
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_policy",
            data_snapshot_ref="sha256:" + "1" * 64,
            assumptions=[
                AssumptionSpec(
                    assumption_id="elasticity",
                    assumption_type=AssumptionType.PARAMETRIC,
                    description="Elasticity remains stable in the policy horizon.",
                )
            ],
        ),
    )


def _candidate() -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        _bundle(),
        candidate_id="candidate_policy",
        metadata={"policy_family": "core_family", "evidence_depth": "replicated"},
    ).model_copy(
        update={
            "target_population": TargetPopulationSpec(
                population_id="population_policy",
                description="General population",
                geography="national",
            )
        }
    )


def _evaluation_vector(candidate: PolicyCandidateSchema) -> PolicyEvaluationVector:
    return PolicyEvaluationVector(
        candidate_id=candidate.candidate_id,
        primary={
            "policy_value": ObjectiveChannelValue(
                name="policy_value",
                kind=ObjectiveKind.PRIMARY,
                value=1.2,
                direction=ObjectiveDirection.MAXIMIZE,
            )
        },
        hard_constraints={
            "policy_budget_constraint": ObjectiveChannelValue(
                name="policy_budget_constraint",
                kind=ObjectiveKind.HARD_CONSTRAINT,
                value=0.95,
                direction=ObjectiveDirection.MINIMIZE,
                threshold=1.0,
                status=ConstraintStatus.NEAR_BINDING,
            )
        },
        feasible=True,
        metadata={"candidate_hash": candidate.candidate_hash()},
    )


def _readiness_contract() -> DecisionReadinessContract:
    return DecisionReadinessContract(
        readiness_level=DecisionReadiness.RECOMMENDATION_READY,
        required_judges_passed=["structural"],
        required_uncertainty_bounds={},
        mandatory_human_gate=False,
        assumptions_must_be_surfaced=["Elasticity remains stable in the policy horizon."],
        expiry_conditions=["freshness_violation"],
        evidence_depth_required="replicated",
    )


def _policy_brief() -> PolicyBrief:
    return PolicyBrief(
        title="Policy brief for candidate_policy",
        executive_summary="Candidate improves welfare while keeping the budget constraint near binding.",
        readiness_level=DecisionReadiness.RECOMMENDATION_READY.value,
        surfaced_assumptions=["Elasticity remains stable in the policy horizon."],
        subgroup_harms=["Low income"],
        hard_constraint_notes=["policy_budget_constraint"],
    )


def _translator_compliance() -> TranslatorComplianceResult:
    return TranslatorComplianceResult(passed=True, findings=[])


def _phase3_ready_refs(cas_store) -> tuple[ArtifactRef, ArtifactRef]:
    matrix_ref = cas_store.put_json(
        {"matrix": [[1]]},
        PutOptions(kind="ir.welfare_multiplier_matrix", media_type="application/json"),
    )
    social_weight_ref = persist_social_weight_manifest(
        cas_store,
        SocialWeightManifestArtifact(
            manifest_ref="swr://policy.welfare/test@1.0.0#phase3",
            method_fqn="policy.welfare.state_dependent_inverse_social_weights@1.0.0",
            normalization="mean_one",
            income_grid=(0.0, 1.0),
            weights_on_grid=(1.0, 1.0),
            state_keys=("income",),
            manifest_payload={
                "ref": "swr://policy.welfare/test@1.0.0#phase3",
                "income_grid": [0.0, 1.0],
                "weights_on_grid": [1.0, 1.0],
            },
        ),
    )
    ge_ref = persist_ge_uncertainty_bundle(
        cas_store,
        GEUncertaintyBundle(
            model_class="linearized_ge_io",
            representation=GEUncertaintyRepresentation.MULTIPLIER_INTERVALS,
            multiplier_shape=(1, 1),
            point_multiplier_ref=ArtifactRefModel.model_validate(
                matrix_ref.model_dump(mode="json")
            ),
            lower_multiplier_ref=ArtifactRefModel.model_validate(
                matrix_ref.model_dump(mode="json")
            ),
            upper_multiplier_ref=ArtifactRefModel.model_validate(
                matrix_ref.model_dump(mode="json")
            ),
        ),
    )
    welfare_ref = persist_welfare_bundle(
        cas_store,
        WelfareBundle(
            welfare_measure="net_social_welfare",
            model_class="linearized_ge_io",
            ge_multiplier_semantics="leontief_inverse",
            social_weight_ref=social_weight_ref,
            ge_uncertainty_ref=ge_ref,
            point_estimate=1.0,
            credible_interval=(0.9, 1.1),
            robust_interval=(0.8, 1.2),
            interval_semantics=WelfareIntervalSemantics.MIXED_NESTED,
            method_used=WelfareMethod.MIXED_NESTED,
            status=WelfareStatus.OK,
        ),
    )
    ambiguity_ref = persist_optimization_ambiguity_certificate(
        cas_store,
        build_optimization_ambiguity_certificate(
            {"mode": "not_applicable", "note": "deterministic path"},
            mode="not_applicable",
            source_kind="test",
            overall_status="pass",
            note="deterministic path",
        ),
    )
    return welfare_ref, ambiguity_ref


def test_build_policy_output_bundle_skips_outside_policy_mode(execution_context, minimal_state):
    outcome = BuildPolicyOutputBundleNode().execute(execution_context, minimal_state)
    assert outcome.status == "skip"


def test_build_policy_output_bundle_writes_refs(execution_context, minimal_state, cas_store):
    candidate = _candidate()
    welfare_ref, ambiguity_ref = _phase3_ready_refs(cas_store)
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
        }
    )
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref

    outcome = BuildPolicyOutputBundleNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert ARTIFACT_POLICY_OUTPUT_BUNDLE_REF in outcome.state.artifacts_index
    assert ARTIFACT_CLAIMS_REF in outcome.state.artifacts_index
    assert ARTIFACT_POLICY_BRIEF_REF in outcome.state.artifacts_index
    bundle = load_policy_artifact_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF],
    )
    assert bundle.policy_brief_ref is not None
    assert bundle.claims_ref == outcome.state.artifacts_index[ARTIFACT_CLAIMS_REF]
    assert bundle.welfare_bundle_ref == welfare_ref
    assert bundle.ambiguity_certificate_ref == ambiguity_ref
    assert (
        outcome.state.policy_output_bundle_ref
        == outcome.state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF]
    )


def test_build_policy_output_bundle_propagates_actionable_side_information(
    execution_context,
    minimal_state,
    cas_store,
):
    candidate = _candidate()
    welfare_ref, ambiguity_ref = _phase3_ready_refs(cas_store)
    side_info_ref = persist_actionable_side_information(
        cas_store,
        ActionableSideInformation(candidate_id=candidate.candidate_id),
    )
    funnel_outcome = FunnelOutcome(
        ticket_id="ticket_policy",
        candidate_hash=candidate.candidate_hash(),
        trace=[],
        stage_results={},
        final_result=FunnelStageResult(
            policy_candidate={},
            objective_value=1.0,
            is_promising=True,
            stage_name="funnel_L6_promotion",
            uncertainty_envelope=UncertaintyEnvelope.deterministic(),
        ),
        failure_cards=[],
        uncertainty_envelope=UncertaintyEnvelope.deterministic(),
        compute_actual_usd=0.5,
        degradation_mode="normal",
        final_action="complete",
        completed=True,
        audit_refs=[side_info_ref],
        actionable_side_information_refs=[side_info_ref],
    )

    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
            "funnel_outcome": funnel_outcome,
        }
    )
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref

    outcome = BuildPolicyOutputBundleNode().execute(execution_context, state)

    assert outcome.status == "ok"
    bundle = load_policy_artifact_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF],
    )
    audit_bundle = load_replayable_audit_bundle(cas_store, bundle.replayable_audit_bundle_ref)

    assert [ref.artifact_id for ref in bundle.actionable_side_information_refs] == [
        side_info_ref.artifact_id
    ]
    assert [ref.artifact_id for ref in bundle.audit_refs] == [side_info_ref.artifact_id]
    assert [ref.artifact_id for ref in audit_bundle.actionable_side_information_refs] == [
        side_info_ref.artifact_id
    ]


def test_build_policy_output_bundle_fails_when_required_inputs_missing(
    execution_context, minimal_state
):
    state = minimal_state.model_copy(deep=True)
    state.params.update({"workflow_id": "scientist_policy_design", "policy_mode": True})

    outcome = BuildPolicyOutputBundleNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None


def test_build_policy_output_bundle_refuses_when_phase3_gate_missing(
    execution_context,
    minimal_state,
):
    candidate = _candidate()
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
        }
    )

    outcome = BuildPolicyOutputBundleNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert "phase3.welfare_missing" in outcome.error.message
    assert ARTIFACT_POLICY_OUTPUT_BUNDLE_REF not in outcome.state.artifacts_index


def test_build_policy_output_bundle_embeds_calibration_validation_summary(
    execution_context,
    minimal_state,
    cas_store,
) -> None:
    candidate = _candidate()
    welfare_ref, ambiguity_ref = _phase3_ready_refs(cas_store)
    state = minimal_state.model_copy(deep=True)
    candidate_ref = ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="scientist.test",
        media_type="application/json",
    )
    calibration_validation_ref = persist_calibration_validation_bundle(
        cas_store,
        CalibrationValidationBundle(
            run_id="R_policy_c5b",
            candidate_ref=candidate_ref,
            governance_verdict="approve",
            status="completed",
            backtest_matrix=BacktestMatrixResult(
                report_id="BTM_policy",
                composite_score=0.79,
                worst_kind=BacktestKind.DISTRESS,
            ),
            stress_scenarios=StressScenarioResult(
                report_id="stress_policy",
                robustness_score=0.73,
                worst_scenario=StressScenarioKind.TRADE_DISRUPTION,
            ),
            leaderboard_entry=CalibrationLeaderboardEntry(
                entry_id="leaderboard_policy",
                run_id="R_policy_c5b",
                candidate_ref=candidate_ref,
                metrics=CalibrationLeaderboardMetrics(
                    calibration_fit_score=0.88,
                    backtest_matrix_score=0.79,
                    stress_robustness_score=0.73,
                    specification_curve_robustness=0.7,
                    transportability_score=0.81,
                    interference_fit=0.76,
                    strategic_response_plausibility=0.82,
                    governance_verdict="approve",
                    adversarial_passed=True,
                    eligible_for_promotion=True,
                    composite_score=0.8,
                ),
                worst_backtest_kind=BacktestKind.DISTRESS,
                worst_stress_scenario=StressScenarioKind.TRADE_DISRUPTION,
            ),
            governance_accountability_ref=GovernanceAccountabilityArtifactRef(
                artifact_id="sha256:" + "9" * 64
            ),
            governance_accountability_summary={
                "risk_weighted_verdict": "needs_revision",
                "requires_human_review": False,
                "selected_threshold": 0.55,
            },
        ),
    )
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
        }
    )
    state.artifacts_index[ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF] = calibration_validation_ref
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref

    outcome = BuildPolicyOutputBundleNode().execute(execution_context, state)

    assert outcome.status == "ok"
    bundle = load_policy_artifact_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF],
    )
    dossier = load_champion_policy_dossier(cas_store, bundle.champion_policy_dossier_ref)
    assert dossier.calibration_validation_summary["composite_score"] == 0.8
    assert dossier.calibration_validation_summary["worst_backtest_kind"] == "distress"
    assert dossier.accountability_summary["risk_weighted_verdict"] == "needs_revision"
    assert bundle.governance_accountability_artifact_ref is not None


def test_build_policy_output_bundle_degrades_invalid_distributional_report(
    execution_context,
    minimal_state,
    cas_store,
) -> None:
    candidate = _candidate()
    welfare_ref, ambiguity_ref = _phase3_ready_refs(cas_store)
    invalid_ref = cas_store.put_json(
        ["invalid"],
        PutOptions(kind="ir.distributional_report", media_type="application/json"),
    )
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
        }
    )
    state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_REPORT_REF] = invalid_ref
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref

    outcome = BuildPolicyOutputBundleNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert ARTIFACT_POLICY_OUTPUT_BUNDLE_REF in outcome.state.artifacts_index
    assert any(
        event.code == "policy_output_bundle.optional_artifact_degraded"
        and event.attrs.get("reason") == "distributional_report_load_failed"
        for event in outcome.events
    )


def test_build_policy_output_bundle_degrades_invalid_uncertainty_envelope(
    execution_context,
    minimal_state,
    cas_store,
) -> None:
    candidate = _candidate()
    welfare_ref, ambiguity_ref = _phase3_ready_refs(cas_store)
    invalid_ref = cas_store.put_json(
        ["invalid"],
        PutOptions(kind="ir.uncertainty_envelope", media_type="application/json"),
    )
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
        }
    )
    state.artifacts_index[ARTIFACT_CAUSAL_ENVELOPE_REF] = invalid_ref
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref

    outcome = BuildPolicyOutputBundleNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert ARTIFACT_POLICY_OUTPUT_BUNDLE_REF in outcome.state.artifacts_index
    assert any(
        event.code == "policy_output_bundle.optional_artifact_degraded"
        and event.attrs.get("reason") == "uncertainty_envelope_load_failed"
        for event in outcome.events
    )


def test_build_policy_output_bundle_uses_branch_state_for_declared_outputs(
    execution_context,
    minimal_state,
):
    candidate = _candidate()
    welfare_ref, ambiguity_ref = _phase3_ready_refs(execution_context.store)
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "judge_verdict": _passing_judge_verdict(),
            "nested": {"baseline": True},
        }
    )
    state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = welfare_ref
    state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = ambiguity_ref
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with patch(
        "polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle.branch_state",
        _spy_branch,
    ):
        outcome = BuildPolicyOutputBundleNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "policy_output_bundle_ref",
        "policy_brief_ref",
        "champion_policy_dossier_ref",
        "artifacts_index.policy_output_bundle_ref",
        "artifacts_index.policy_frontier_report_ref",
        "artifacts_index.champion_policy_dossier_ref",
        "artifacts_index.claims_ref",
        "artifacts_index.policy_brief_ref",
        "artifacts_index.constraint_satisfaction_report_ref",
        "artifacts_index.subgroup_impact_report_ref",
        "artifacts_index.policy_uncertainty_report_ref",
        "artifacts_index.policy_transportability_report_ref",
        "artifacts_index.governance_gate_packet_ref",
        "artifacts_index.implementation_plan_ref",
        "artifacts_index.rejected_alternatives_summary_ref",
        "artifacts_index.replayable_audit_bundle_ref",
        "artifacts_index.decision_readiness_contract_ref",
        "artifacts_index.validation_report_ref",
        "artifacts_index.judge_verdict_ref",
    )
    assert state.params["nested"] == {"baseline": True}
    assert state.policy_output_bundle_ref is None
    assert ARTIFACT_POLICY_OUTPUT_BUNDLE_REF not in state.artifacts_index
    assert outcome.state.policy_output_bundle_ref is not None
    assert ARTIFACT_POLICY_OUTPUT_BUNDLE_REF in outcome.state.artifacts_index


def test_decision_packet_not_mutated_when_policy_bundle_absent(tmp_path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store, registry_bundle=registry_bundle, run_id="R_packet_no_policy"
    )
    import logging

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
        {"data_ref": None},
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    state = ExperimentState(
        run_id="R_packet_no_policy",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        params={"random_seed": 1},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    payload = from_canonical_bytes(store.get_bytes(outcome.artifacts[0].artifact_id))

    assert "policy_output_bundle" not in payload


def test_decision_packet_records_degraded_path_for_invalid_policy_bundle(tmp_path) -> None:
    import logging

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_packet_invalid_policy_bundle",
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.policy"))

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
    invalid_policy_bundle_ref = store.put_json(
        ["invalid"],
        PutOptions(kind="scientist.policy_output_bundle", media_type="application/json"),
    )
    state = ExperimentState(
        run_id="R_packet_invalid_policy_bundle",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_POLICY_OUTPUT_BUNDLE_REF: invalid_policy_bundle_ref},
        params={"random_seed": 1, "judge_verdict": _passing_judge_verdict()},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    payload = from_canonical_bytes(store.get_bytes(outcome.artifacts[0].artifact_id))
    degraded_reasons = [item["reason"] for item in payload["degraded_paths"]]

    assert "policy_output_bundle" not in payload
    assert "policy_output_bundle_load_failed" in degraded_reasons
    assert payload["analysis_limits"]["decision_packet_degraded"] is True
