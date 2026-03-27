from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.catalog.causal.dtr import estimate_dtr_trajectory
from polisyos.foundry.methods.catalog.causal.g_computation import (
    estimate_g_computation_trajectory,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    DynamicTreatmentData,
    PanelObservationalData,
)
from polisyos.foundry.methods.catalog.causal.structural_time_series import (
    estimate_structural_time_series_trajectory,
    solve_temporal_effect_path,
)
from polisyos.foundry.methods.catalog.causal.temporal_estimand_compiler import (
    compile_temporal_estimand,
)
from polisyos.ir.analytics.dynamic_regime import (
    ContinuousTimeQuery,
    DynamicTreatmentRegime,
    InterventionInterpolationPolicy,
    RegimeRule,
    TemporalInterventionTrajectory,
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
    outcome_process: str,
    horizon_end: float,
    preferred_backend: str = "linear_sde",
) -> ContinuousTimeQuery:
    return ContinuousTimeQuery(
        intervention_trajectory_ref=_artifact_ref("a", kind="test.intervention_trajectory"),
        outcome_process=outcome_process,
        horizon_start=0.0,
        horizon_end=horizon_end,
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        metadata={"preferred_backend": preferred_backend},
    )


def _intervention(
    *,
    horizon_end: float,
    values: tuple[float, ...] | None = None,
) -> TemporalInterventionTrajectory:
    n_points = int(horizon_end) + 1
    return TemporalInterventionTrajectory(
        time_points=tuple(float(index) for index in range(n_points)),
        values=values or tuple(1.0 for _ in range(n_points)),
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
    )


def _panel_data() -> PanelObservationalData:
    rng = np.random.default_rng(11)
    n_donors, n_periods, t0 = 4, 6, 4
    donors = np.cumsum(rng.normal(0.0, 0.15, size=(n_donors, n_periods)), axis=1)
    treated = donors.mean(axis=0).copy()
    treated[t0:] += np.array([1.2, 1.5], dtype=float)
    return PanelObservationalData(
        outcome=np.vstack([treated, donors]),
        treatment=np.array([1] + [0] * n_donors, dtype=int),
        time_treatment=t0,
        time_index=np.arange(n_periods, dtype=float),
    )


def _dynamic_g_data() -> DynamicTreatmentData:
    rng = np.random.default_rng(21)
    n_units, n_periods = 220, 4
    state = np.zeros((n_units, n_periods), dtype=float)
    treatment = np.zeros((n_units, n_periods), dtype=int)
    state[:, 0] = rng.normal(size=n_units)

    def sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-x))

    for t in range(n_periods):
        treatment[:, t] = rng.binomial(1, sigmoid(0.5 * state[:, t]))
        if t < n_periods - 1:
            state[:, t + 1] = 0.5 * treatment[:, t] + 0.3 * state[:, t] + rng.normal(
                0.0,
                0.35,
                size=n_units,
            )

    outcome = treatment.sum(axis=1).astype(float) + state[:, 0] + rng.normal(0.0, 0.8, size=n_units)
    return DynamicTreatmentData(
        outcome=outcome,
        treatment_sequence=treatment,
        covariate_sequence=state[:, :, np.newaxis],
        time_ids=np.arange(n_periods, dtype=float),
        variable_names=["state"],
    )


def _dynamic_dtr_data() -> DynamicTreatmentData:
    rng = np.random.default_rng(31)
    n_units, n_periods = 260, 3
    state = np.zeros((n_units, n_periods), dtype=float)
    treatment = np.zeros((n_units, n_periods), dtype=int)
    state[:, 0] = rng.normal(size=n_units)

    for t in range(n_periods):
        treatment[:, t] = rng.integers(0, 2, size=n_units)
        if t < n_periods - 1:
            state[:, t + 1] = 0.45 * treatment[:, t] + 0.25 * state[:, t] + rng.normal(
                0.0,
                0.3,
                size=n_units,
            )

    outcome = 1.8 * treatment.sum(axis=1).astype(float) + state[:, 0] + rng.normal(
        0.0,
        0.5,
        size=n_units,
    )
    return DynamicTreatmentData(
        outcome=outcome,
        treatment_sequence=treatment,
        covariate_sequence=state[:, :, np.newaxis],
        time_ids=np.arange(n_periods, dtype=float),
        variable_names=["state"],
    )


def test_ode_and_linear_sde_match_when_diffusion_is_zero() -> None:
    panel = PanelObservationalData(
        outcome=np.vstack([np.linspace(0.0, 4.0, 5), np.zeros(5), np.zeros(5)]),
        treatment=np.array([1, 0, 0], dtype=int),
        time_treatment=3,
        time_index=np.arange(5, dtype=float),
    )
    linear_plan = compile_temporal_estimand(
        _query(outcome_process="panel_state", horizon_end=4.0, preferred_backend="linear_sde"),
        data=panel,
        resolved_intervention=_intervention(horizon_end=4.0, values=(0.0, 0.0, 0.0, 1.0, 1.0)),
    )
    ode_plan = compile_temporal_estimand(
        _query(outcome_process="panel_state", horizon_end=4.0, preferred_backend="ode"),
        data=panel,
        resolved_intervention=_intervention(horizon_end=4.0, values=(0.0, 0.0, 0.0, 1.0, 1.0)),
    )
    observed = np.linspace(0.0, 4.0, 5)
    baseline = np.zeros(5)

    linear = solve_temporal_effect_path(
        linear_plan,
        observed_series=observed,
        controls={"counterfactual_series": baseline},
    )
    ode = solve_temporal_effect_path(
        ode_plan,
        observed_series=observed,
        controls={"counterfactual_series": baseline},
    )

    assert linear.solver_mean_path == ode.solver_mean_path
    assert linear.discretization_error == ode.discretization_error


def test_structural_time_series_temporal_path_returns_positive_effect() -> None:
    trajectory = estimate_structural_time_series_trajectory(
        _panel_data(),
        _query(outcome_process="treated_outcome", horizon_end=5.0),
    )

    assert np.isfinite(trajectory.integral_effect)
    assert trajectory.effect_path[-1] > 0.5
    assert len(trajectory.counterfactual_path) == 6
    assert trajectory.diagnostics["comparator_semantics"] == "untreated_counterfactual"


def test_g_computation_temporal_path_beats_never_treat_baseline() -> None:
    regime = DynamicTreatmentRegime(
        time_points=(0, 1, 2, 3),
        treatment_variables=("A_0", "A_1", "A_2", "A_3"),
        time_varying_covariates=("state",),
        outcome="Y",
        rule=RegimeRule.ALWAYS_TREAT,
    )
    g_result, trajectory = estimate_g_computation_trajectory(
        _dynamic_g_data(),
        _query(outcome_process="state", horizon_end=3.0),
        regime=regime,
        method="parametric_g",
        method_params={"n_bootstrap": 30, "n_monte_carlo": 120},
    )

    assert g_result.counterfactual_mean > 1.0
    assert trajectory.integral_effect > 0.0
    assert trajectory.effect_path[-1] > 0.0
    assert trajectory.diagnostics["comparator_semantics"] == "never_treat_baseline"


def test_dtr_temporal_path_uses_optimal_regime_against_baseline() -> None:
    dtr_result, trajectory = estimate_dtr_trajectory(
        _dynamic_dtr_data(),
        _query(outcome_process="state", horizon_end=2.0),
        method="q_learning",
        method_params={"n_bootstrap": 30},
    )

    assert dtr_result.value_estimate > 0.0
    assert trajectory.integral_effect > 0.0
    assert trajectory.effect_path[-1] > 0.0
    assert trajectory.diagnostics["optimal_regime_rule"] in {
        RegimeRule.ALWAYS_TREAT.value,
        RegimeRule.THRESHOLD.value,
    }


def test_linear_interpolation_does_not_posthoc_shrink_confidence_bands() -> None:
    panel = PanelObservationalData(
        outcome=np.vstack([np.linspace(0.0, 3.0, 4), np.zeros(4), np.zeros(4)]),
        treatment=np.array([1, 0, 0], dtype=int),
        time_treatment=1,
        time_index=np.arange(4, dtype=float),
    )
    query = ContinuousTimeQuery(
        intervention_trajectory_ref=_artifact_ref("a", kind="test.intervention_trajectory"),
        outcome_process="panel_state",
        horizon_start=0.0,
        horizon_end=3.0,
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        metadata={"preferred_backend": "linear_sde"},
    )
    intervention = TemporalInterventionTrajectory(
        time_points=(0.0, 1.0, 2.0, 3.0),
        values=(0.0, 1.0, 1.0, 1.0),
        time_scale="days",
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
    )
    plan = compile_temporal_estimand(
        query,
        data=panel,
        resolved_intervention=intervention,
    )
    effect_samples = np.asarray(
        [
            [0.10, 0.20, 0.30, 0.40],
            [0.15, 0.25, 0.35, 0.45],
            [0.05, 0.15, 0.25, 0.35],
        ],
        dtype=float,
    )
    trajectory = solve_temporal_effect_path(
        plan,
        observed_series=np.array([0.1, 0.2, 0.3, 0.4], dtype=float),
        controls={
            "counterfactual_series": np.zeros(4, dtype=float),
            "effect_samples": effect_samples,
        },
    )

    assert np.allclose(
        np.asarray(trajectory.confidence_band_lower, dtype=float),
        np.quantile(effect_samples, 0.025, axis=0),
    )
    assert np.allclose(
        np.asarray(trajectory.confidence_band_upper, dtype=float),
        np.quantile(effect_samples, 0.975, axis=0),
    )


def test_discrete_fallback_is_truthfully_disclosed() -> None:
    regime = DynamicTreatmentRegime(
        time_points=(0, 1, 2, 3),
        treatment_variables=("A_0", "A_1", "A_2", "A_3"),
        time_varying_covariates=("state",),
        outcome="Y",
        rule=RegimeRule.ALWAYS_TREAT,
    )
    _, trajectory = estimate_g_computation_trajectory(
        _dynamic_g_data(),
        _query(outcome_process="state", horizon_end=2.5),
        regime=regime,
        method="parametric_g",
        method_params={"n_bootstrap": 30, "n_monte_carlo": 120},
    )

    assert trajectory.path_representation.value == "discrete_replay"
    assert trajectory.discretization_error is None
    assert trajectory.discretization_note == "unavailable_under_discrete_fallback"
    assert trajectory.continuous_time_degraded is True
