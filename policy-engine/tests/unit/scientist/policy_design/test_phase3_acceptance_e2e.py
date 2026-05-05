from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from decimal import Decimal

import pytest
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.ic_verification import ICVerificationRequest
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.microsim.protocols import MicrosimResult
from polisyos.ir.analytics.decision_layer import (
    SocialWeightManifestArtifact,
    build_optimization_ambiguity_certificate,
    persist_optimization_ambiguity_certificate,
    persist_social_weight_manifest,
)
from polisyos.ir.analytics.welfare import (
    ChannelDecompositionArtifact,
    ChannelDecompositionTargetKind,
    ChannelIdentificationStatus,
    ChannelPolicyClass,
    GEUncertaintyBundle,
    GEUncertaintyRepresentation,
    WelfareBundle,
    WelfareIntervalSemantics,
    WelfareMethod,
    WelfareStatus,
    persist_channel_decomposition_artifact,
    persist_ge_uncertainty_bundle,
    persist_welfare_bundle,
)
from polisyos.ir.governance.game_design import (
    BayesianTypeSpec,
    MechanismConstraintType,
    MechanismDesignConstraint,
    MechanismDesignSpec,
    MechanismGameRepresentation,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, MechanismBinding, PolicySpec
from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_spec import FidelityLevel, ModelSpec
from polisyos.ir.refs import ArtifactRefModel
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import OptimizationDirection
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import (
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.output import (
    PolicyArtifactBuilder,
    PolicyArtifactBuildInput,
    PolicyBrief,
    load_policy_artifact_bundle,
)
from polisyos.scientist.policy_design.phase3 import resolve_phase3_gate
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.policy_design.translator import TranslatorComplianceResult
from polisyos.scientist.search.judge_stack import JudgeVerdict
from polisyos.scientist.search.readiness import (
    DecisionReadiness,
    DecisionReadinessContract,
    DecisionReadinessEvaluator,
)
from polisyos.scientist.search.uncertainty import (
    UncertaintyEnvelope,
    UncertaintyEstimate,
    UncertaintyType,
)
from polisyos.scientist.verification.ic import load_ic_certificate, verify_incentive_compatibility


def _ctx(tmp_path, *, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path / "cas")
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def _run_id(ctx: ExecutionContext) -> str:
    return ctx.run.run_manifest.run_id


def _decimalize_floats(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, Mapping):
        return {key: _decimalize_floats(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_decimalize_floats(item) for item in value]
    return value


def _problem_frame() -> ProblemFrame:
    return ProblemFrame(
        problem_id="phase3_policy",
        domain=ProblemDomain.FISCAL,
        objectives=[
            ObjectiveSpec(
                objective_id="welfare",
                metric_id="social_welfare",
                direction=OptimizationDirection.MAXIMIZE,
            )
        ],
    )


def _model_spec() -> ModelSpec:
    return ModelSpec(
        model_id="phase3_model",
        data_snapshot_ref="sha256:" + "0" * 64,
        fidelity_level=FidelityLevel.HYBRID,
    )


def _candidate_from_policy(policy: PolicySpec, *, candidate_id: str) -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=_problem_frame(),
            policy_spec=policy,
            model_spec=_model_spec(),
        ),
        candidate_id=candidate_id,
        metadata={"evidence_depth": "replicated"},
    )


def _non_mechanism_policy() -> PolicySpec:
    return PolicySpec(
        policy_id="phase3_non_mechanism",
        interventions=[
            InterventionSpec(
                intervention_id="baseline_transfer",
                kind="cash_transfer",
                target=SelectorPredicate(field="income", operator=">=", value=Decimal("0")),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={"transfer": Decimal("1.0")},
            )
        ],
    )


def _family_policy(
    *,
    mechanism_id: str,
    intervention_id: str,
    intervention_kind: str,
    params: dict[str, object],
    constraint_type: MechanismConstraintType,
) -> PolicySpec:
    return PolicySpec(
        policy_id=f"phase3_{mechanism_id}",
        interventions=[
            InterventionSpec(
                intervention_id=intervention_id,
                kind=intervention_kind,
                target=SelectorPredicate(field="income", operator=">=", value=Decimal("0")),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params=params,
            )
        ],
        mechanism_bindings=[
            MechanismBinding(
                binding_id=f"{intervention_id}_binding",
                mechanism_id=mechanism_id,
                intervention_ids=[intervention_id],
            )
        ],
        mechanism_design=MechanismDesignSpec(
            design_id=f"{mechanism_id}_design",
            representation=MechanismGameRepresentation.BAYESIAN,
            players=("agent",),
            mechanism_ids=(mechanism_id,),
            action_spaces={"agent": ("low", "middle", "high")},
            bayesian_types=[
                BayesianTypeSpec(
                    player_id="agent",
                    type_space=("low", "middle", "high"),
                    prior_probabilities={"low": 1 / 3, "middle": 1 / 3, "high": 1 / 3},
                )
            ],
            constraints=[
                MechanismDesignConstraint(
                    constraint_id=f"{mechanism_id}_{constraint_type.value}",
                    constraint_type=constraint_type,
                    applies_to_players=("agent",),
                )
            ],
        ),
    )


def _tax_policy() -> PolicySpec:
    return _family_policy(
        mechanism_id="bayes_tax_pl_v1",
        intervention_id="income_tax",
        intervention_kind="income_tax_piecewise_linear",
        params={
            "type_grid": [Decimal("1.0"), Decimal("1.5"), Decimal("2.0")],
            "earnings_schedule": [Decimal("0.85"), Decimal("1.20"), Decimal("1.55")],
            "prior_weights": [Decimal("0.25"), Decimal("0.50"), Decimal("0.25")],
            "u0": Decimal("0"),
            "revenue_floor": Decimal("-1"),
        },
        constraint_type=MechanismConstraintType.BAYESIAN_IC,
    )


def _license_policy() -> PolicySpec:
    return _family_policy(
        mechanism_id="license_scoring_reserve_v1",
        intervention_id="license_auction",
        intervention_kind="license_scoring_auction",
        params={
            "bid_grid": [Decimal("0"), Decimal("0.5"), Decimal("1.0")],
            "allocation_rule": [Decimal("0"), Decimal("1"), Decimal("1")],
            "payments": [Decimal("0"), Decimal("0.5"), Decimal("0.5")],
            "reserve_price": Decimal("0.5"),
            "n_bidders": 5,
            "k_units": 2,
            "cdf_at_reserve": Decimal("0.5"),
        },
        constraint_type=MechanismConstraintType.DOMINANT_STRATEGY_IC,
    )


def _persist_complete_welfare(ctx: ExecutionContext, *, behavioral: bool = False):
    matrix_ref = ctx.store.put_json(
        {"matrix": [[1]]},
        PutOptions(kind="ir.welfare_multiplier_matrix", media_type="application/json"),
    )
    social_weight_ref = persist_social_weight_manifest(
        ctx.store,
        SocialWeightManifestArtifact(
            manifest_ref="swr://phase3/acceptance@1.0.0#weights",
            method_fqn="policy.welfare.state_dependent_inverse_social_weights@1.0.0",
            normalization="mean_one",
            income_grid=(0.0, 1.0),
            weights_on_grid=(1.1, 0.9),
            state_keys=("income",),
        ),
    )
    ge_ref = persist_ge_uncertainty_bundle(
        ctx.store,
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
    channel_ref = None
    if behavioral:
        channel_ref = persist_channel_decomposition_artifact(
            ctx.store,
            ChannelDecompositionArtifact(
                target_kind=ChannelDecompositionTargetKind.SOCIAL_WELFARE,
                policy_class=ChannelPolicyClass.LOCAL_AFFINE_TAX_TRANSFER,
                basis_labels=("delta_tax_rate",),
                step_vector=(0.02,),
                mechanical_vector=(0.6,),
                behavioral_vector=(-0.2,),
                fiscal_feedback_vector=(0.1,),
                total_vector=(0.5,),
                identification_status=ChannelIdentificationStatus.IDENTIFIED,
                baseline_microdata_ref=ArtifactRefModel(
                    artifact_id="sha256:" + "2" * 64,
                    kind="ir.baseline_microdata",
                    media_type="application/json",
                ),
                policy_basis_ref=ArtifactRefModel(
                    artifact_id="sha256:" + "3" * 64,
                    kind="ir.policy_basis",
                    media_type="application/json",
                ),
                mechanical_inputs_ref=ArtifactRefModel(
                    artifact_id="sha256:" + "4" * 64,
                    kind="ir.mechanical_inputs",
                    media_type="application/json",
                ),
            ),
        )
    return persist_welfare_bundle(
        ctx.store,
        WelfareBundle(
            welfare_measure="net_social_welfare",
            model_class="linearized_ge_io",
            ge_multiplier_semantics="leontief_inverse",
            social_weight_ref=social_weight_ref,
            ge_uncertainty_ref=ge_ref,
            channel_decomposition_ref=channel_ref,
            point_estimate=1.0,
            credible_interval=(0.9, 1.1),
            robust_interval=(0.8, 1.2),
            interval_semantics=WelfareIntervalSemantics.MIXED_NESTED,
            method_used=WelfareMethod.MIXED_NESTED,
            status=WelfareStatus.OK,
        ),
    )


def _persist_incomplete_welfare_missing_social_weight(ctx: ExecutionContext):
    ge_ref = persist_ge_uncertainty_bundle(
        ctx.store,
        GEUncertaintyBundle(
            model_class="linearized_ge_io",
            representation=GEUncertaintyRepresentation.MULTIPLIER_INTERVALS,
            multiplier_shape=(1, 1),
        ),
    )
    return persist_welfare_bundle(
        ctx.store,
        WelfareBundle(
            welfare_measure="net_social_welfare",
            model_class="linearized_ge_io",
            ge_multiplier_semantics="leontief_inverse",
            ge_uncertainty_ref=ge_ref,
            point_estimate=1.0,
            method_used=WelfareMethod.DETERMINISTIC,
            status=WelfareStatus.OK,
        ),
    )


def _persist_ambiguity(ctx: ExecutionContext, *, mode: str = "not_applicable"):
    return persist_optimization_ambiguity_certificate(
        ctx.store,
        build_optimization_ambiguity_certificate(
            {"mode": mode, "overall_status": "pass"},
            mode=mode,
            source_kind="test",
            overall_status="pass",
        ),
    )


def _persist_policy_spec(store: FileSystemCAS, policy: PolicySpec) -> ArtifactRef:
    artifact = store.put_json(
        _decimalize_floats(policy.model_dump(mode="python")),
        PutOptions(kind="ir.policy_spec", media_type="application/json"),
    )
    return ArtifactRef.model_validate(artifact.model_dump(mode="json"))


def _index_mechanism_sidecars(ctx: ExecutionContext, state: ExperimentState, result) -> None:
    certificate = load_ic_certificate(ctx.store, result.certificate_ref)
    state.artifacts_index["semantic_ic_certificate_ref"] = ArtifactRef.model_validate(
        result.certificate_ref.model_dump(mode="json")
    )
    state.artifacts_index["mechanism_ic_certificate_ref"] = ArtifactRef.model_validate(
        certificate.witness["mechanism_ic_certificate_ref"]
    )
    state.artifacts_index["mechanism_welfare_loss_bound_ref"] = ArtifactRef.model_validate(
        certificate.witness["mechanism_welfare_loss_bound_ref"]
    )


def _minimal_evaluation(candidate: PolicyCandidateSchema) -> PolicyEvaluationVector:
    return PolicyEvaluationVector(
        candidate_id=candidate.candidate_id,
        primary={
            "welfare": ObjectiveChannelValue(
                name="welfare",
                kind=ObjectiveKind.PRIMARY,
                value=1.0,
                direction=ObjectiveDirection.MAXIMIZE,
            )
        },
        feasible=True,
    )


def _minimal_readiness(gate) -> DecisionReadinessContract:
    return DecisionReadinessContract(
        readiness_level=DecisionReadiness.RECOMMENDATION_READY,
        required_judges_passed=["structural"],
        required_uncertainty_bounds={},
        mandatory_human_gate=False,
        assumptions_must_be_surfaced=[],
        expiry_conditions=[],
        evidence_depth_required="replicated",
        phase3_gate=gate,
    )


def _minimal_brief() -> PolicyBrief:
    return PolicyBrief(
        title="Phase 3 acceptance brief",
        executive_summary="Synthetic acceptance bundle for Phase 3.",
        readiness_level=DecisionReadiness.RECOMMENDATION_READY.value,
    )


def _uncertainty(level: float = 0.1) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        uncertainties={
            uncertainty_type: UncertaintyEstimate(
                level=level,
                source="test",
                quantification_method="manual",
                is_reducible=True,
            )
            for uncertainty_type in UncertaintyType
        }
    )


def _build_bundle(ctx: ExecutionContext, candidate: PolicyCandidateSchema, gate):
    bundle_ref = PolicyArtifactBuilder().build(
        ctx.store,
        PolicyArtifactBuildInput(
            loop_id="phase3_acceptance",
            run_id=_run_id(ctx),
            candidate=candidate,
            candidate_hash=candidate.candidate_hash(),
            evaluation_vector=_minimal_evaluation(candidate),
            judge_verdict=JudgeVerdict(per_judge={}, composite_decision="promote"),
            readiness_contract=_minimal_readiness(gate),
            phase3_gate=gate,
            policy_brief=_minimal_brief(),
            translator_compliance=TranslatorComplianceResult(passed=True, findings=[]),
        ),
    )
    return load_policy_artifact_bundle(ctx.store, bundle_ref)


def _assert_refusal(ctx: ExecutionContext, candidate: PolicyCandidateSchema, gate) -> None:
    readiness = DecisionReadinessEvaluator().evaluate(
        candidate=candidate,
        judge_verdict=JudgeVerdict(per_judge={}, composite_decision="promote"),
        uncertainty_envelope=_uncertainty(),
        phase3_gate=gate,
    )
    assert readiness.readiness_level == DecisionReadiness.RESEARCH_ARTIFACT
    assert readiness.metadata["readiness_cap_reason"] == "phase3_gate_blocked"
    with pytest.raises(ValueError, match="Phase 3"):
        _build_bundle(ctx, candidate, gate)


def test_phase3_acceptance_non_mechanism_recommendation_flow(tmp_path) -> None:
    ctx = _ctx(tmp_path, run_id="R_phase3_accept_non_mech")
    candidate = _candidate_from_policy(_non_mechanism_policy(), candidate_id="non_mech")
    welfare_ref = _persist_complete_welfare(ctx)
    ambiguity_ref = _persist_ambiguity(ctx)
    state = ExperimentState(
        run_id=_run_id(ctx),
        artifacts_index={
            "welfare_bundle_ref": ArtifactRef.model_validate(welfare_ref.model_dump(mode="json")),
            "ambiguity_certificate_ref": ArtifactRef.model_validate(
                ambiguity_ref.model_dump(mode="json")
            ),
        },
    )

    gate = resolve_phase3_gate(ctx, state, candidate=candidate)
    bundle = _build_bundle(ctx, candidate, gate)

    assert gate.gate_passed is True
    assert gate.mechanism_required is False
    assert bundle.phase3_gate.gate_passed is True
    assert bundle.welfare_bundle_ref == gate.welfare_bundle_ref
    assert bundle.ambiguity_certificate_ref == gate.ambiguity_certificate_ref
    assert bundle.mechanism_ic_certificate_ref is None


def test_phase3_acceptance_tax_family_recommendation_flow(tmp_path) -> None:
    ctx = _ctx(tmp_path, run_id="R_phase3_accept_tax")
    policy = _tax_policy()
    candidate = _candidate_from_policy(policy, candidate_id="tax_family")
    policy_ref = _persist_policy_spec(ctx.store, policy)
    result = verify_incentive_compatibility(
        ctx.store,
        ICVerificationRequest(property="bayesian_ic", input_ref=policy_ref),
    )
    welfare_ref = _persist_complete_welfare(ctx)
    ambiguity_ref = _persist_ambiguity(ctx)
    state = ExperimentState(
        run_id=_run_id(ctx),
        artifacts_index={
            "welfare_bundle_ref": ArtifactRef.model_validate(welfare_ref.model_dump(mode="json")),
            "ambiguity_certificate_ref": ArtifactRef.model_validate(
                ambiguity_ref.model_dump(mode="json")
            ),
        },
    )
    _index_mechanism_sidecars(ctx, state, result)

    gate = resolve_phase3_gate(ctx, state, candidate=candidate)
    bundle = _build_bundle(ctx, candidate, gate)

    assert gate.gate_passed is True
    assert gate.mechanism_required is True
    assert gate.semantic_ic_certificate_ref is not None
    assert gate.mechanism_ic_certificate_ref is not None
    assert gate.mechanism_welfare_loss_bound_ref is not None
    assert bundle.semantic_ic_certificate_ref == gate.semantic_ic_certificate_ref
    assert bundle.mechanism_ic_certificate_ref == gate.mechanism_ic_certificate_ref
    assert bundle.mechanism_welfare_loss_bound_ref == gate.mechanism_welfare_loss_bound_ref


def test_phase3_acceptance_license_family_recommendation_flow(tmp_path) -> None:
    ctx = _ctx(tmp_path, run_id="R_phase3_accept_license")
    policy = _license_policy()
    candidate = _candidate_from_policy(policy, candidate_id="license_family")
    policy_ref = _persist_policy_spec(ctx.store, policy)
    result = verify_incentive_compatibility(
        ctx.store,
        ICVerificationRequest(property="dominant_strategy_ic", input_ref=policy_ref),
    )
    welfare_ref = _persist_complete_welfare(ctx)
    ambiguity_ref = _persist_ambiguity(ctx)
    state = ExperimentState(
        run_id=_run_id(ctx),
        artifacts_index={
            "welfare_bundle_ref": ArtifactRef.model_validate(welfare_ref.model_dump(mode="json")),
            "ambiguity_certificate_ref": ArtifactRef.model_validate(
                ambiguity_ref.model_dump(mode="json")
            ),
        },
    )
    _index_mechanism_sidecars(ctx, state, result)

    gate = resolve_phase3_gate(ctx, state, candidate=candidate)
    bundle = _build_bundle(ctx, candidate, gate)

    assert gate.gate_passed is True
    assert gate.mechanism_required is True
    assert gate.mechanism_welfare_loss_bound_ref is not None
    assert bundle.mechanism_welfare_loss_bound_ref == gate.mechanism_welfare_loss_bound_ref


def test_phase3_acceptance_refusal_welfare_missing(tmp_path) -> None:
    ctx = _ctx(tmp_path, run_id="R_phase3_refuse_welfare")
    candidate = _candidate_from_policy(_non_mechanism_policy(), candidate_id="welfare_missing")
    state = ExperimentState(
        run_id=_run_id(ctx),
        artifacts_index={
            "ambiguity_certificate_ref": ArtifactRef.model_validate(
                _persist_ambiguity(ctx).model_dump(mode="json")
            )
        },
    )

    gate = resolve_phase3_gate(ctx, state, candidate=candidate)

    assert "phase3.welfare_missing" in gate.blocking_reasons
    _assert_refusal(ctx, candidate, gate)


def test_phase3_acceptance_refusal_social_weight_missing(tmp_path) -> None:
    ctx = _ctx(tmp_path, run_id="R_phase3_refuse_social_weight")
    candidate = _candidate_from_policy(
        _non_mechanism_policy(), candidate_id="social_weight_missing"
    )
    state = ExperimentState(
        run_id=_run_id(ctx),
        artifacts_index={
            "welfare_bundle_ref": ArtifactRef.model_validate(
                _persist_incomplete_welfare_missing_social_weight(ctx).model_dump(mode="json")
            ),
            "ambiguity_certificate_ref": ArtifactRef.model_validate(
                _persist_ambiguity(ctx).model_dump(mode="json")
            ),
        },
    )

    gate = resolve_phase3_gate(ctx, state, candidate=candidate)

    assert "phase3.social_weight_missing" in gate.blocking_reasons
    _assert_refusal(ctx, candidate, gate)


def test_phase3_acceptance_refusal_ambiguity_missing_on_dro_path(tmp_path) -> None:
    ctx = _ctx(tmp_path, run_id="R_phase3_refuse_ambiguity")
    candidate = _candidate_from_policy(_non_mechanism_policy(), candidate_id="ambiguity_missing")
    state = ExperimentState(
        run_id=_run_id(ctx),
        artifacts_index={
            "welfare_bundle_ref": ArtifactRef.model_validate(
                _persist_complete_welfare(ctx).model_dump(mode="json")
            )
        },
        params={"moment_dro_result": {"objective_value": 1.0}},
    )

    gate = resolve_phase3_gate(ctx, state, candidate=candidate)

    assert "phase3.ambiguity_missing" in gate.blocking_reasons
    _assert_refusal(ctx, candidate, gate)


def test_phase3_acceptance_refusal_mechanism_welfare_bound_missing(tmp_path) -> None:
    ctx = _ctx(tmp_path, run_id="R_phase3_refuse_mechanism_bound")
    policy = _tax_policy()
    candidate = _candidate_from_policy(policy, candidate_id="mechanism_bound_missing")
    policy_ref = _persist_policy_spec(ctx.store, policy)
    result = verify_incentive_compatibility(
        ctx.store,
        ICVerificationRequest(property="bayesian_ic", input_ref=policy_ref),
    )
    welfare_ref = _persist_complete_welfare(ctx)
    ambiguity_ref = _persist_ambiguity(ctx)
    state = ExperimentState(
        run_id=_run_id(ctx),
        artifacts_index={
            "welfare_bundle_ref": ArtifactRef.model_validate(welfare_ref.model_dump(mode="json")),
            "ambiguity_certificate_ref": ArtifactRef.model_validate(
                ambiguity_ref.model_dump(mode="json")
            ),
        },
    )
    _index_mechanism_sidecars(ctx, state, result)
    state.artifacts_index.pop("mechanism_welfare_loss_bound_ref")

    gate = resolve_phase3_gate(ctx, state, candidate=candidate)

    assert "phase3.mechanism_welfare_bound_missing" in gate.blocking_reasons
    _assert_refusal(ctx, candidate, gate)


def test_phase3_acceptance_refusal_fiscal_feedback_missing(tmp_path) -> None:
    ctx = _ctx(tmp_path, run_id="R_phase3_refuse_fiscal_feedback")
    candidate = _candidate_from_policy(
        _non_mechanism_policy(), candidate_id="fiscal_feedback_missing"
    )
    welfare_ref = _persist_complete_welfare(ctx)
    ambiguity_ref = _persist_ambiguity(ctx)
    state = ExperimentState(
        run_id=_run_id(ctx),
        artifacts_index={
            "welfare_bundle_ref": ArtifactRef.model_validate(welfare_ref.model_dump(mode="json")),
            "ambiguity_certificate_ref": ArtifactRef.model_validate(
                ambiguity_ref.model_dump(mode="json")
            ),
        },
        params={
            "require_phase3_fiscal_feedback": True,
            "microsim_result": MicrosimResult(
                disposable_income=[10.0],
                tax_liability=[1.0],
                benefit_income=[0.0],
                weighted_mean_disposable_income=10.0,
                weighted_gini=0.1,
                policy_revenue=1.0,
            ).model_dump(mode="json"),
        },
    )

    gate = resolve_phase3_gate(ctx, state, candidate=candidate)

    assert "phase3.fiscal_feedback_missing" in gate.blocking_reasons
    _assert_refusal(ctx, candidate, gate)


def test_phase3_acceptance_refusal_forged_gate_blocked_at_final_bundle(tmp_path) -> None:
    ctx = _ctx(tmp_path, run_id="R_phase3_refuse_forged_gate")
    candidate = _candidate_from_policy(_non_mechanism_policy(), candidate_id="forged_gate")

    with pytest.raises(ValueError, match="Phase 3"):
        _build_bundle(
            ctx,
            candidate,
            {
                "gate_passed": True,
            },
        )
