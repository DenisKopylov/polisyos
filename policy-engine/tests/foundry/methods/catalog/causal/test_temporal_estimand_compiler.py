from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal.protocols import (
    DynamicTreatmentData,
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
    TemporalSamplingScheme,
    TemporalInterventionTrajectory,
    TemporalTargetFunctional,
)
from polisyos.ir.refs import ArtifactRefModel


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
            state[:, t + 1] = 0.6 * state[:, t] + 0.4 * treatment[:, t] + rng.normal(
                0.0,
                0.2,
                size=n_units,
            )
    outcome = state[:, -1] + treatment.sum(axis=1)
    return DynamicTreatmentData(
        outcome=outcome,
        treatment_sequence=treatment,
        covariate_sequence=state[:, :, np.newaxis],
        time_ids=np.array([0.0, 1.0, 2.0, 3.0], dtype=float),
        variable_names=["state"],
    )


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


def test_neural_backend_is_research_gated() -> None:
    with pytest.raises(TemporalCompileError) as exc_info:
        compile_temporal_estimand(
            _query(horizon_end=3.0, metadata={"preferred_backend": "neural_sde"}),
            data=_dynamic_data(),
            resolved_intervention=_intervention(horizon_end=3.0),
        )

    assert exc_info.value.reason_code == "research_gated_backend"


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
