from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.catalog.causal.protocols import (
    DynamicTreatmentData,
    EventProcessObservationalData,
    PanelObservationalData,
)
from polisyos.foundry.methods.catalog.causal.temporal_estimand_compiler import (
    TemporalBackendTarget,
    TemporalComparatorSemantics,
    TemporalCompileError,
    TemporalFallbackMode,
    compile_temporal_estimand,
)
from polisyos.ir.analytics.dynamic_regime import (
    ContinuousTimeQuery,
    InterventionInterpolationPolicy,
    TemporalIdentificationCertificate,
    TemporalIdentificationTheoremFamily,
    TemporalInterventionSemantics,
    TemporalInterventionTrajectory,
    TemporalLawObject,
    TemporalObservabilityRegime,
    TemporalSamplingScheme,
    TemporalTargetFunctional,
)
from polisyos.ir.analytics.rough_path_semantics import (
    PathLiftMethod,
    RoughPathGraphCriterion,
    RoughPathIdentificationStatus,
    RoughPathIdentificationStrategy,
    RoughPathInterventionCertificate,
    RoughPathInterventionType,
    RoughPathModelFamily,
    RoughPathTopology,
    TemporalPathSemanticsAttachment,
    TemporalPathSemanticsScope,
)
from polisyos.ir.registry.refs import ArtifactRefModel, RoughPathInterventionCertificateRef


def _artifact_id(ch: str) -> str:
    return f"sha256:{ch * 64}"


def _artifact_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=_artifact_id(ch),
        kind=kind,
        media_type="application/json",
    )


def _query(
    *,
    horizon_end: float,
    target_functional: TemporalTargetFunctional = TemporalTargetFunctional.EFFECT_PATH,
    sampling_scheme: TemporalSamplingScheme = TemporalSamplingScheme.REGULAR_GRID,
    metadata: dict[str, object] | None = None,
) -> ContinuousTimeQuery:
    return ContinuousTimeQuery(
        intervention_trajectory_ref=_artifact_ref("a", kind="test.intervention_trajectory"),
        outcome_process="state",
        horizon_start=0.0,
        horizon_end=horizon_end,
        target_functional=target_functional,
        sampling_scheme=sampling_scheme,
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        metadata=dict(metadata or {}),
    )


def _intervention(
    *,
    horizon_end: float,
    values: tuple[float, ...] | None = None,
    interpolation_policy: InterventionInterpolationPolicy = InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
) -> TemporalInterventionTrajectory:
    n_points = int(horizon_end) + 1
    schedule = values or tuple(1.0 for _ in range(n_points))
    return TemporalInterventionTrajectory(
        time_points=tuple(float(index) for index in range(n_points)),
        values=schedule,
        time_scale="days",
        interpolation_policy=interpolation_policy,
    )


def _certificate(
    *,
    theorem_family: TemporalIdentificationTheoremFamily = (
        TemporalIdentificationTheoremFamily.NSDE_FIXED_OBSERVED_CHANNEL_V1
    ),
) -> TemporalIdentificationCertificate:
    if theorem_family is TemporalIdentificationTheoremFamily.LOCAL_INDEPENDENCE_WEIGHTING_V1:
        return TemporalIdentificationCertificate(
            theorem_family=theorem_family,
            identified_functionals=(
                TemporalTargetFunctional.CUMULATIVE_INCIDENCE,
                TemporalTargetFunctional.SURVIVAL_CURVE,
            ),
            intervention_semantics=TemporalInterventionSemantics.INTENSITY_REPLACEMENT,
            observability_regime=TemporalObservabilityRegime.OBSERVED_FILTRATION,
            law_object=TemporalLawObject.INTENSITY_COMPENSATOR,
            assumptions=("causal_validity_intensity_replacement", "independent_censoring_local"),
        )
    if theorem_family is TemporalIdentificationTheoremFamily.NCDE_FIXED_OBSERVED_CHANNEL_V1:
        return TemporalIdentificationCertificate(
            theorem_family=theorem_family,
            identified_functionals=(
                TemporalTargetFunctional.EFFECT_PATH,
                TemporalTargetFunctional.INTEGRAL_EFFECT,
            ),
            intervention_semantics=TemporalInterventionSemantics.SURGICAL_REPLACEMENT,
            observability_regime=TemporalObservabilityRegime.FULL_STATE,
            law_object=TemporalLawObject.CANONICAL_CONTROL_PATH,
            canonical_control_required=True,
            control_canonicalization=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
            assumptions=("full_state_observability", "canonical_control_path"),
        )
    return TemporalIdentificationCertificate(
        theorem_family=theorem_family,
        identified_functionals=(
            TemporalTargetFunctional.EFFECT_PATH,
            TemporalTargetFunctional.INTEGRAL_EFFECT,
        ),
        intervention_semantics=TemporalInterventionSemantics.SURGICAL_REPLACEMENT,
        observability_regime=TemporalObservabilityRegime.FULL_STATE,
        law_object=TemporalLawObject.SEMIMARTINGALE_CHARACTERISTICS,
        assumptions=("full_state_observability", "weak_uniqueness_after_intervention"),
    )


def _panel_data() -> PanelObservationalData:
    outcome = np.array(
        [
            [0.0, 0.1, 0.2, 1.8],
            [0.0, 0.1, 0.2, 0.3],
            [0.1, 0.0, 0.2, 0.4],
        ],
        dtype=float,
    )
    return PanelObservationalData(
        outcome=outcome,
        treatment=np.array([1, 0, 0], dtype=int),
        time_treatment=3,
        time_index=np.array([0.0, 1.0, 2.0, 3.0], dtype=float),
    )


def _dynamic_data() -> DynamicTreatmentData:
    rng = np.random.default_rng(7)
    n_units, n_periods = 40, 4
    state = np.zeros((n_units, n_periods), dtype=float)
    treatment = np.zeros((n_units, n_periods), dtype=int)
    state[:, 0] = rng.normal(size=n_units)
    for t in range(n_periods):
        treatment[:, t] = rng.binomial(1, 0.5, size=n_units)
        if t < n_periods - 1:
            state[:, t + 1] = (
                0.6 * state[:, t]
                + 0.4 * treatment[:, t]
                + rng.normal(
                    0.0,
                    0.2,
                    size=n_units,
                )
            )
    outcome = state[:, -1] + treatment.sum(axis=1)
    return DynamicTreatmentData(
        outcome=outcome,
        treatment_sequence=treatment,
        covariate_sequence=state[:, :, np.newaxis],
        time_ids=np.array([0.0, 1.0, 2.0, 3.0], dtype=float),
        variable_names=["state"],
    )


def _irregular_dynamic_data() -> DynamicTreatmentData:
    return _dynamic_data().model_copy(
        update={"time_ids": np.array([0.0, 1.0, 2.5, 4.0], dtype=float)}
    )


def _event_process_data() -> EventProcessObservationalData:
    outcome_events = np.array(
        [
            [0, 0, 1, 0],
            [0, 1, 0, 0],
            [0, 0, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 1],
        ],
        dtype=int,
    )
    policy_weights = np.array(
        [
            [1.0, 1.0, 1.8, 1.8],
            [1.0, 1.1, 1.1, 1.1],
            [1.0, 1.0, 1.0, 1.7],
            [1.0, 1.0, 1.6, 1.6],
            [1.0, 1.0, 1.0, 1.0],
            [1.0, 1.0, 1.0, 1.5],
        ],
        dtype=float,
    )
    baseline_weights = np.ones_like(policy_weights, dtype=float)
    return EventProcessObservationalData(
        outcome_events=outcome_events,
        censoring_events=np.zeros_like(outcome_events, dtype=int),
        policy_weights=policy_weights,
        baseline_weights=baseline_weights,
        time_index=np.array([0.0, 1.0, 2.5, 4.0], dtype=float),
        metadata={"time_scale": "days", "process_family": "event_log"},
    )


def _rough_path_certificate_ref(ch: str = "a") -> RoughPathInterventionCertificateRef:
    return RoughPathInterventionCertificateRef(artifact_id=_artifact_id(ch))


def _rough_path_certificate(
    *,
    status: RoughPathIdentificationStatus = RoughPathIdentificationStatus.IDENTIFIED,
    semantics_scope: TemporalPathSemanticsScope = TemporalPathSemanticsScope.REPRESENTED_PATH,
) -> RoughPathInterventionCertificate:
    payload: dict[str, object] = {
        "semantics_scope": semantics_scope,
        "model_family": RoughPathModelFamily.HYBRID_RDE,
        "topology": RoughPathTopology.P_VARIATION,
        "graph_criterion": RoughPathGraphCriterion.DELTA_SEP,
        "observation_operator_ref": _artifact_ref("b", kind="test.observation_operator"),
        "lift_operator_ref": _artifact_ref("c", kind="test.lift_operator"),
        "interpolation_is_adapted": True,
        "future_leakage_ruled_out": True,
        "intervention_type": RoughPathInterventionType.POLICY_OVERRIDE,
        "intervention_operator_ref": _artifact_ref("d", kind="test.intervention_operator"),
        "actuatable_component": "state",
        "filtration_ref": _artifact_ref("e", kind="test.filtration"),
        "well_posedness_ref": _artifact_ref("f", kind="test.well_posedness"),
        "identification_strategy": RoughPathIdentificationStrategy.CONTINUOUS_TIME_G_FORMULA,
        "positivity_ref": _artifact_ref("1", kind="test.positivity"),
        "sampling_ignorability_ref": _artifact_ref("2", kind="test.sampling_ignorability"),
        "target_functional_ref": _artifact_ref("3", kind="test.target_functional"),
        "proof_trace_ref": _artifact_ref("4", kind="test.proof_trace"),
        "status": status,
    }
    if semantics_scope is TemporalPathSemanticsScope.LATENT_PATH:
        payload["lift_faithfulness_ref"] = _artifact_ref("5", kind="test.lift_faithfulness")
    return RoughPathInterventionCertificate.model_validate(payload)


def _rough_path_attachment(
    *,
    semantics_scope: TemporalPathSemanticsScope = TemporalPathSemanticsScope.REPRESENTED_PATH,
    lift_method: PathLiftMethod = PathLiftMethod.LEAD_LAG,
) -> TemporalPathSemanticsAttachment:
    payload: dict[str, object] = {
        "semantics_scope": semantics_scope,
        "lift_method": lift_method,
        "topology": RoughPathTopology.P_VARIATION,
        "p_variation_order": 2.0,
        "interpolation_is_adapted": True,
        "future_leakage_ruled_out": True,
        "intervention_type": RoughPathInterventionType.POLICY_OVERRIDE,
        "graph_criterion": RoughPathGraphCriterion.DELTA_SEP,
        "proof_artifact_ref": _rough_path_certificate_ref().model_dump(mode="json"),
        "sampling_ignorability_checked": True,
        "lift_faithfulness_checked": semantics_scope is TemporalPathSemanticsScope.LATENT_PATH,
    }
    if lift_method is PathLiftMethod.LOGSIGNATURE:
        payload["signature_level"] = 4
    return TemporalPathSemanticsAttachment.model_validate(payload)


def test_panel_query_compiles_to_linear_sde_plan() -> None:
    plan = compile_temporal_estimand(
        _query(horizon_end=3.0),
        data=_panel_data(),
        resolved_intervention=_intervention(horizon_end=3.0, values=(0.0, 0.0, 0.0, 1.0)),
    )

    assert plan.backend_target is TemporalBackendTarget.LINEAR_SDE
    assert plan.fallback_mode is TemporalFallbackMode.NONE
    assert plan.comparator_semantics is TemporalComparatorSemantics.UNTREATED_COUNTERFACTUAL
    assert plan.time_grid == (0.0, 1.0, 2.0, 3.0)


def test_dynamic_query_compiles_to_ode_plan_when_requested() -> None:
    plan = compile_temporal_estimand(
        _query(horizon_end=3.0, metadata={"preferred_backend": "ode"}),
        data=_dynamic_data(),
        resolved_intervention=_intervention(horizon_end=3.0),
    )

    assert plan.backend_target is TemporalBackendTarget.ODE
    assert plan.comparator_semantics is TemporalComparatorSemantics.NEVER_TREAT_BASELINE


def test_event_process_query_compiles_to_weighting_plan() -> None:
    plan = compile_temporal_estimand(
        _query(
            horizon_end=4.0,
            target_functional=TemporalTargetFunctional.CUMULATIVE_INCIDENCE,
            sampling_scheme=TemporalSamplingScheme.IRREGULAR_GRID,
            metadata={
                "preferred_backend": "event_process_weighting",
                "process_family": "event_log",
            },
        ),
        data=_event_process_data(),
        resolved_intervention=_intervention(horizon_end=4.0, values=(0.0, 0.0, 1.0, 1.0, 1.0)),
        identification_certificate=_certificate(
            theorem_family=TemporalIdentificationTheoremFamily.LOCAL_INDEPENDENCE_WEIGHTING_V1
        ),
    )

    assert plan.backend_target is TemporalBackendTarget.EVENT_PROCESS_WEIGHTING
    assert plan.comparator_semantics is TemporalComparatorSemantics.POLICY_BASELINE
    assert plan.time_grid == (0.0, 1.0, 2.5, 4.0)


def test_unsupported_target_functional_has_reason_code() -> None:
    with pytest.raises(TemporalCompileError) as exc_info:
        compile_temporal_estimand(
            _query(
                horizon_end=3.0,
                target_functional=TemporalTargetFunctional.TIME_TO_THRESHOLD,
            ),
            data=_panel_data(),
            resolved_intervention=_intervention(horizon_end=3.0, values=(0.0, 0.0, 0.0, 1.0)),
        )

    assert exc_info.value.reason_code == "unsupported_target_functional"


def test_irregular_sampling_is_research_gated() -> None:
    with pytest.raises(TemporalCompileError) as exc_info:
        compile_temporal_estimand(
            _query(
                horizon_end=3.0,
                sampling_scheme=TemporalSamplingScheme.IRREGULAR_GRID,
            ),
            data=_panel_data(),
            resolved_intervention=_intervention(horizon_end=3.0, values=(0.0, 0.0, 0.0, 1.0)),
        )

    assert exc_info.value.reason_code == "research_gated_sampling_scheme"


def test_irregular_sampling_compiles_to_geometric_rough_path_when_certified() -> None:
    query = _query(
        horizon_end=4.0,
        sampling_scheme=TemporalSamplingScheme.IRREGULAR_GRID,
        metadata={
            "preferred_backend": "geometric_rough_path",
            "path_semantics": _rough_path_attachment().model_dump(mode="json"),
            "rough_path_certificate": _rough_path_certificate().model_dump(mode="json"),
        },
    )

    plan = compile_temporal_estimand(
        query,
        data=_irregular_dynamic_data(),
        resolved_intervention=_intervention(horizon_end=4.0, values=(0.0, 0.0, 0.0, 1.0, 1.0)),
    )

    assert query.runtime_support_status.value == "supported"
    assert plan.backend_target is TemporalBackendTarget.GEOMETRIC_ROUGH_PATH
    assert plan.time_grid == (0.0, 1.0, 2.5, 4.0)
    assert plan.metadata["path_semantics"]["semantics_scope"] == "represented_path"
    assert plan.metadata["rough_path_identification_status"] == "identified"


def test_irregular_sampling_representation_only_certificate_is_runtime_degraded() -> None:
    query = _query(
        horizon_end=4.0,
        sampling_scheme=TemporalSamplingScheme.IRREGULAR_GRID,
        metadata={
            "preferred_backend": "geometric_rough_path",
            "path_semantics": _rough_path_attachment().model_dump(mode="json"),
            "rough_path_certificate": _rough_path_certificate(
                status=RoughPathIdentificationStatus.IDENTIFIED_REPRESENTATION_ONLY
            ).model_dump(mode="json"),
        },
    )

    plan = compile_temporal_estimand(
        query,
        data=_irregular_dynamic_data(),
        resolved_intervention=_intervention(horizon_end=4.0, values=(0.0, 0.0, 0.0, 1.0, 1.0)),
    )

    assert query.runtime_support_status.value == "degraded"
    assert query.runtime_eligible is True
    assert plan.backend_target is TemporalBackendTarget.GEOMETRIC_ROUGH_PATH
    assert plan.metadata["rough_path_runtime_support"] == "degraded"


def test_irregular_sampling_blocked_when_rough_path_certificate_is_blocked() -> None:
    query = _query(
        horizon_end=4.0,
        sampling_scheme=TemporalSamplingScheme.IRREGULAR_GRID,
        metadata={
            "preferred_backend": "geometric_rough_path",
            "path_semantics": _rough_path_attachment().model_dump(mode="json"),
            "rough_path_certificate": _rough_path_certificate(
                status=RoughPathIdentificationStatus.BLOCKED
            ).model_dump(mode="json"),
        },
    )

    with pytest.raises(TemporalCompileError) as exc_info:
        compile_temporal_estimand(
            query,
            data=_irregular_dynamic_data(),
            resolved_intervention=_intervention(horizon_end=4.0, values=(0.0, 0.0, 0.0, 1.0, 1.0)),
        )

    assert query.runtime_support_status.value == "blocked_unsupported"
    assert exc_info.value.reason_code == "blocked_rough_path_identification"


def test_neural_backend_is_research_gated() -> None:
    with pytest.raises(TemporalCompileError) as exc_info:
        compile_temporal_estimand(
            _query(horizon_end=3.0, metadata={"preferred_backend": "neural_sde"}),
            data=_dynamic_data(),
            resolved_intervention=_intervention(horizon_end=3.0),
        )

    assert exc_info.value.reason_code == "research_gated_backend"


def test_neural_backend_rejects_out_of_scope_identification_certificate() -> None:
    with pytest.raises(TemporalCompileError) as exc_info:
        compile_temporal_estimand(
            _query(horizon_end=3.0, metadata={"preferred_backend": "neural_sde"}),
            data=_dynamic_data(),
            resolved_intervention=_intervention(horizon_end=3.0),
            identification_certificate=_certificate(
                theorem_family=TemporalIdentificationTheoremFamily.NCDE_FIXED_OBSERVED_CHANNEL_V1
            ),
        )

    assert exc_info.value.reason_code == "unsupported_identification_scope"


def test_neural_backend_compiles_with_supported_identification_scope() -> None:
    plan = compile_temporal_estimand(
        _query(horizon_end=3.0, metadata={"preferred_backend": "neural_sde"}),
        data=_dynamic_data(),
        resolved_intervention=_intervention(horizon_end=3.0),
        identification_certificate=_certificate(),
    )

    assert plan.backend_target is TemporalBackendTarget.NEURAL_SDE
    assert plan.solver_config["solver_family"] == "law_invariant_nsde"
    assert plan.metadata["identification_scope"]["theorem_family"] == (
        TemporalIdentificationTheoremFamily.NSDE_FIXED_OBSERVED_CHANNEL_V1.value
    )
    assert plan.metadata["identification_support_status"] == "on_support"


def test_neural_cde_backend_requires_matching_canonical_control() -> None:
    with pytest.raises(TemporalCompileError) as exc_info:
        compile_temporal_estimand(
            _query(
                horizon_end=3.0,
                metadata={"preferred_backend": "neural_cde"},
            ).model_copy(update={"interpolation_policy": InterventionInterpolationPolicy.LINEAR}),
            data=_dynamic_data(),
            resolved_intervention=_intervention(
                horizon_end=3.0,
                interpolation_policy=InterventionInterpolationPolicy.LINEAR,
            ),
            identification_certificate=_certificate(
                theorem_family=TemporalIdentificationTheoremFamily.NCDE_FIXED_OBSERVED_CHANNEL_V1
            ),
        )

    assert exc_info.value.reason_code == "unsupported_identification_scope"


def test_horizon_mismatch_triggers_explicit_discrete_fallback() -> None:
    plan = compile_temporal_estimand(
        _query(horizon_end=2.5),
        data=_dynamic_data(),
        resolved_intervention=_intervention(horizon_end=3.0),
    )

    assert plan.backend_target is TemporalBackendTarget.DISCRETE_FALLBACK
    assert plan.fallback_mode is TemporalFallbackMode.DISCRETE_TIME
    assert plan.metadata["fallback_reason_code"] == "horizon_not_on_grid"


def test_time_scale_mismatch_is_rejected_machine_readably() -> None:
    with pytest.raises(TemporalCompileError) as exc_info:
        compile_temporal_estimand(
            _query(horizon_end=3.0),
            data=_dynamic_data(),
            resolved_intervention=TemporalInterventionTrajectory(
                time_points=(0.0, 1.0, 2.0, 3.0),
                values=(1.0, 1.0, 1.0, 1.0),
                time_scale="weeks",
                interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
            ),
        )

    assert exc_info.value.reason_code == "time_scale_mismatch"
