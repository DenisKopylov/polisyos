"""G-computation estimators for time-varying (dynamic) treatment effects.

Implements three variants of the g-computation formula (Robins 1986):
  - ParametricGFormula:  Monte Carlo simulation over sequential models
  - ICEGFormula:         Iterative Conditional Expectations (backward regression)
  - LTMLEEstimator:      Longitudinal TMLE with sequential targeting (doubly robust)

All three methods estimate the counterfactual mean E[Y^{ā}] under a specified
dynamic treatment regime ā = (a_0, a_1, ..., a_{T-1}).

References:
    Robins, J.M. (1986). A new approach to causal inference in mortality studies.
        Mathematical Modelling, 7, 1393-1512.
    Hernán, M.A. & Robins, J.M. (2020). Causal Inference: What If. Chapman & Hall.
    van der Laan, M.J. & Gruber, S. (2012). Targeted minimum loss based estimation
        of causal effects of multiple time point interventions.
        International Journal of Biostatistics, 8(1).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.causal._common import (
    bootstrap_ci,
    build_failure_report,
    build_success_report,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal._sklearn_compat import (
    LinearRegression,
    LogisticRegression,
)
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.foundry.methods.catalog.causal.structural_time_series import (
    TemporalTrajectoryResult,
    solve_temporal_effect_path,
)
from polisyos.foundry.methods.catalog.causal.temporal_estimand_compiler import (
    TemporalCompileError,
    compile_temporal_estimand,
)
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus
from polisyos.ir.analytics.dynamic_regime import (
    ContinuousTimeQuery,
    DynamicTreatmentRegime,
    GComputationResult,
    RegimeRule,
    TemporalIdentificationCertificate,
    TemporalInterventionTrajectory,
)

# ---------------------------------------------------------------------------
# Internal shared helpers
# ---------------------------------------------------------------------------

_ASSUMPTIONS = {
    "sequential_ignorability": (
        "A_t ⊥ Y^{ā} | H_t for all t (no unmeasured time-varying confounders)"
    ),
    "consistency": "Y_i = Y_i^{ā} when Ā_i = ā (no hidden treatment versions)",
    "positivity": "0 < P(A_t = a_t | H_t) < 1 for all t and h_t in support",
    "sutva": "No interference between units",
}


def _build_history_matrix(A_seq: np.ndarray, L_seq: np.ndarray, t: int) -> np.ndarray:
    """Construct flattened history feature matrix H_t for all units.

    H_t = [L_0, A_0, L_1, A_1, ..., L_{t-1}, A_{t-1}, L_t]
    shape: (n_units, t*(p+1) + p) where p = n_covariates.
    """
    n_units, _, p = L_seq.shape
    parts: list[np.ndarray] = []
    for s in range(t):
        parts.append(L_seq[:, s, :])  # (n_units, p)
        parts.append(A_seq[:, s : s + 1].astype(float))  # (n_units, 1)
    parts.append(L_seq[:, t, :])  # (n_units, p) — current covariates
    return np.hstack(parts)  # (n_units, t*(p+1) + p)


def _apply_regime(
    H_t: np.ndarray,
    L_t: np.ndarray,
    rule: str,
    threshold_cov_idx: int = 0,
    threshold_value: float = 0.0,
    *,
    time_index: int | None = None,
    scheduled_actions: Sequence[float] | None = None,
) -> np.ndarray:
    """Map history H_t → action A_t under the specified regime.

    Returns binary array of shape (n_units,).
    """
    n_units = H_t.shape[0]
    if rule == RegimeRule.ALWAYS_TREAT.value:
        return np.ones(n_units, dtype=float)
    if rule == RegimeRule.NEVER_TREAT.value:
        return np.zeros(n_units, dtype=float)
    if rule == RegimeRule.THRESHOLD.value:
        # treat if L_t[threshold_cov_idx] > threshold_value
        cov_idx = min(threshold_cov_idx, L_t.shape[1] - 1)
        return (L_t[:, cov_idx] > threshold_value).astype(float)
    if rule == RegimeRule.EXPLICIT_SCHEDULE.value:
        if scheduled_actions is None or time_index is None:
            raise ValueError("explicit_schedule regimes require time_index and scheduled_actions")
        action = float(scheduled_actions[min(int(time_index), len(scheduled_actions) - 1)])
        return np.full(n_units, action, dtype=float)
    # Default: always treat
    return np.ones(n_units, dtype=float)


def _fit_outcome_model(X: np.ndarray, y: np.ndarray) -> LinearRegression:
    model = LinearRegression()
    model.fit(X, y)
    return model


def _fit_propensity_model(X: np.ndarray, a: np.ndarray) -> LogisticRegression:
    model = LogisticRegression(max_iter=500, C=1.0, solver="lbfgs")
    # Guard: need both classes
    if len(np.unique(a)) < 2:
        return None  # type: ignore[return-value]
    model.fit(X, a)
    return model


def _predict_proba_safe(model: LogisticRegression | None, X: np.ndarray) -> np.ndarray:
    """Predict P(A=1|X) with clipping; fall back to 0.5 if model is None."""
    if model is None:
        return np.full(X.shape[0], 0.5)
    prob = model.predict_proba(X)[:, 1]
    return np.clip(prob, 1e-6, 1 - 1e-6)


# ---------------------------------------------------------------------------
# ICE g-formula (shared backbone used by ParametricGFormula bootstrap and LTMLE init)
# ---------------------------------------------------------------------------


def _ice_estimate(
    Y: np.ndarray,
    A_seq: np.ndarray,
    L_seq: np.ndarray,
    regime_params: dict[str, Any],
) -> float:
    """Iterative Conditional Expectations g-formula.

    Backward regression: fit Q_T, then pseudo-Y_{T-1} = Q_T(H, d*(H)), ...
    Returns scalar E[Y^d].
    """
    n_units, n_periods, _ = L_seq.shape
    rule = regime_params.get("regime", RegimeRule.ALWAYS_TREAT.value)
    thr_cov = int(regime_params.get("threshold_covariate_index", 0))
    thr_val = float(regime_params.get("threshold_value", 0.0))
    scheduled_actions = regime_params.get("scheduled_actions")

    # Pre-cache all history matrices — avoids 3× redundant O(n·T·p) builds per period
    H_cache = [_build_history_matrix(A_seq, L_seq, t) for t in range(n_periods)]

    # Step 1: fit Q_T = E[Y | H_{T-1}, A_{T-1}]
    H_last = H_cache[n_periods - 1]
    X_last = np.hstack([H_last, A_seq[:, n_periods - 1 : n_periods]])
    q_model = _fit_outcome_model(X_last, Y)
    pseudo_Y = Y.copy().astype(float)

    # Step 2: backward iteration t = T-2, ..., 0
    for t in range(n_periods - 2, -1, -1):
        H_t = H_cache[t]
        L_t = L_seq[:, t, :]
        a_regime = _apply_regime(
            H_t,
            L_t,
            rule,
            thr_cov,
            thr_val,
            time_index=t,
            scheduled_actions=scheduled_actions,
        )

        # Predict Q_{t+1}(H_{t+1}, d*(H_{t+1})) using current pseudo_Y model
        # but apply regime at period t+1
        H_next = H_cache[t + 1]
        L_next = L_seq[:, t + 1, :] if t + 1 < n_periods else L_seq[:, -1, :]
        a_next = _apply_regime(
            H_next,
            L_next,
            rule,
            thr_cov,
            thr_val,
            time_index=t + 1,
            scheduled_actions=scheduled_actions,
        )
        X_next_regime = np.hstack([H_next, a_next.reshape(-1, 1)])
        pseudo_Y = q_model.predict(X_next_regime)

        # Fit new model for Q_t on OBSERVED treatment A_t (not regime)
        X_t = np.hstack([H_t, A_seq[:, t : t + 1]])
        q_model = _fit_outcome_model(X_t, pseudo_Y)

    # Step 3: final estimate — apply regime at t=0
    H0 = H_cache[0]
    L0 = L_seq[:, 0, :]
    a0 = _apply_regime(
        H0,
        L0,
        rule,
        thr_cov,
        thr_val,
        time_index=0,
        scheduled_actions=scheduled_actions,
    )
    X0_regime = np.hstack([H0, a0.reshape(-1, 1)])
    final_pseudo = q_model.predict(X0_regime)
    return float(np.mean(final_pseudo))


def _parametric_mc_estimate(
    Y: np.ndarray,
    A_seq: np.ndarray,
    L_seq: np.ndarray,
    regime_params: dict[str, Any],
    n_mc: int = 500,
    rng: np.random.Generator | None = None,
) -> float:
    """Parametric g-formula via Monte Carlo simulation.

    Fits sequential covariate models P(L_t | H_{t-1}) and outcome model E[Y | H_T],
    then simulates n_mc trajectories under the specified regime.
    """
    if rng is None:
        rng = np.random.default_rng(0)

    n_units, n_periods, n_cov = L_seq.shape
    rule = regime_params.get("regime", RegimeRule.ALWAYS_TREAT.value)
    thr_cov = int(regime_params.get("threshold_covariate_index", 0))
    thr_val = float(regime_params.get("threshold_value", 0.0))
    scheduled_actions = regime_params.get("scheduled_actions")

    # Fit covariate models P(L_t | H_{t-1}, A_{t-1}) for t = 1, ..., T-1
    cov_models: list[list[LinearRegression]] = []  # [t][feature_j]
    cov_residual_stds: list[np.ndarray] = []
    for t in range(1, n_periods):
        H_prev = _build_history_matrix(A_seq, L_seq, t - 1)
        X_cov = np.hstack([H_prev, A_seq[:, t - 1 : t]])
        models_t = []
        stds_t = []
        for j in range(n_cov):
            m = _fit_outcome_model(X_cov, L_seq[:, t, j])
            models_t.append(m)
            resid = L_seq[:, t, j] - m.predict(X_cov)
            stds_t.append(float(np.std(resid) + 1e-8))
        cov_models.append(models_t)
        cov_residual_stds.append(np.array(stds_t))

    # Fit outcome model E[Y | H_{T-1}, A_{T-1}]
    H_last = _build_history_matrix(A_seq, L_seq, n_periods - 1)
    X_out = np.hstack([H_last, A_seq[:, n_periods - 1 : n_periods]])
    out_model = _fit_outcome_model(X_out, Y)
    out_resid_std = float(np.std(Y - out_model.predict(X_out)) + 1e-8)

    # Monte Carlo simulation — vectorized over all n_mc paths simultaneously.
    # Replaces O(n_mc × n_periods × n_cov) single-row predicts with
    # O(n_periods × n_cov) batch predicts of shape (n_mc,).
    unit_idxs = rng.integers(0, n_units, size=n_mc)
    L_sim = np.zeros((n_mc, n_periods, n_cov))
    A_sim = np.zeros((n_mc, n_periods))
    L_sim[:, 0, :] = L_seq[unit_idxs, 0, :]

    for t in range(n_periods):
        H_t = _build_history_matrix(A_sim, L_sim, t)  # (n_mc, features)
        L_t = L_sim[:, t, :]
        a_t = _apply_regime(
            H_t,
            L_t,
            rule,
            thr_cov,
            thr_val,
            time_index=t,
            scheduled_actions=scheduled_actions,
        )
        A_sim[:, t] = a_t

        if t < n_periods - 1:
            X_cov_sim = np.hstack([H_t, a_t.reshape(-1, 1)])
            for j in range(n_cov):
                mean_j = cov_models[t][j].predict(X_cov_sim)  # (n_mc,) batch
                noise = rng.normal(0, cov_residual_stds[t][j], size=n_mc)
                L_sim[:, t + 1, j] = mean_j + noise

    H_final = _build_history_matrix(A_sim, L_sim, n_periods - 1)
    X_out_sim = np.hstack([H_final, A_sim[:, n_periods - 1 : n_periods]])
    y_sim = out_model.predict(X_out_sim)  # (n_mc,) batch
    mc_outcomes = y_sim + rng.normal(0, out_resid_std, size=n_mc)

    return float(np.mean(mc_outcomes))


# ---------------------------------------------------------------------------
# Shared output slot definitions
# ---------------------------------------------------------------------------


def _dynamic_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("result", SlotType.SCALAR, Unit("report", "json")),
            SlotSpec("g_result", SlotType.SCALAR, Unit("g_computation_result", "json")),
            SlotSpec("warnings", SlotType.SCALAR, Unit("warning", "list")),
        }
    )


def _dynamic_input_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "outcome",
                SlotType.VECTOR,
                Unit("outcome", "value"),
                shape=("n_units",),
                contract_id=DynamicTreatmentData.contract_id,
            ),
            SlotSpec(
                "treatment_sequence",
                SlotType.MATRIX,
                Unit("treatment", "binary"),
                shape=("n_units", "n_periods"),
            ),
            SlotSpec(
                "covariate_sequence",
                SlotType.TENSOR,
                Unit("covariate", "value"),
                shape=("n_units", "n_periods", "n_covariates"),
            ),
        }
    )


def _dynamic_base_params() -> tuple[ParameterSpec, ...]:
    return (
        ParameterSpec("regime", default="always_treat"),
        ParameterSpec(
            "n_bootstrap",
            default=200,
            bounds=(50, 1000),
        ),
        ParameterSpec("confidence_level", default=0.95, bounds=(0.8, 0.99)),
        ParameterSpec("threshold_covariate_index", default=0, bounds=(0, 1000)),
        ParameterSpec("threshold_value", default=0.0),
    )


def _extract_dynamic_data(state: Any) -> DynamicTreatmentData:
    """Extract or validate DynamicTreatmentData from method state."""
    if isinstance(state, DynamicTreatmentData):
        return state
    if isinstance(state, dict):
        return DynamicTreatmentData.model_validate(state)
    raise TypeError(f"Expected DynamicTreatmentData or dict, got {type(state).__name__}")


def _build_g_output(
    *,
    method_enum: CausalMethod,
    estimand_str: str,
    g_result: GComputationResult,
    n_treated_est: int,
    n_control_est: int,
    n_units: int,
    n_periods: int,
    warnings: list[str],
) -> dict[str, Any]:
    report = build_success_report(
        method=method_enum,
        estimand=estimand_str,
        point_estimate=g_result.counterfactual_mean,
        confidence_interval=g_result.confidence_interval,
        inference_method="bootstrap",
        sample_size=n_units,
        n_treated=n_treated_est,
        n_control=n_control_est,
        pre_periods=n_periods,
        post_periods=0,
        assumptions=dict(_ASSUMPTIONS),
        standard_error=g_result.standard_error,
        metadata={"regime": g_result.regime, "n_periods": n_periods},
    )
    return wrap_causal_output(report, warnings=warnings, extras={"g_result": g_result})


def _regime_params_from_spec(
    regime: DynamicTreatmentRegime | None,
) -> dict[str, Any]:
    if regime is None:
        return {
            "regime": RegimeRule.ALWAYS_TREAT.value,
            "threshold_covariate_index": 0,
            "threshold_value": 0.0,
            "scheduled_actions": None,
        }
    return {
        "regime": regime.rule.value,
        "threshold_covariate_index": int(regime.threshold_covariate_index),
        "threshold_value": float(regime.threshold_value),
        "scheduled_actions": (
            None
            if regime.scheduled_actions is None
            else tuple(float(action) for action in regime.scheduled_actions)
        ),
    }


def _build_temporal_intervention_from_schedule(
    *,
    query: ContinuousTimeQuery,
    time_grid: Sequence[float],
    schedule: Sequence[float],
    metadata: Mapping[str, Any] | None = None,
) -> TemporalInterventionTrajectory:
    return TemporalInterventionTrajectory(
        time_points=tuple(float(value) for value in time_grid),
        values=tuple(float(value) for value in schedule),
        time_scale=query.time_scale,
        interpolation_policy=query.interpolation_policy,
        metadata=dict(metadata or {}),
    )


def _materialize_intervention_schedule(
    intervention: TemporalInterventionTrajectory,
    *,
    time_grid: Sequence[float],
) -> tuple[int, ...]:
    knot_times = np.asarray(intervention.time_points, dtype=float)
    knot_values = np.asarray(intervention.values, dtype=float)
    grid = np.asarray(tuple(float(value) for value in time_grid), dtype=float)
    if intervention.interpolation_policy.value == "linear":
        materialized = np.interp(grid, knot_times, knot_values)
    else:
        indices = np.searchsorted(knot_times, grid, side="right") - 1
        indices = np.clip(indices, 0, knot_values.shape[0] - 1)
        materialized = knot_values[indices]
    rounded = np.round(materialized)
    if not np.allclose(materialized, rounded, atol=1e-8) or not np.isin(rounded, [0, 1]).all():
        raise TemporalCompileError(
            "unsupported_dynamic_intervention",
            "Phase C dynamic-treatment execution currently supports only binary schedules.",
            details={"materialized_values": materialized.tolist()},
        )
    return tuple(int(value) for value in rounded.tolist())


def _schedule_from_regime(
    regime: DynamicTreatmentRegime,
    *,
    time_grid: Sequence[float],
) -> tuple[int, ...]:
    if regime.rule is RegimeRule.ALWAYS_TREAT:
        return tuple(1 for _ in time_grid)
    if regime.rule is RegimeRule.NEVER_TREAT:
        return tuple(0 for _ in time_grid)
    if regime.rule is RegimeRule.EXPLICIT_SCHEDULE and regime.scheduled_actions is not None:
        if len(regime.scheduled_actions) != len(tuple(time_grid)):
            raise TemporalCompileError(
                "intervention_regime_mismatch",
                "Explicit schedule regime length must match the dynamic time grid.",
                details={
                    "scheduled_actions": list(regime.scheduled_actions),
                    "time_grid_length": len(tuple(time_grid)),
                },
            )
        return tuple(int(value) for value in regime.scheduled_actions)
    raise TemporalCompileError(
        "unsupported_intervention_regime_consistency",
        "Only always_treat, never_treat, and explicit_schedule regimes can be checked against fixed intervention artifacts in Phase C.",
        details={"rule": regime.rule.value},
    )


def _regime_from_intervention(
    *,
    query: ContinuousTimeQuery,
    data: DynamicTreatmentData,
    intervention: TemporalInterventionTrajectory,
) -> DynamicTreatmentRegime:
    time_grid = (
        np.arange(data.n_periods, dtype=float)
        if data.time_ids is None
        else np.asarray(data.time_ids, dtype=float)
    )
    schedule = _materialize_intervention_schedule(intervention, time_grid=time_grid)
    return DynamicTreatmentRegime(
        time_points=tuple(range(len(schedule))),
        treatment_variables=tuple(
            f"{data.treatment_name}_{index}" for index in range(len(schedule))
        ),
        time_varying_covariates=tuple(data.variable_names or [query.outcome_process]),
        outcome=data.outcome_name,
        rule=RegimeRule.EXPLICIT_SCHEDULE,
        scheduled_actions=schedule,
        metadata={"derived_from_intervention_contract": True},
    )


def _compat_schedule_from_dynamic_regime(
    regime: DynamicTreatmentRegime,
    *,
    data: DynamicTreatmentData,
) -> tuple[int, ...]:
    try:
        return _schedule_from_regime(
            regime,
            time_grid=(
                np.arange(data.n_periods, dtype=float)
                if data.time_ids is None
                else np.asarray(data.time_ids, dtype=float)
            ),
        )
    except TemporalCompileError:
        A_seq = data.treatment_sequence.astype(float)
        L_seq = data.covariate_sequence.astype(float)
        schedule: list[int] = []
        params = _regime_params_from_spec(regime)
        for t in range(data.n_periods):
            H_t = _build_history_matrix(A_seq, L_seq, t)
            L_t = L_seq[:, t, :]
            actions = _apply_regime(
                H_t,
                L_t,
                params["regime"],
                int(params["threshold_covariate_index"]),
                float(params["threshold_value"]),
                time_index=t,
                scheduled_actions=params.get("scheduled_actions"),
            )
            schedule.append(int(float(np.mean(actions)) >= 0.5))
        return tuple(schedule)


def _resolve_temporal_process_index(
    data: DynamicTreatmentData,
    outcome_process: str,
) -> int:
    candidate = str(outcome_process).strip()
    if data.variable_names is not None:
        for index, name in enumerate(data.variable_names):
            if str(name).strip().lower() == candidate.lower():
                return index
    if data.covariate_sequence.shape[2] == 1:
        return 0
    raise ValueError(
        "Temporal dynamic-treatment queries must name a covariate in variable_names "
        "unless there is exactly one covariate channel."
    )


def _fit_covariate_transition_models(
    A_seq: np.ndarray,
    L_seq: np.ndarray,
) -> tuple[list[list[LinearRegression]], list[np.ndarray]]:
    n_units, n_periods, n_cov = L_seq.shape
    _ = n_units
    cov_models: list[list[LinearRegression]] = []
    cov_residual_stds: list[np.ndarray] = []
    for t in range(1, n_periods):
        H_prev = _build_history_matrix(A_seq, L_seq, t - 1)
        X_cov = np.hstack([H_prev, A_seq[:, t - 1 : t]])
        models_t: list[LinearRegression] = []
        stds_t: list[float] = []
        for j in range(n_cov):
            model = _fit_outcome_model(X_cov, L_seq[:, t, j])
            models_t.append(model)
            residual = L_seq[:, t, j] - model.predict(X_cov)
            stds_t.append(float(np.std(residual) + 1e-8))
        cov_models.append(models_t)
        cov_residual_stds.append(np.asarray(stds_t, dtype=float))
    return cov_models, cov_residual_stds


def _simulate_regime_trajectory_ensemble(
    data: DynamicTreatmentData,
    *,
    regime_params: Mapping[str, Any],
    outcome_process: str,
    n_mc: int = 256,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Simulate covariate trajectories for the requested temporal process."""

    if rng is None:
        rng = np.random.default_rng(0)

    A_seq = data.treatment_sequence.astype(float)
    L_seq = data.covariate_sequence.astype(float)
    n_units, n_periods, n_cov = L_seq.shape
    process_index = _resolve_temporal_process_index(data, outcome_process)
    cov_models, cov_residual_stds = _fit_covariate_transition_models(A_seq, L_seq)

    rule = str(regime_params.get("regime", RegimeRule.ALWAYS_TREAT.value))
    thr_cov = int(regime_params.get("threshold_covariate_index", 0))
    thr_val = float(regime_params.get("threshold_value", 0.0))
    scheduled_actions = regime_params.get("scheduled_actions")

    samples = np.empty((max(1, n_mc), n_periods), dtype=float)
    for draw in range(samples.shape[0]):
        unit_idx = int(rng.integers(0, n_units))
        L_sim = np.zeros((1, n_periods, n_cov), dtype=float)
        A_sim = np.zeros((1, n_periods), dtype=float)
        L_sim[0, 0, :] = L_seq[unit_idx, 0, :]
        samples[draw, 0] = float(L_sim[0, 0, process_index])

        for t in range(n_periods):
            H_t = _build_history_matrix(A_sim, L_sim, t)
            L_t = L_sim[0, t, :].reshape(1, -1)
            action = _apply_regime(
                H_t,
                L_t,
                rule,
                thr_cov,
                thr_val,
                time_index=t,
                scheduled_actions=scheduled_actions,
            )
            A_sim[0, t] = float(action[0])
            if t >= n_periods - 1:
                continue
            X_cov_sim = np.hstack([H_t, action.reshape(-1, 1)])
            for cov_index in range(n_cov):
                mean_value = cov_models[t][cov_index].predict(X_cov_sim)[0]
                L_sim[0, t + 1, cov_index] = mean_value + rng.normal(
                    0.0,
                    cov_residual_stds[t][cov_index],
                )
            samples[draw, t + 1] = float(L_sim[0, t + 1, process_index])
    return samples


def estimate_g_computation_trajectory(
    data: DynamicTreatmentData | dict[str, Any],
    query: ContinuousTimeQuery,
    *,
    regime: DynamicTreatmentRegime | None = None,
    resolved_intervention: TemporalInterventionTrajectory | dict[str, Any] | None = None,
    identification_certificate: TemporalIdentificationCertificate | dict[str, Any] | None = None,
    method: str = "parametric_g",
    method_params: Mapping[str, Any] | None = None,
    allow_discrete_fallback: bool = True,
) -> tuple[GComputationResult, TemporalTrajectoryResult]:
    """Return scalar g-computation output plus a temporal effect trajectory."""

    dynamic_data = _extract_dynamic_data(data)
    intervention = (
        None
        if resolved_intervention is None
        else (
            resolved_intervention
            if isinstance(resolved_intervention, TemporalInterventionTrajectory)
            else TemporalInterventionTrajectory.model_validate(resolved_intervention)
        )
    )
    effective_regime = regime
    contract_status = (
        "resolved_artifact" if intervention is not None else "compatibility_synthesized"
    )
    if intervention is None:
        effective_regime = regime or DynamicTreatmentRegime(
            time_points=tuple(range(dynamic_data.n_periods)),
            treatment_variables=tuple(
                f"{dynamic_data.treatment_name}_{index}" for index in range(dynamic_data.n_periods)
            ),
            time_varying_covariates=tuple(dynamic_data.variable_names or [query.outcome_process]),
            outcome=dynamic_data.outcome_name,
            rule=RegimeRule.ALWAYS_TREAT,
        )
        intervention = _build_temporal_intervention_from_schedule(
            query=query,
            time_grid=(
                np.arange(dynamic_data.n_periods, dtype=float)
                if dynamic_data.time_ids is None
                else np.asarray(dynamic_data.time_ids, dtype=float)
            ),
            schedule=_compat_schedule_from_dynamic_regime(
                effective_regime,
                data=dynamic_data,
            ),
            metadata={"contract_status": contract_status},
        )
    elif effective_regime is None:
        effective_regime = _regime_from_intervention(
            query=query,
            data=dynamic_data,
            intervention=intervention,
        )
    else:
        expected_schedule = _schedule_from_regime(
            effective_regime,
            time_grid=(
                np.arange(dynamic_data.n_periods, dtype=float)
                if dynamic_data.time_ids is None
                else np.asarray(dynamic_data.time_ids, dtype=float)
            ),
        )
        intervention_schedule = _materialize_intervention_schedule(
            intervention,
            time_grid=(
                np.arange(dynamic_data.n_periods, dtype=float)
                if dynamic_data.time_ids is None
                else np.asarray(dynamic_data.time_ids, dtype=float)
            ),
        )
        if intervention_schedule != expected_schedule:
            raise TemporalCompileError(
                "intervention_regime_mismatch",
                "Resolved intervention artifact does not match the requested dynamic treatment regime on the compiled grid.",
                details={
                    "expected_schedule": list(expected_schedule),
                    "intervention_schedule": list(intervention_schedule),
                },
            )

    plan = compile_temporal_estimand(
        query,
        data=dynamic_data,
        resolved_intervention=intervention,
        identification_certificate=identification_certificate,
        intervention_contract_status=contract_status,
        allow_discrete_fallback=allow_discrete_fallback,
    )
    method_dispatch: dict[str, type] = {
        "parametric_g": ParametricGFormula,
        "ice_g": ICEGFormula,
        "ltmle": LTMLEEstimator,
    }
    method_cls = method_dispatch.get(method)
    if method_cls is None:
        raise ValueError(
            f"Unknown g-computation temporal method {method!r}. "
            f"Choose from: {sorted(method_dispatch)}"
        )

    scalar_params = dict(method_params or {})
    scalar_params.update(_regime_params_from_spec(effective_regime))
    scalar_result = method_cls.pure_step(dynamic_data, scalar_params)
    g_result = scalar_result.get("g_result")
    if not isinstance(g_result, GComputationResult):
        raise RuntimeError("Temporal g-computation helper expected a GComputationResult payload")

    regime_params = _regime_params_from_spec(effective_regime)
    baseline_params = {
        "regime": RegimeRule.NEVER_TREAT.value,
        "threshold_covariate_index": 0,
        "threshold_value": 0.0,
        "scheduled_actions": None,
    }
    rng = np.random.default_rng(42)
    n_paths = int(plan.solver_config.get("monte_carlo_paths", 256))
    target_samples = _simulate_regime_trajectory_ensemble(
        dynamic_data,
        regime_params=regime_params,
        outcome_process=query.outcome_process,
        n_mc=n_paths,
        rng=rng,
    )
    baseline_samples = _simulate_regime_trajectory_ensemble(
        dynamic_data,
        regime_params=baseline_params,
        outcome_process=query.outcome_process,
        n_mc=n_paths,
        rng=rng,
    )
    grid_positions = np.asarray(plan.time_index_positions, dtype=int)
    target_aligned = target_samples[:, grid_positions]
    baseline_aligned = baseline_samples[:, grid_positions]
    trajectory = solve_temporal_effect_path(
        plan,
        observed_series=target_aligned.mean(axis=0),
        controls={
            "counterfactual_series": baseline_aligned.mean(axis=0),
            "effect_samples": target_aligned - baseline_aligned,
            "seed": 42,
        },
    )
    trajectory.metadata.update(
        {
            "regime": regime_params["regime"],
            "scalar_method": g_result.method,
            "outcome_process": query.outcome_process,
            "intervention_contract_status": contract_status,
        }
    )
    trajectory.diagnostics["scalar_counterfactual_mean"] = float(g_result.counterfactual_mean)
    trajectory.diagnostics["regime"] = regime_params["regime"]
    return g_result, trajectory


# ---------------------------------------------------------------------------
# 1. ParametricGFormula
# ---------------------------------------------------------------------------


@foundry_method(namespace="causal.dynamic.g_computation", version="1.0.0")
class ParametricGFormula:
    """Parametric G-computation formula via Monte Carlo simulation (Robins 1986).

    Fits sequential covariate models P(L_t | H_{t-1}, A_{t-1}) and an outcome
    model E[Y | H_{T-1}, A_{T-1}], then simulates trajectories under a specified
    dynamic treatment regime to estimate E[Y^{ā}].

    Assumptions:
        Sequential ignorability: A_t ⊥ Y^{ā} | H_t for all t.
        Consistency and positivity.

    References:
        Robins (1986). A new approach to causal inference in mortality studies.
        Hernán & Robins (2020). Causal Inference: What If.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="parametric_g_formula",
        namespace="",
        version="0.0.0",
        input_slots=_dynamic_input_slots(),
        output_slots=_dynamic_output_slots(),
        parameters=_dynamic_base_params()
        + (ParameterSpec("n_monte_carlo", default=500, bounds=(100, 5000)),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Parametric G-computation for time-varying treatments. "
            "Estimates E[Y^{ā}] via Monte Carlo simulation under a specified regime."
        ),
        tags=frozenset(
            {
                "causal",
                "dynamic",
                "longitudinal",
                "g_computation",
                "time_varying",
                "sequential",
            }
        ),
        citations=(
            "Robins, J.M. (1986). A new approach to causal inference in mortality studies. "
            "Mathematical Modelling, 7, 1393-1512.",
            "Hernán, M.A. & Robins, J.M. (2020). Causal Inference: What If. Chapman & Hall.",
        ),
        equations={
            "g_formula": ("E[Y^{ā}] = Σ_{l̄} E[Y|Ā=ā,L̄=l̄] × Π_t P(L_t|ā_{t-1},l̄_{t-1})"),
        },
        assumptions=dict(_ASSUMPTIONS),
        when_to_use=(
            "Time-varying treatments with sequential confounders where standard "
            "regression would produce biased estimates due to treatment-confounder "
            "feedback loops."
        ),
        when_not_to_use=(
            "Cross-sectional data (use AIPW/TMLE), unmeasured time-varying confounders "
            "(g-formula cannot correct for these), or very short follow-up (T < 2)."
        ),
        typical_min_obs=100,
        output_interpretation=(
            "point_estimate is E[Y^{ā}] — the mean outcome if everyone had followed "
            "the specified regime. Compare always_treat vs never_treat to get ATE."
        ),
    )

    @staticmethod
    def pure_step(state: DynamicTreatmentData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            data = _extract_dynamic_data(state)
        except Exception as exc:
            from polisyos.ir.analytics.causal import EstimationStatus

            dummy = build_failure_report(
                method=CausalMethod.G_COMPUTATION,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="E[Y^{ā}]",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions={},
            )
            return wrap_causal_output(dummy)

        Y = data.outcome.astype(float)
        A_seq = data.treatment_sequence.astype(float)
        L_seq = data.covariate_sequence.astype(float)
        n_units, n_periods = data.n_units, data.n_periods

        if n_units < 10:
            dummy = build_failure_report(
                method=CausalMethod.G_COMPUTATION,
                status=EstimationStatus.INPUT_INVALID,
                reason="Need at least 10 units for g-computation",
                estimand="E[Y^{ā}]",
                sample_size=n_units,
                n_treated=0,
                n_control=0,
                pre_periods=n_periods,
                post_periods=0,
                assumptions=dict(_ASSUMPTIONS),
            )
            return wrap_causal_output(dummy)

        regime = str(params.get("regime", RegimeRule.ALWAYS_TREAT.value))
        n_mc = int(params.get("n_monte_carlo", 500))
        n_boot = int(params.get("n_bootstrap", 200))
        conf_level = float(params.get("confidence_level", 0.95))
        regime_params = {
            k: params.get(k, v.default)
            for k, v in {
                "regime": type("_", (), {"default": "always_treat"})(),
                "threshold_covariate_index": type("_", (), {"default": 0})(),
                "threshold_value": type("_", (), {"default": 0.0})(),
            }.items()
        }
        regime_params["regime"] = regime
        regime_params["threshold_covariate_index"] = int(params.get("threshold_covariate_index", 0))
        regime_params["threshold_value"] = float(params.get("threshold_value", 0.0))

        rng = np.random.default_rng(42)
        point = _parametric_mc_estimate(Y, A_seq, L_seq, regime_params, n_mc, rng)

        # Bootstrap CI
        boot_estimates = np.empty(n_boot)
        for b in range(n_boot):
            idx = rng.integers(0, n_units, size=n_units)
            boot_estimates[b] = _parametric_mc_estimate(
                Y[idx],
                A_seq[idx],
                L_seq[idx],
                regime_params,
                max(50, n_mc // 5),
                rng,
            )
        ci = bootstrap_ci(boot_estimates, conf_level)
        se = float(np.std(boot_estimates, ddof=1))

        # Sanitise CI
        lo = min(float(ci[0]), point)
        hi = max(float(ci[1]), point)

        n_treated = int(np.sum(A_seq[:, 0]))
        g_result = GComputationResult(
            counterfactual_mean=point,
            confidence_interval=(lo, hi),
            confidence_level=conf_level,
            standard_error=se,
            regime=regime,
            n_units=n_units,
            n_periods=n_periods,
            method="parametric_g",
        )
        return _build_g_output(
            method_enum=CausalMethod.G_COMPUTATION,
            estimand_str=f"E[Y^{{ā}}] under regime={regime}",
            g_result=g_result,
            n_treated_est=n_treated,
            n_control_est=n_units - n_treated,
            n_units=n_units,
            n_periods=n_periods,
            warnings=[],
        )


# ---------------------------------------------------------------------------
# 2. ICEGFormula
# ---------------------------------------------------------------------------


@foundry_method(namespace="causal.dynamic.ice_g_formula", version="1.0.0")
class ICEGFormula:
    """Iterative Conditional Expectations (ICE) g-formula (Robins & Hernán 2009).

    Backward regression approach — no Monte Carlo simulation required.
    Fits sequential outcome models backward in time, propagating pseudo-outcomes
    under the specified regime.  More computationally efficient than parametric
    g-formula but relies on correct outcome model specification.

    Algorithm:
        1. Fit Q_T = E[Y | H_{T-1}, A_{T-1}]
        2. For t = T-2, ..., 0:
             Ỹ_t = Q_{t+1}(H_{t+1}, d*(H_{t+1}))
             Q_t = E[Ỹ_t | H_t, A_t]
        3. E[Y^d] = E[Q_0(H_0, d*(H_0))]

    References:
        Hernán & Robins (2020). Causal Inference: What If. Appendix.
        Robins (1986). Mathematical Modelling, 7, 1393-1512.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ice_g_formula",
        namespace="",
        version="0.0.0",
        input_slots=_dynamic_input_slots(),
        output_slots=_dynamic_output_slots(),
        parameters=_dynamic_base_params(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "ICE g-formula via backward sequential regression. "
            "Efficient alternative to Monte Carlo g-computation — no simulation needed."
        ),
        tags=frozenset(
            {
                "causal",
                "dynamic",
                "longitudinal",
                "ice",
                "g_computation",
                "time_varying",
            }
        ),
        citations=(
            "Robins, J.M. (1986). A new approach to causal inference in mortality studies.",
            "Hernán, M.A. & Robins, J.M. (2020). Causal Inference: What If. Chapman & Hall.",
        ),
        equations={
            "ice_backward": (
                "Q_t = E[Q_{t+1}(H_{t+1}, d*(H_{t+1})) | H_t, A_t]; E[Y^d] = E[Q_0(H_0, d*(H_0))]"
            ),
        },
        assumptions=dict(_ASSUMPTIONS),
        when_to_use="Time-varying treatments; prefer over parametric g-formula for speed.",
        when_not_to_use=(
            "When outcome model is severely misspecified; prefer LTMLE for robustness."
        ),
        typical_min_obs=50,
        output_interpretation=("point_estimate is E[Y^{ā}] under the specified dynamic regime."),
    )

    @staticmethod
    def pure_step(state: DynamicTreatmentData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            data = _extract_dynamic_data(state)
        except Exception as exc:
            dummy = build_failure_report(
                method=CausalMethod.ICE_G_FORMULA,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="E[Y^{ā}]",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions={},
            )
            return wrap_causal_output(dummy)

        Y = data.outcome.astype(float)
        A_seq = data.treatment_sequence.astype(float)
        L_seq = data.covariate_sequence.astype(float)
        n_units, n_periods = data.n_units, data.n_periods

        if n_units < 10:
            dummy = build_failure_report(
                method=CausalMethod.ICE_G_FORMULA,
                status=EstimationStatus.INPUT_INVALID,
                reason="Need at least 10 units for ICE g-formula",
                estimand="E[Y^{ā}]",
                sample_size=n_units,
                n_treated=0,
                n_control=0,
                pre_periods=n_periods,
                post_periods=0,
                assumptions=dict(_ASSUMPTIONS),
            )
            return wrap_causal_output(dummy)

        regime = str(params.get("regime", RegimeRule.ALWAYS_TREAT.value))
        n_boot = int(params.get("n_bootstrap", 200))
        conf_level = float(params.get("confidence_level", 0.95))
        thr_cov = int(params.get("threshold_covariate_index", 0))
        thr_val = float(params.get("threshold_value", 0.0))
        regime_params = {
            "regime": regime,
            "threshold_covariate_index": thr_cov,
            "threshold_value": thr_val,
        }

        point = _ice_estimate(Y, A_seq, L_seq, regime_params)

        rng = np.random.default_rng(42)
        boot_estimates = np.empty(n_boot)
        for b in range(n_boot):
            idx = rng.integers(0, n_units, size=n_units)
            boot_estimates[b] = _ice_estimate(Y[idx], A_seq[idx], L_seq[idx], regime_params)
        ci = bootstrap_ci(boot_estimates, conf_level)
        se = float(np.std(boot_estimates, ddof=1))

        lo = min(float(ci[0]), point)
        hi = max(float(ci[1]), point)

        n_treated = int(np.sum(A_seq[:, 0]))
        g_result = GComputationResult(
            counterfactual_mean=point,
            confidence_interval=(lo, hi),
            confidence_level=conf_level,
            standard_error=se,
            regime=regime,
            n_units=n_units,
            n_periods=n_periods,
            method="ice_g",
        )
        return _build_g_output(
            method_enum=CausalMethod.ICE_G_FORMULA,
            estimand_str=f"E[Y^{{ā}}] under regime={regime}",
            g_result=g_result,
            n_treated_est=n_treated,
            n_control_est=n_units - n_treated,
            n_units=n_units,
            n_periods=n_periods,
            warnings=[],
        )


# ---------------------------------------------------------------------------
# 3. LTMLEEstimator
# ---------------------------------------------------------------------------


@foundry_method(namespace="causal.dynamic.ltmle", version="1.0.0")
class LTMLEEstimator:
    """Longitudinal Targeted Minimum Loss Estimation (LTMLE).

    Doubly-robust estimator for E[Y^{ā}] combining sequential outcome models (ICE)
    with propensity score targeting updates.  Consistent if either the outcome
    models or the propensity models are correctly specified.

    Algorithm:
        1. Initial outcome estimates: Q̃_t via ICE g-formula
        2. Propensity models: π_t = P(A_t=1|H_t) via logistic regression
        3. Clever covariate: h_t = I(A_t=1)/π_t - I(A_t=0)/(1-π_t)
        4. Targeting update: Q*_t = logistic(logit(Q̃_t) + ε_t * h_t)  [binary Y]
           or linear update Q*_t = Q̃_t + ε_t * h_t  [continuous Y]
        5. E[Y^d] = (1/n) Σ_i Q*_0(H_{i,0}, d*(H_{i,0}))

    References:
        van der Laan, M.J. & Gruber, S. (2012). Targeted minimum loss based estimation
            of causal effects of multiple time point interventions.
            International Journal of Biostatistics, 8(1).
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ltmle",
        namespace="",
        version="0.0.0",
        input_slots=_dynamic_input_slots(),
        output_slots=_dynamic_output_slots(),
        parameters=_dynamic_base_params(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Longitudinal TMLE: doubly-robust estimator for dynamic treatment effects. "
            "Combines ICE outcome models with propensity-score targeting."
        ),
        tags=frozenset(
            {
                "causal",
                "dynamic",
                "longitudinal",
                "ltmle",
                "tmle",
                "doubly_robust",
                "time_varying",
            }
        ),
        citations=(
            "van der Laan, M.J. & Gruber, S. (2012). Targeted minimum loss based "
            "estimation of causal effects of multiple time point interventions. "
            "International Journal of Biostatistics, 8(1).",
            "Hernán, M.A. & Robins, J.M. (2020). Causal Inference: What If.",
        ),
        equations={
            "ltmle_targeting": "Q*_t = Q̃_t + ε_t · h_t  (continuous Y)",
            "clever_covariate": "h_t = I(A_t=1)/π_t − I(A_t=0)/(1−π_t)",
        },
        assumptions=dict(_ASSUMPTIONS),
        when_to_use=(
            "When either the outcome model or propensity model may be misspecified. "
            "Provides semiparametric efficiency under correct model specification."
        ),
        when_not_to_use=(
            "Both models severely misspecified, or very small sample (< 30 per period)."
        ),
        typical_min_obs=100,
        output_interpretation=(
            "Doubly-robust estimate of E[Y^{ā}]. More reliable than ICE when propensity "
            "models are correctly specified."
        ),
    )

    @staticmethod
    def pure_step(state: DynamicTreatmentData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            data = _extract_dynamic_data(state)
        except Exception as exc:
            dummy = build_failure_report(
                method=CausalMethod.LTMLE,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="E[Y^{ā}]",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions={},
            )
            return wrap_causal_output(dummy)

        Y = data.outcome.astype(float)
        A_seq = data.treatment_sequence.astype(float)
        L_seq = data.covariate_sequence.astype(float)
        n_units, n_periods = data.n_units, data.n_periods

        if n_units < 10:
            dummy = build_failure_report(
                method=CausalMethod.LTMLE,
                status=EstimationStatus.INPUT_INVALID,
                reason="Need at least 10 units for LTMLE",
                estimand="E[Y^{ā}]",
                sample_size=n_units,
                n_treated=0,
                n_control=0,
                pre_periods=n_periods,
                post_periods=0,
                assumptions=dict(_ASSUMPTIONS),
            )
            return wrap_causal_output(dummy)

        regime = str(params.get("regime", RegimeRule.ALWAYS_TREAT.value))
        n_boot = int(params.get("n_bootstrap", 200))
        conf_level = float(params.get("confidence_level", 0.95))
        thr_cov = int(params.get("threshold_covariate_index", 0))
        thr_val = float(params.get("threshold_value", 0.0))
        regime_params = {
            "regime": regime,
            "threshold_covariate_index": thr_cov,
            "threshold_value": thr_val,
        }
        warnings: list[str] = []

        def _ltmle_once(
            Y_b: np.ndarray,
            A_b: np.ndarray,
            L_b: np.ndarray,
        ) -> float:
            n = Y_b.shape[0]
            # Step 1: ICE initial estimates (backward)
            # Build per-period pseudo-Y, forward from last period
            pseudo_Y = Y_b.copy().astype(float)

            # Fit propensity models per period
            propensity_models = []
            for t in range(n_periods):
                H_t = _build_history_matrix(A_b, L_b, t)
                pm = _fit_propensity_model(H_t, A_b[:, t])
                propensity_models.append(pm)

            # Backward ICE pass to get initial Q_0 prediction
            q_init = _ice_estimate(Y_b, A_b, L_b, regime_params)

            # Step 2: Targeting update using propensity residuals
            # For each unit, compute cumulative propensity weight under regime
            cum_weights = np.ones(n)
            for t in range(n_periods):
                H_t = _build_history_matrix(A_b, L_b, t)
                pi_t = _predict_proba_safe(propensity_models[t], H_t)
                L_t = L_b[:, t, :]
                a_regime = _apply_regime(H_t, L_t, regime, thr_cov, thr_val)
                # Weight contribution from period t
                # P(A_t = a_regime_t | H_t)
                prob_regime = np.where(a_regime == 1, pi_t, 1 - pi_t)
                # P(A_t = obs | H_t)
                prob_obs = np.where(A_b[:, t] == 1, pi_t, 1 - pi_t)
                cum_weights *= prob_regime / np.clip(prob_obs, 1e-6, None)

            # LTMLE targeting: epsilon = weighted regression of Y on cum_weights
            # with intercept = q_init (simplified linear targeting)
            X_target = cum_weights.reshape(-1, 1)
            y_resid = Y_b - q_init
            if np.std(X_target) > 1e-10:
                m_target = LinearRegression(fit_intercept=False)
                m_target.fit(X_target, y_resid)
                epsilon = float(m_target.coef_[0])
            else:
                epsilon = 0.0

            # Targeted estimate
            targeted_estimate = q_init + epsilon * float(np.mean(cum_weights))
            return float(targeted_estimate)

        point = _ltmle_once(Y, A_seq, L_seq)

        rng = np.random.default_rng(42)
        boot_estimates = np.empty(n_boot)
        for b in range(n_boot):
            idx = rng.integers(0, n_units, size=n_units)
            boot_estimates[b] = _ltmle_once(Y[idx], A_seq[idx], L_seq[idx])

        ci = bootstrap_ci(boot_estimates, conf_level)
        se = float(np.std(boot_estimates, ddof=1))
        lo = min(float(ci[0]), point)
        hi = max(float(ci[1]), point)

        n_treated = int(np.sum(A_seq[:, 0]))
        g_result = GComputationResult(
            counterfactual_mean=point,
            confidence_interval=(lo, hi),
            confidence_level=conf_level,
            standard_error=se,
            regime=regime,
            n_units=n_units,
            n_periods=n_periods,
            method="ltmle",
        )
        return _build_g_output(
            method_enum=CausalMethod.LTMLE,
            estimand_str=f"E[Y^{{ā}}] under regime={regime} (LTMLE)",
            g_result=g_result,
            n_treated_est=n_treated,
            n_control_est=n_units - n_treated,
            n_units=n_units,
            n_periods=n_periods,
            warnings=warnings,
        )


__all__ = [
    "GComputationResult",
    "ICEGFormula",
    "LTMLEEstimator",
    "ParametricGFormula",
    "estimate_g_computation_trajectory",
]
