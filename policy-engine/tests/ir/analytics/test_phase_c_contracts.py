from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.dynamic_regime import (
    ContinuousTimeQuery,
    DynamicTreatmentRegime,
    EffectTrajectoryBundle,
    InterventionInterpolationPolicy,
    RegimeRule,
    RuntimeSupportStatus,
    StrategicAdaptationMode,
    TemporalInterventionTrajectory,
    TemporalPathRepresentation,
    TemporalQueryMode,
    TemporalSamplingScheme,
    TemporalTargetFunctional,
    load_continuous_time_query,
    load_dynamic_treatment_regime,
    load_effect_trajectory_bundle,
    load_temporal_intervention_trajectory,
    persist_continuous_time_query,
    persist_dynamic_treatment_regime,
    persist_effect_trajectory_bundle,
    persist_temporal_intervention_trajectory,
)
from polisyos.ir.refs import (
    ArtifactRefModel,
    ContinuousTimeQueryRef,
    DynamicTreatmentRegimeRef,
    EffectTrajectoryBundleRef,
    TemporalInterventionTrajectoryRef,
)


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
    sampling_scheme: TemporalSamplingScheme = TemporalSamplingScheme.REGULAR_GRID,
    time_scale: str = "days",
    horizon_start: float = 0.0,
    horizon_end: float = 30.0,
) -> ContinuousTimeQuery:
    return ContinuousTimeQuery(
        intervention_trajectory_ref=_artifact_ref("a", kind="test.intervention_trajectory"),
        outcome_process="employment_rate",
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        target_functional=TemporalTargetFunctional.EFFECT_PATH,
        sampling_scheme=sampling_scheme,
        time_scale=time_scale,
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
    )


def _bundle(
    *,
    query_ref: ContinuousTimeQueryRef | None = None,
    path_representation: TemporalPathRepresentation = TemporalPathRepresentation.LINEAR_SDE,
    discretization_error: float | None = 0.05,
    discretization_note: str | None = None,
    continuous_time_degraded: bool = False,
) -> EffectTrajectoryBundle:
    return EffectTrajectoryBundle(
        query_ref=query_ref or ContinuousTimeQueryRef(artifact_id=_artifact_id("b")),
        trajectory_ref=_artifact_ref("c", kind="test.trajectory"),
        confidence_band_ref=_artifact_ref("d", kind="test.confidence_band"),
        solver_diagnostics_ref=_artifact_ref("e", kind="test.solver_diagnostics"),
        discretization_error=discretization_error,
        discretization_note=discretization_note,
        path_representation=path_representation,
        solver_family="euler_maruyama",
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        strategic_adaptation_mode=StrategicAdaptationMode.ABSENT,
        continuous_time_degraded=continuous_time_degraded,
    )


def _intervention() -> TemporalInterventionTrajectory:
    return TemporalInterventionTrajectory(
        time_points=(0.0, 10.0, 20.0, 30.0),
        values=(0.0, 1.0, 1.0, 1.0),
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
    )


def test_continuous_time_query_accepts_regular_grid_contract() -> None:
    query = _query()

    assert query.target_functional is TemporalTargetFunctional.EFFECT_PATH
    assert query.interpolation_policy is InterventionInterpolationPolicy.PIECEWISE_CONSTANT
    assert query.is_research_gated is False
    assert query.runtime_eligible is True
    assert query.runtime_support_status is RuntimeSupportStatus.SUPPORTED


def test_continuous_time_query_rejects_invalid_horizon_and_blank_time_scale() -> None:
    with pytest.raises(ValidationError, match="horizon_start must be strictly less than horizon_end"):
        _query(horizon_start=5.0, horizon_end=5.0)

    with pytest.raises(ValidationError, match="string fields must be non-empty"):
        _query(time_scale="   ")

    with pytest.raises(ValidationError, match="intervention_trajectory_ref is required"):
        ContinuousTimeQuery(
            outcome_process="employment_rate",
            horizon_start=0.0,
            horizon_end=30.0,
            time_scale="days",
            interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        )


def test_optimal_policy_query_mode_does_not_require_fixed_intervention_ref() -> None:
    query = ContinuousTimeQuery(
        query_mode=TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY,
        outcome_process="employment_rate",
        horizon_start=0.0,
        horizon_end=30.0,
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
    )

    assert query.intervention_trajectory_ref is None
    assert query.query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY


def test_effect_trajectory_bundle_requires_band_and_finite_diagnostics_surface() -> None:
    with pytest.raises(ValidationError, match="confidence_band_ref"):
        EffectTrajectoryBundle(
            query_ref=ContinuousTimeQueryRef(artifact_id=_artifact_id("b")),
            trajectory_ref=_artifact_ref("c", kind="test.trajectory"),
            solver_diagnostics_ref=_artifact_ref("e", kind="test.solver_diagnostics"),
            discretization_error=0.05,
            path_representation=TemporalPathRepresentation.LINEAR_SDE,
            solver_family="rk4",
            time_scale="days",
            interpolation_policy=InterventionInterpolationPolicy.LINEAR,
            strategic_adaptation_mode=StrategicAdaptationMode.ABSENT,
        )

    with pytest.raises(ValidationError, match="discretization_error"):
        _bundle(discretization_error=float("inf"))


def test_phase_c_contracts_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    query = _query()
    intervention = _intervention()
    regime = DynamicTreatmentRegime(
        time_points=(0, 1, 2),
        treatment_variables=("A_0", "A_1", "A_2"),
        time_varying_covariates=("state",),
        outcome="Y",
        rule=RegimeRule.THRESHOLD,
        threshold_value=0.2,
    )

    intervention_ref = persist_temporal_intervention_trajectory(store, intervention)
    query_ref = persist_continuous_time_query(store, query)
    regime_ref = persist_dynamic_treatment_regime(store, regime)
    bundle = _bundle(query_ref=query_ref)
    bundle_ref = persist_effect_trajectory_bundle(store, bundle)

    assert isinstance(intervention_ref, TemporalInterventionTrajectoryRef)
    assert isinstance(query_ref, ContinuousTimeQueryRef)
    assert isinstance(regime_ref, DynamicTreatmentRegimeRef)
    assert isinstance(bundle_ref, EffectTrajectoryBundleRef)
    assert load_temporal_intervention_trajectory(store, intervention_ref) == intervention
    assert load_continuous_time_query(store, query_ref) == query
    assert load_dynamic_treatment_regime(store, regime_ref) == regime
    assert load_effect_trajectory_bundle(store, bundle_ref) == bundle


def test_phase_c_research_gating_is_machine_readable() -> None:
    irregular_query = _query(sampling_scheme=TemporalSamplingScheme.IRREGULAR_GRID)
    neural_bundle = _bundle(path_representation=TemporalPathRepresentation.NEURAL_SDE)

    assert irregular_query.is_research_gated is True
    assert irregular_query.runtime_eligible is False
    assert neural_bundle.is_research_gated is True
    assert neural_bundle.runtime_eligible is False


def test_discrete_fallback_bundle_requires_truthful_disclosure() -> None:
    bundle = _bundle(
        path_representation=TemporalPathRepresentation.DISCRETE_REPLAY,
        discretization_error=None,
        discretization_note="unavailable_under_discrete_fallback",
        continuous_time_degraded=True,
    )

    assert bundle.runtime_support_status is RuntimeSupportStatus.DEGRADED
    assert bundle.runtime_eligible is True

    with pytest.raises(ValidationError, match="must not claim a numeric discretization_error"):
        _bundle(
            path_representation=TemporalPathRepresentation.DISCRETE_REPLAY,
            discretization_error=0.0,
            discretization_note="unavailable_under_discrete_fallback",
            continuous_time_degraded=True,
        )
