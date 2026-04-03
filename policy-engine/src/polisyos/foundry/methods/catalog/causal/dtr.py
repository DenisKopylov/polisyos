"""Dynamic Treatment Regime (DTR) estimators.

Implements four methods for estimating optimal dynamic treatment regimes:

  - QLearningDTR:           Backward induction via Q-function regression (Murphy 2005)
  - ALearningDTR:           Contrast/advantage-based learning (Murphy 2003)
  - OutcomeWeightedLearning: Outcome-weighted binary classification (Zhao et al. 2012)
  - DoublyRobustDTR:        Augmented IPW estimator for regime value (Zhang et al. 2013)

All estimators return the optimal dynamic regime d*(H_t) and an estimate of its
value E[Y^{d*}].

References:
    Murphy, S.A. (2003). Optimal dynamic treatment regimes. JRSS-B, 65(2), 331-355.
    Murphy, S.A. (2005). A generalization error for Q-learning. JMLR, 6, 1073-1097.
    Zhao, Y. et al. (2012). Estimating individualized treatment rules using outcome
        weighted learning. JASA, 107(499), 1106-1118.
    Zhang, B. et al. (2013). Robust estimation of optimal dynamic treatment regimes
        for sequential treatment decisions. Biometrika, 100(3), 681-694.
"""
from __future__ import annotations

from typing import Any, ClassVar, Literal, Mapping

import numpy as np
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.svm import SVC

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
from polisyos.foundry.methods.catalog.causal.g_computation import (
    _apply_regime,
    _build_history_matrix,
    _build_temporal_intervention_from_schedule,
    _compat_schedule_from_dynamic_regime,
    _dynamic_input_slots,
    _extract_dynamic_data,
    _fit_propensity_model,
    _ice_estimate,
    _materialize_intervention_schedule,
    _regime_params_from_spec,
    _schedule_from_regime,
    _predict_proba_safe,
    _simulate_regime_trajectory_ensemble,
)
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.foundry.methods.catalog.causal.strategic import evaluate_strategic_hook
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
    DTRResult,
    DynamicTreatmentRegime,
    TemporalInterventionTrajectory,
    RegimeRule,
)

_ASSUMPTIONS = {
    "sequential_ignorability": (
        "A_t ⊥ Y^{ā} | H_t — no unmeasured time-varying confounders"
    ),
    "consistency": "Y = Y^{d} when D = d",
    "positivity": "0 < P(A_t = 1 | H_t) < 1 for all H_t in support",
    "sutva": "No interference between units",
}


# ---------------------------------------------------------------------------
# Shared DTR output slots
# ---------------------------------------------------------------------------


def _dtr_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("result", SlotType.SCALAR, Unit("report", "json")),
            SlotSpec("dtr_result", SlotType.SCALAR, Unit("dtr_result", "json")),
            SlotSpec("warnings", SlotType.SCALAR, Unit("warning", "list")),
        }
    )


def _dtr_base_params() -> tuple[ParameterSpec, ...]:
    return (
        ParameterSpec("n_bootstrap", default=200, bounds=(50, 1000)),
        ParameterSpec("confidence_level", default=0.95, bounds=(0.8, 0.99)),
        ParameterSpec("outcome_model", default="linear"),
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _fit_q_function(
    H_t_A: np.ndarray, pseudo_Y: np.ndarray
) -> LinearRegression:
    """Fit Q_t(H_t, A_t) = E[pseudo_Y | H_t, A_t] via OLS."""
    m = LinearRegression()
    m.fit(H_t_A, pseudo_Y)
    return m


def _q_value(
    q_model: LinearRegression,
    H_t: np.ndarray,
    a: "float | np.ndarray",
    n_cov: int = 0,
) -> np.ndarray:
    """Predict Q_t(H_t, a) for all units under action a (scalar or per-unit array).

    When n_cov > 0 the last n_cov columns of H_t are treated as the current
    covariates L_t and an A_t × L_t interaction block is appended so that the
    feature layout matches models trained with interaction augmentation.
    """
    a_arr = np.asarray(a)
    if a_arr.ndim == 0:
        a_col = np.full((H_t.shape[0], 1), float(a_arr))
    else:
        a_col = a_arr.reshape(-1, 1)
    if n_cov > 0:
        L_t = H_t[:, -n_cov:]
        X = np.hstack([H_t, a_col, a_col * L_t])
    else:
        X = np.hstack([H_t, a_col])
    return q_model.predict(X)


def _optimal_q_action(
    q_model: LinearRegression, H_t: np.ndarray, n_cov: int = 0
) -> np.ndarray:
    """Return argmax_a Q(H_t, a) ∈ {0, 1} for each unit."""
    q1 = _q_value(q_model, H_t, 1.0, n_cov)
    q0 = _q_value(q_model, H_t, 0.0, n_cov)
    return (q1 > q0).astype(float)


def _estimate_value_ice(
    Y: np.ndarray,
    A_seq: np.ndarray,
    L_seq: np.ndarray,
    regime: DynamicTreatmentRegime,
) -> float:
    """Estimate E[Y^{d*}] using ICE g-formula with the optimal regime."""
    regime_params = {
        "regime": regime.rule.value,
        "threshold_covariate_index": regime.threshold_covariate_index,
        "threshold_value": regime.threshold_value,
    }
    return _ice_estimate(Y, A_seq, L_seq, regime_params)


def _regime_from_q_models(
    q_models: list[LinearRegression],
    L_seq: np.ndarray,
    A_seq: np.ndarray,
    n_cov: int = 0,
) -> DynamicTreatmentRegime:
    """Derive a DynamicTreatmentRegime from fitted Q-function models.

    We examine if the optimal rule is always-treat or never-treat;
    otherwise approximate as a threshold rule on the first covariate.
    """
    n_periods = len(q_models)
    time_points = tuple(range(n_periods))
    treatment_vars = tuple(f"A_{t}" for t in range(n_periods))
    cov_vars = tuple(f"L_{t}" for t in range(n_periods))

    # Check first stage: apply to all units
    H0 = _build_history_matrix(A_seq, L_seq, 0)
    optimal_a0 = _optimal_q_action(q_models[0], H0, n_cov)
    frac_treated = float(np.mean(optimal_a0))

    if frac_treated >= 0.95:
        rule = RegimeRule.ALWAYS_TREAT
        threshold_value = 0.0
    elif frac_treated <= 0.05:
        rule = RegimeRule.NEVER_TREAT
        threshold_value = 0.0
    else:
        # Approximate threshold on first covariate
        L0 = L_seq[:, 0, 0]
        # Find median of L among treated units
        threshold_value = float(np.median(L0[optimal_a0 == 1])) if frac_treated > 0 else 0.0
        rule = RegimeRule.THRESHOLD

    # Collect Q-function coefficients (first stage)
    coefs = list(q_models[0].coef_) + [float(q_models[0].intercept_)]

    return DynamicTreatmentRegime(
        time_points=time_points,
        treatment_variables=treatment_vars,
        time_varying_covariates=cov_vars,
        outcome="Y",
        rule=rule,
        threshold_covariate_index=0,
        threshold_value=threshold_value,
        regime_coefficients=tuple(float(c) for c in coefs),
    )


def _build_dtr_output(
    *,
    method_enum: CausalMethod,
    estimand_str: str,
    dtr_result: DTRResult,
    n_units: int,
    n_periods: int,
    n_treated: int,
    warnings: list[str],
    params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    report = build_success_report(
        method=method_enum,
        estimand=estimand_str,
        point_estimate=dtr_result.value_estimate,
        confidence_interval=dtr_result.value_ci,
        inference_method="bootstrap",
        sample_size=n_units,
        n_treated=n_treated,
        n_control=n_units - n_treated,
        pre_periods=n_periods,
        post_periods=0,
        assumptions=dict(_ASSUMPTIONS),
        metadata={
            "dtr_method": dtr_result.method,
            "n_stages": dtr_result.n_stages,
            "optimal_regime_rule": dtr_result.optimal_regime.rule.value,
        },
    )
    extras: dict[str, Any] = {"dtr_result": dtr_result}
    if params:
        strategic_summary, strategic_warnings, _strategic_bundle = evaluate_strategic_hook(
            params=params,
            baseline_policy_value=dtr_result.value_estimate,
        )
        if strategic_summary is not None:
            warnings.extend(
                warning for warning in strategic_warnings if warning not in warnings
            )
            dtr_result.metadata["strategic_response"] = strategic_summary
            report.metadata["strategic_response"] = strategic_summary
            report.metadata["strategic_response_present"] = True
            extras["strategic_response_summary"] = strategic_summary
    return wrap_causal_output(report, warnings=warnings, extras=extras)


def estimate_dtr_trajectory(
    data: DynamicTreatmentData | dict[str, Any],
    query: ContinuousTimeQuery,
    *,
    resolved_intervention: TemporalInterventionTrajectory | dict[str, Any] | None = None,
    intervention_contract_status: str | None = None,
    method: Literal["q_learning", "a_learning", "owl", "dr_dtr"] = "q_learning",
    method_params: Mapping[str, Any] | None = None,
    allow_discrete_fallback: bool = True,
) -> tuple[DTRResult, TemporalTrajectoryResult]:
    """Return scalar DTR output plus a temporal policy-value trajectory."""

    dynamic_data = _extract_dynamic_data(data)
    method_dispatch: dict[str, type] = {
        "q_learning": QLearningDTR,
        "a_learning": ALearningDTR,
        "owl": OutcomeWeightedLearning,
        "dr_dtr": DoublyRobustDTR,
    }
    method_cls = method_dispatch.get(method)
    if method_cls is None:
        raise ValueError(
            f"Unknown DTR temporal method {method!r}. Choose from: {sorted(method_dispatch)}"
        )

    scalar_result = method_cls.pure_step(dynamic_data, dict(method_params or {}))
    dtr_result = scalar_result.get("dtr_result")
    if not isinstance(dtr_result, DTRResult):
        raise RuntimeError("Temporal DTR helper expected a DTRResult payload")

    intervention = (
        None
        if resolved_intervention is None
        else (
            resolved_intervention
            if isinstance(resolved_intervention, TemporalInterventionTrajectory)
            else TemporalInterventionTrajectory.model_validate(resolved_intervention)
        )
    )
    contract_status = (
        str(intervention_contract_status)
        if intervention_contract_status is not None
        else ("resolved_artifact" if intervention is not None else "compatibility_synthesized")
    )
    full_time_grid = (
        np.arange(dynamic_data.n_periods, dtype=float)
        if dynamic_data.time_ids is None
        else np.asarray(dynamic_data.time_ids, dtype=float)
    )
    if intervention is None:
        intervention = _build_temporal_intervention_from_schedule(
            query=query,
            time_grid=full_time_grid,
            schedule=_compat_schedule_from_dynamic_regime(
                dtr_result.optimal_regime,
                data=dynamic_data,
            ),
            metadata={"contract_status": contract_status, "derived_from_optimal_regime": True},
        )
    else:
        expected_schedule = _schedule_from_regime(
            dtr_result.optimal_regime,
            time_grid=full_time_grid,
        )
        intervention_schedule = _materialize_intervention_schedule(
            intervention,
            time_grid=full_time_grid,
        )
        if intervention_schedule != expected_schedule:
            raise TemporalCompileError(
                "intervention_regime_mismatch",
                "Resolved intervention artifact does not match the DTR optimal regime on the compiled grid.",
                details={
                    "expected_schedule": list(expected_schedule),
                    "intervention_schedule": list(intervention_schedule),
                },
            )

    plan = compile_temporal_estimand(
        query,
        data=dynamic_data,
        resolved_intervention=intervention,
        intervention_contract_status=contract_status,
        allow_discrete_fallback=allow_discrete_fallback,
    )

    optimal_params = _regime_params_from_spec(dtr_result.optimal_regime)
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
        regime_params=optimal_params,
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
            "optimal_regime_rule": dtr_result.optimal_regime.rule.value,
            "scalar_method": dtr_result.method,
            "outcome_process": query.outcome_process,
            "intervention_contract_status": contract_status,
        }
    )
    trajectory.diagnostics["optimal_regime_rule"] = dtr_result.optimal_regime.rule.value
    trajectory.diagnostics["scalar_value_estimate"] = float(dtr_result.value_estimate)
    strategic_summary = scalar_result.get("strategic_response_summary")
    if isinstance(strategic_summary, dict):
        trajectory.metadata["strategic_response"] = dict(strategic_summary)
        trajectory.diagnostics["strategic_fallback_mode"] = str(
            strategic_summary.get("fallback_mode")
        )
    return dtr_result, trajectory


# ---------------------------------------------------------------------------
# 1. Q-learning
# ---------------------------------------------------------------------------


@foundry_method(namespace="causal.dynamic.q_learning", version="1.0.0")
class QLearningDTR:
    """Q-learning for Dynamic Treatment Regimes (Murphy 2005).

    Backward induction over stages: at each stage t, fits a Q-function
    Q_t(H_t, A_t) = E[V_{t+1}^{d*} | H_t, A_t] via linear regression, where
    V_{t+1}^{d*} = max_a Q_{t+1}(H_{t+1}, a).

    The optimal regime d*_t(H_t) = argmax_a Q_t(H_t, a).

    References:
        Murphy, S.A. (2005). A generalization error for Q-learning. JMLR, 6, 1073-1097.
        Chakraborty, B. & Moodie, E.E.M. (2013). Statistical Methods for Dynamic
            Treatment Regimes. Springer.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="q_learning",
        namespace="placeholder",
        version="0.0.0",
        input_slots=_dynamic_input_slots(),
        output_slots=_dtr_output_slots(),
        parameters=_dtr_base_params(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Q-learning for optimal dynamic treatment regimes. "
            "Backward induction via sequential Q-function regression."
        ),
        tags=frozenset(
            {"causal", "dynamic", "dtr", "q_learning", "longitudinal", "treatment_regime"}
        ),
        citations=(
            "Murphy, S.A. (2005). A generalization error for Q-learning. JMLR, 6, 1073-1097.",
            "Chakraborty & Moodie (2013). Statistical Methods for Dynamic Treatment Regimes.",
        ),
        equations={
            "q_backward": (
                "Q_T(H_T, A_T) = E[Y | H_T, A_T]; "
                "Q_t = E[max_a Q_{t+1}(H_{t+1}, a) | H_t, A_t]"
            ),
            "optimal": "d*_t(H_t) = argmax_{a∈{0,1}} Q_t(H_t, a)",
        },
        assumptions=dict(_ASSUMPTIONS),
        when_to_use=(
            "Multi-stage treatment decisions with time-varying confounders; "
            "when Q-function can be approximated linearly."
        ),
        when_not_to_use="Highly non-linear Q-functions; use OWL or DR-DTR.",
        typical_min_obs=80,
        output_interpretation=(
            "value_estimate = E[Y^{d*}]: expected outcome under optimal regime. "
            "optimal_regime contains the decision rule at each stage."
        ),
    )

    @staticmethod
    def pure_step(
        state: DynamicTreatmentData, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        try:
            data = _extract_dynamic_data(state)
        except Exception as exc:
            dummy = build_failure_report(
                method=CausalMethod.Q_LEARNING_DTR,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="E[Y^{d*}]",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions={},
            )
            return wrap_causal_output(dummy, extras={"dtr_result": None})

        Y = data.outcome.astype(float)
        A_seq = data.treatment_sequence.astype(float)
        L_seq = data.covariate_sequence.astype(float)
        n_units, n_periods = data.n_units, data.n_periods
        n_boot = int(params.get("n_bootstrap", 200))
        conf_level = float(params.get("confidence_level", 0.95))

        if n_units < 20:
            dummy = build_failure_report(
                method=CausalMethod.Q_LEARNING_DTR,
                status=EstimationStatus.INPUT_INVALID,
                reason="Need at least 20 units for Q-learning",
                estimand="E[Y^{d*}]",
                sample_size=n_units,
                n_treated=0,
                n_control=0,
                pre_periods=n_periods,
                post_periods=0,
                assumptions=dict(_ASSUMPTIONS),
            )
            return wrap_causal_output(dummy, extras={"dtr_result": None})

        _n_cov = L_seq.shape[2]

        def _run_q_learning(
            Y_b: np.ndarray, A_b: np.ndarray, L_b: np.ndarray
        ) -> tuple[float, list[LinearRegression]]:
            """Return (value_estimate, list_of_Q_models).

            Feature matrix at each stage is augmented with A_t × L_t interaction
            terms so that linear Q-functions can capture state-conditional
            treatment heterogeneity (e.g. 1.4*A*(L>0) - 0.7*A*(L<=0) patterns).
            """
            pseudo_Y = Y_b.copy().astype(float)
            q_models: list[LinearRegression] = []

            for t in range(n_periods - 1, -1, -1):
                H_t = _build_history_matrix(A_b, L_b, t)
                A_t = A_b[:, t : t + 1]
                L_t = L_b[:, t, :]          # current covariates (also last _n_cov cols of H_t)
                interact = A_t * L_t        # shape (n_units, n_cov)
                X_t = np.hstack([H_t, A_t, interact])
                q_t = _fit_q_function(X_t, pseudo_Y)
                q_models.insert(0, q_t)
                # Pseudo-Y for next stage = max_a Q_t(H_t, a)
                q1 = _q_value(q_t, H_t, 1.0, _n_cov)
                q0 = _q_value(q_t, H_t, 0.0, _n_cov)
                pseudo_Y = np.maximum(q1, q0)

            # Estimate value: apply optimal regime from stage 0
            H0 = _build_history_matrix(A_b, L_b, 0)
            a0 = _optimal_q_action(q_models[0], H0, _n_cov)
            value = float(np.mean(_q_value(q_models[0], H0, 1.0, _n_cov) * a0
                                  + _q_value(q_models[0], H0, 0.0, _n_cov) * (1 - a0)))
            return value, q_models

        point_value, q_models_fit = _run_q_learning(Y, A_seq, L_seq)

        rng = np.random.default_rng(42)
        boot_values = np.empty(n_boot)
        for b in range(n_boot):
            idx = rng.integers(0, n_units, size=n_units)
            bv, _ = _run_q_learning(Y[idx], A_seq[idx], L_seq[idx])
            boot_values[b] = bv

        ci = bootstrap_ci(boot_values, conf_level)
        lo = min(float(ci[0]), point_value)
        hi = max(float(ci[1]), point_value)

        optimal_regime = _regime_from_q_models(q_models_fit, L_seq, A_seq, _n_cov)
        stage_coefs = tuple(
            tuple(float(c) for c in list(m.coef_) + [float(m.intercept_)])
            for m in q_models_fit
        )
        n_treated = int(np.sum(A_seq[:, 0]))

        dtr_result = DTRResult(
            method="q_learning",
            optimal_regime=optimal_regime,
            value_estimate=point_value,
            value_ci=(lo, hi),
            n_units=n_units,
            n_stages=n_periods,
            stage_coefficients=stage_coefs,
        )
        return _build_dtr_output(
            method_enum=CausalMethod.Q_LEARNING_DTR,
            estimand_str="E[Y^{d*}] optimal dynamic regime value",
            dtr_result=dtr_result,
            n_units=n_units,
            n_periods=n_periods,
            n_treated=n_treated,
            warnings=[],
            params=params,
        )


# ---------------------------------------------------------------------------
# 2. A-learning
# ---------------------------------------------------------------------------


@foundry_method(namespace="causal.dynamic.a_learning", version="1.0.0")
class ALearningDTR:
    """A-learning (Advantage-learning) for Dynamic Treatment Regimes (Murphy 2003).

    Models the contrast (blip-to-reference) C_t(H_t, A_t) = Q_t(H_t, A_t) - Q_t(H_t, 0)
    instead of the full Q-function.  This avoids modelling the baseline Q_t(H_t, 0),
    which can reduce bias when baseline model is misspecified.

    Optimal regime: d*_t(H_t) = 1  if  C_t(H_t, 1) > 0.

    References:
        Murphy, S.A. (2003). Optimal dynamic treatment regimes. JRSS-B, 65(2), 331-355.
        Robins, J.M. (2004). Optimal structural nested models for optimal sequential
            decisions. Springer Proceedings in Statistics.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="a_learning",
        namespace="placeholder",
        version="0.0.0",
        input_slots=_dynamic_input_slots(),
        output_slots=_dtr_output_slots(),
        parameters=_dtr_base_params(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "A-learning (advantage/contrast-based) for optimal DTR. "
            "Models the blip-to-reference C_t = Q_t(H, A) - Q_t(H, 0) "
            "instead of the full Q-function."
        ),
        tags=frozenset(
            {"causal", "dynamic", "dtr", "a_learning", "advantage_learning", "treatment_regime"}
        ),
        citations=(
            "Murphy, S.A. (2003). Optimal dynamic treatment regimes. JRSS-B, 65(2), 331-355.",
            "Robins (2004). Optimal structural nested models for sequential decisions.",
        ),
        equations={
            "blip_to_ref": "C_t(H_t, A_t) = Q_t(H_t, A_t) - Q_t(H_t, 0)",
            "optimal": "d*_t(H_t) = 1  iff  C_t(H_t, 1) > 0",
        },
        assumptions=dict(_ASSUMPTIONS),
        when_to_use=(
            "When baseline expected outcomes are hard to model; "
            "A-learning is more robust to baseline misspecification than Q-learning."
        ),
        when_not_to_use=(
            "Very small T (< 2) or when full Q-function is needed for planning."
        ),
        typical_min_obs=80,
        output_interpretation=(
            "value_estimate = E[Y^{d*}] under the advantage-based optimal regime."
        ),
    )

    @staticmethod
    def pure_step(
        state: DynamicTreatmentData, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        try:
            data = _extract_dynamic_data(state)
        except Exception as exc:
            dummy = build_failure_report(
                method=CausalMethod.A_LEARNING_DTR,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="E[Y^{d*}]",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions={},
            )
            return wrap_causal_output(dummy, extras={"dtr_result": None})

        Y = data.outcome.astype(float)
        A_seq = data.treatment_sequence.astype(float)
        L_seq = data.covariate_sequence.astype(float)
        n_units, n_periods = data.n_units, data.n_periods
        n_boot = int(params.get("n_bootstrap", 200))
        conf_level = float(params.get("confidence_level", 0.95))

        if n_units < 20:
            dummy = build_failure_report(
                method=CausalMethod.A_LEARNING_DTR,
                status=EstimationStatus.INPUT_INVALID,
                reason="Need at least 20 units for A-learning",
                estimand="E[Y^{d*}]",
                sample_size=n_units,
                n_treated=0,
                n_control=0,
                pre_periods=n_periods,
                post_periods=0,
                assumptions=dict(_ASSUMPTIONS),
            )
            return wrap_causal_output(dummy, extras={"dtr_result": None})

        def _run_a_learning(
            Y_b: np.ndarray, A_b: np.ndarray, L_b: np.ndarray
        ) -> tuple[float, list[np.ndarray]]:
            """Return (value_estimate, blip_coef_per_stage)."""
            pseudo_Y = Y_b.copy().astype(float)
            blip_coefs: list[np.ndarray] = []
            optimal_actions: list[np.ndarray] = []

            for t in range(n_periods - 1, -1, -1):
                H_t = _build_history_matrix(A_b, L_b, t)
                A_t = A_b[:, t]

                # Fit propensity π_t
                pm = _fit_propensity_model(H_t, A_t)
                pi_t = _predict_proba_safe(pm, H_t)

                # Center treatment: Ã_t = A_t - π_t
                A_centered = A_t - pi_t

                # Fit outcome model with centered treatment (A-learning)
                # μ(H_t) + γ(A_t - π_t) where γ is the blip coefficient
                X_aug = np.hstack([H_t, A_centered.reshape(-1, 1)])
                m = LinearRegression()
                m.fit(X_aug, pseudo_Y)
                blip_coef = m.coef_[-1]  # coefficient on A_centered
                blip_coefs.insert(0, np.array([blip_coef]))

                # Optimal action at stage t: treat iff blip_coef > 0 (for linear case)
                # (since γ(a - π) → positive blip ⟹ treat)
                opt_a = (blip_coef > 0).astype(float) * np.ones(len(A_t))
                optimal_actions.insert(0, opt_a)

                # Pseudo-Y update: apply optimal action
                mu_H = m.predict(np.hstack([H_t, np.zeros((len(A_t), 1))]))
                blip_opt = blip_coef * (opt_a - pi_t)
                pseudo_Y = mu_H + blip_opt

            # Value estimate = mean of stage-0 pseudo-Y
            value = float(np.mean(pseudo_Y))
            return value, blip_coefs

        point_value, blip_coefs = _run_a_learning(Y, A_seq, L_seq)

        rng = np.random.default_rng(42)
        boot_values = np.empty(n_boot)
        for b in range(n_boot):
            idx = rng.integers(0, n_units, size=n_units)
            bv, _ = _run_a_learning(Y[idx], A_seq[idx], L_seq[idx])
            boot_values[b] = bv

        ci = bootstrap_ci(boot_values, conf_level)
        lo = min(float(ci[0]), point_value)
        hi = max(float(ci[1]), point_value)

        # Determine optimal regime from blip coefficients
        n_periods_blip = len(blip_coefs)
        time_points = tuple(range(n_periods_blip))
        treatment_vars = tuple(f"A_{t}" for t in range(n_periods_blip))
        cov_vars = tuple(f"L_{t}" for t in range(n_periods_blip))
        main_blip = float(blip_coefs[0][0]) if blip_coefs else 0.0
        rule = RegimeRule.ALWAYS_TREAT if main_blip > 0 else RegimeRule.NEVER_TREAT

        optimal_regime = DynamicTreatmentRegime(
            time_points=time_points,
            treatment_variables=treatment_vars,
            time_varying_covariates=cov_vars,
            outcome="Y",
            rule=rule,
            regime_coefficients=tuple(float(c[0]) for c in blip_coefs),
        )
        stage_coefs = tuple(
            tuple(float(c) for c in coef) for coef in blip_coefs
        )
        n_treated = int(np.sum(A_seq[:, 0]))

        dtr_result = DTRResult(
            method="a_learning",
            optimal_regime=optimal_regime,
            value_estimate=point_value,
            value_ci=(lo, hi),
            n_units=n_units,
            n_stages=n_periods,
            stage_coefficients=stage_coefs,
        )
        return _build_dtr_output(
            method_enum=CausalMethod.A_LEARNING_DTR,
            estimand_str="E[Y^{d*}] via A-learning",
            dtr_result=dtr_result,
            n_units=n_units,
            n_periods=n_periods,
            n_treated=n_treated,
            warnings=[],
            params=params,
        )


# ---------------------------------------------------------------------------
# 3. Outcome-Weighted Learning (OWL)
# ---------------------------------------------------------------------------


@foundry_method(namespace="causal.dynamic.owl", version="1.0.0")
class OutcomeWeightedLearning:
    """Outcome-Weighted Learning (OWL) for DTR (Zhao et al. 2012).

    Reformulates DTR estimation as a weighted binary classification problem:
        Minimize:  -E[w_i · I(d(H_i) = A_i)]
        where:     w_i = Y_i / π(A_i | H_i)  (IPW weighted by outcome)

    Solved via weighted SVM (sklearn SVC with sample_weight).
    Applied per-stage in backward induction, using pseudo-outcomes as weights.

    References:
        Zhao, Y. et al. (2012). Estimating individualized treatment rules
            using outcome weighted learning. JASA, 107(499), 1106-1118.
        Zhao, Y. et al. (2015). New statistical learning methods for estimating
            optimal dynamic treatment regimes. JASA, 110(510), 583-598.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="owl",
        namespace="placeholder",
        version="0.0.0",
        input_slots=_dynamic_input_slots(),
        output_slots=_dtr_output_slots(),
        parameters=_dtr_base_params()
        + (ParameterSpec("kernel", default="linear"),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Outcome-Weighted Learning: reformulates DTR as IPW-weighted classification. "
            "Non-parametric; does not assume a linear Q-function."
        ),
        tags=frozenset(
            {
                "causal",
                "dynamic",
                "dtr",
                "owl",
                "outcome_weighted",
                "svm",
                "treatment_regime",
            }
        ),
        citations=(
            "Zhao, Y. et al. (2012). Estimating individualized treatment rules "
            "using outcome weighted learning. JASA, 107(499), 1106-1118.",
        ),
        equations={
            "owl_obj": "max_d E[Y · I(d(H)=A) / π(A|H)]",
            "weight": "w_i = Y_i / π(A_i | H_i)",
        },
        assumptions=dict(_ASSUMPTIONS),
        when_to_use=(
            "When Q-function is non-linear; OWL is non-parametric and can learn "
            "complex decision boundaries."
        ),
        when_not_to_use=(
            "Very small samples (SVM needs ≥ 30 per stage) or negative outcomes "
            "(weights w_i = Y_i/π can be negative, making SVM ill-defined; "
            "shift Y by max|Y| first)."
        ),
        typical_min_obs=100,
        output_interpretation=(
            "value_estimate = E[Y^{d*}] estimated via OWL weighted SVM. "
            "May be slightly conservative due to SVM margin."
        ),
    )

    @staticmethod
    def pure_step(
        state: DynamicTreatmentData, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        try:
            data = _extract_dynamic_data(state)
        except Exception as exc:
            dummy = build_failure_report(
                method=CausalMethod.OUTCOME_WEIGHTED_LEARNING,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="E[Y^{d*}]",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions={},
            )
            return wrap_causal_output(dummy, extras={"dtr_result": None})

        Y = data.outcome.astype(float)
        A_seq = data.treatment_sequence.astype(float)
        L_seq = data.covariate_sequence.astype(float)
        n_units, n_periods = data.n_units, data.n_periods
        n_boot = int(params.get("n_bootstrap", 200))
        conf_level = float(params.get("confidence_level", 0.95))
        kernel = str(params.get("kernel", "linear"))

        if n_units < 20:
            dummy = build_failure_report(
                method=CausalMethod.OUTCOME_WEIGHTED_LEARNING,
                status=EstimationStatus.INPUT_INVALID,
                reason="Need at least 20 units for OWL",
                estimand="E[Y^{d*}]",
                sample_size=n_units,
                n_treated=0,
                n_control=0,
                pre_periods=n_periods,
                post_periods=0,
                assumptions=dict(_ASSUMPTIONS),
            )
            return wrap_causal_output(dummy, extras={"dtr_result": None})

        def _run_owl(
            Y_b: np.ndarray, A_b: np.ndarray, L_b: np.ndarray
        ) -> tuple[float, list[Any]]:
            # Shift Y to be positive for valid OWL weights
            Y_shift = Y_b - np.min(Y_b) + 1e-3
            pseudo_Y = Y_shift.copy()
            svm_models: list[Any] = []

            for t in range(n_periods - 1, -1, -1):
                H_t = _build_history_matrix(A_b, L_b, t)
                A_t = A_b[:, t]

                pm = _fit_propensity_model(H_t, A_t)
                pi_t = _predict_proba_safe(pm, H_t)
                prob_A = np.where(A_t == 1, pi_t, 1 - pi_t)

                # OWL weights: w_i = pseudo_Y_i / P(A_t_i | H_t_i)
                w = np.abs(pseudo_Y) / np.clip(prob_A, 1e-4, None)
                w = np.clip(w, 0, np.percentile(w, 99))  # trim extreme weights
                if w.sum() < 1e-10:
                    w = np.ones_like(w)

                # Relabel: +1 if treating A_t=1 is desirable, -1 otherwise
                # Standard OWL: labels = 2*A_t - 1, weight = w
                labels = (2 * A_t - 1).astype(int)

                if len(np.unique(labels)) < 2:
                    svm = None
                    svm_models.insert(0, svm)
                    pseudo_Y = pseudo_Y  # no update
                    continue

                try:
                    svm = SVC(kernel=kernel, C=1.0)
                    svm.fit(H_t, labels, sample_weight=w)
                except Exception:
                    svm = None

                svm_models.insert(0, svm)

                # Update pseudo-Y: predicted regime value
                if svm is not None:
                    pred = svm.predict(H_t)  # +1 or -1
                    opt_a = (pred > 0).astype(float)
                else:
                    opt_a = np.ones(len(A_t))

                # Pseudo-Y for next stage: IPW estimate under optimal action
                indicator = (A_t == opt_a).astype(float)
                pseudo_Y = pseudo_Y * indicator / np.clip(prob_A, 1e-4, None)
                pseudo_Y = np.clip(pseudo_Y, -1e6, 1e6)

            value = float(np.mean(pseudo_Y))
            return value, svm_models

        point_value, svm_models = _run_owl(Y, A_seq, L_seq)

        rng = np.random.default_rng(42)
        boot_values = np.empty(n_boot)
        for b in range(n_boot):
            idx = rng.integers(0, n_units, size=n_units)
            bv, _ = _run_owl(Y[idx], A_seq[idx], L_seq[idx])
            boot_values[b] = bv
        boot_values = boot_values[np.isfinite(boot_values)]
        if len(boot_values) == 0:
            boot_values = np.array([point_value])

        ci = bootstrap_ci(boot_values, conf_level)
        lo = min(float(ci[0]), point_value)
        hi = max(float(ci[1]), point_value)

        # Regime: derive from SVM decision on training data
        H0 = _build_history_matrix(A_seq, L_seq, 0)
        svm0 = svm_models[0] if svm_models else None
        if svm0 is not None:
            pred0 = svm0.predict(H0)
            frac_treat = float(np.mean(pred0 > 0))
        else:
            frac_treat = 1.0
        rule = RegimeRule.ALWAYS_TREAT if frac_treat > 0.5 else RegimeRule.NEVER_TREAT

        time_points = tuple(range(n_periods))
        treatment_vars = tuple(f"A_{t}" for t in range(n_periods))
        cov_vars = tuple(f"L_{t}" for t in range(n_periods))
        optimal_regime = DynamicTreatmentRegime(
            time_points=time_points,
            treatment_variables=treatment_vars,
            time_varying_covariates=cov_vars,
            outcome="Y",
            rule=rule,
        )
        n_treated = int(np.sum(A_seq[:, 0]))

        dtr_result = DTRResult(
            method="owl",
            optimal_regime=optimal_regime,
            value_estimate=point_value,
            value_ci=(lo, hi),
            n_units=n_units,
            n_stages=n_periods,
            stage_coefficients=(),
        )
        return _build_dtr_output(
            method_enum=CausalMethod.OUTCOME_WEIGHTED_LEARNING,
            estimand_str="E[Y^{d*}] via outcome-weighted SVM",
            dtr_result=dtr_result,
            n_units=n_units,
            n_periods=n_periods,
            n_treated=n_treated,
            warnings=["OWL value estimate uses IPW and may have high variance with small samples."],
            params=params,
        )


# ---------------------------------------------------------------------------
# 4. Doubly Robust DTR
# ---------------------------------------------------------------------------


@foundry_method(namespace="causal.dynamic.dr_dtr", version="1.0.0")
class DoublyRobustDTR:
    """Doubly Robust estimator for Dynamic Treatment Regime value (Zhang et al. 2013).

    Augments the IPW value estimator with an outcome model for double robustness:
        V^{DR}(d) = E[Y · ρ − (ρ − 1) · Q̃(H, d(H))]
        where ρ = Π_t I(A_t=d_t(H_t)) / π_t(A_t|H_t)

    The optimal regime is first estimated via Q-learning, then its value is
    re-estimated with this doubly-robust formula.

    References:
        Zhang, B. et al. (2013). Robust estimation of optimal dynamic treatment
            regimes for sequential treatment decisions. Biometrika, 100(3), 681-694.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="dr_dtr",
        namespace="placeholder",
        version="0.0.0",
        input_slots=_dynamic_input_slots(),
        output_slots=_dtr_output_slots(),
        parameters=_dtr_base_params(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Doubly-robust estimator for DTR value. "
            "First finds optimal regime via Q-learning, then estimates its value "
            "with a doubly-robust augmented IPW formula."
        ),
        tags=frozenset(
            {
                "causal",
                "dynamic",
                "dtr",
                "doubly_robust",
                "augmented_ipw",
                "treatment_regime",
            }
        ),
        citations=(
            "Zhang, B. et al. (2013). Robust estimation of optimal dynamic "
            "treatment regimes. Biometrika, 100(3), 681-694.",
        ),
        equations={
            "dr_value": "V^{DR}(d) = E[Y·ρ − (ρ−1)·Q̃(H,d(H))]",
            "ipw_weight": "ρ = Π_t I(A_t=d_t(H_t)) / π_t(A_t|H_t)",
        },
        assumptions=dict(_ASSUMPTIONS),
        when_to_use=(
            "When either the outcome model or propensity model may be misspecified; "
            "consistent if at least one is correctly specified."
        ),
        when_not_to_use="Both models severely misspecified; use with Super Learner nuisance.",
        typical_min_obs=100,
        output_interpretation=(
            "Doubly-robust estimate of E[Y^{d*}]. Preferable over pure IPW "
            "or outcome-regression when model uncertainty is high."
        ),
    )

    @staticmethod
    def pure_step(
        state: DynamicTreatmentData, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        try:
            data = _extract_dynamic_data(state)
        except Exception as exc:
            dummy = build_failure_report(
                method=CausalMethod.DOUBLY_ROBUST_DTR,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="V^{DR}(d*)",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions={},
            )
            return wrap_causal_output(dummy, extras={"dtr_result": None})

        Y = data.outcome.astype(float)
        A_seq = data.treatment_sequence.astype(float)
        L_seq = data.covariate_sequence.astype(float)
        n_units, n_periods = data.n_units, data.n_periods
        n_boot = int(params.get("n_bootstrap", 200))
        conf_level = float(params.get("confidence_level", 0.95))

        if n_units < 20:
            dummy = build_failure_report(
                method=CausalMethod.DOUBLY_ROBUST_DTR,
                status=EstimationStatus.INPUT_INVALID,
                reason="Need at least 20 units for DR-DTR",
                estimand="V^{DR}(d*)",
                sample_size=n_units,
                n_treated=0,
                n_control=0,
                pre_periods=n_periods,
                post_periods=0,
                assumptions=dict(_ASSUMPTIONS),
            )
            return wrap_causal_output(dummy, extras={"dtr_result": None})

        def _run_dr_dtr(
            Y_b: np.ndarray, A_b: np.ndarray, L_b: np.ndarray
        ) -> tuple[float, list[LinearRegression], DynamicTreatmentRegime]:
            # Step 1: Q-learning for optimal regime
            pseudo_Y = Y_b.copy().astype(float)
            q_models: list[LinearRegression] = []
            for t in range(n_periods - 1, -1, -1):
                H_t = _build_history_matrix(A_b, L_b, t)
                X_t = np.hstack([H_t, A_b[:, t : t + 1]])
                q_t = _fit_q_function(X_t, pseudo_Y)
                q_models.insert(0, q_t)
                q1 = _q_value(q_t, H_t, 1.0)
                q0 = _q_value(q_t, H_t, 0.0)
                pseudo_Y = np.maximum(q1, q0)

            optimal_regime = _regime_from_q_models(q_models, L_b, A_b)

            # Step 2: DR value estimator
            # For each unit: compute ρ_i = Π_t I(A_t = d*_t(H_t)) / π_t(A_t|H_t)
            log_ratio = np.zeros(len(Y_b))
            q_under_regime = np.zeros(len(Y_b))
            for t in range(n_periods):
                H_t = _build_history_matrix(A_b, L_b, t)
                L_t = L_b[:, t, :]
                pm = _fit_propensity_model(H_t, A_b[:, t])
                pi_t = _predict_proba_safe(pm, H_t)
                prob_obs = np.where(A_b[:, t] == 1, pi_t, 1 - pi_t)
                d_star_t = _apply_regime(
                    H_t, L_t,
                    optimal_regime.rule.value,
                    optimal_regime.threshold_covariate_index,
                    optimal_regime.threshold_value,
                )
                prob_regime = np.where(d_star_t == 1, pi_t, 1 - pi_t)
                log_ratio += np.log(np.clip(prob_regime / prob_obs, 1e-8, None))
                # Q-function prediction under regime
                q_under_regime += _q_value(q_models[t], H_t, d_star_t)

            rho = np.exp(np.clip(log_ratio, -10, 10))  # cumulative IS ratio
            q_under_regime /= n_periods  # average Q across periods (simplification)

            # DR estimator: V^{DR} = E[Y * ρ - (ρ - 1) * Q̃(H, d*)]
            dr_scores = Y_b * rho - (rho - 1.0) * q_under_regime
            value = float(np.mean(dr_scores))
            return value, q_models, optimal_regime

        point_value, q_models_fit, optimal_regime = _run_dr_dtr(Y, A_seq, L_seq)

        rng = np.random.default_rng(42)
        boot_values = np.empty(n_boot)
        for b in range(n_boot):
            idx = rng.integers(0, n_units, size=n_units)
            bv, _, _ = _run_dr_dtr(Y[idx], A_seq[idx], L_seq[idx])
            boot_values[b] = bv
        boot_values = boot_values[np.isfinite(boot_values)]
        if len(boot_values) == 0:
            boot_values = np.array([point_value])

        ci = bootstrap_ci(boot_values, conf_level)
        lo = min(float(ci[0]), point_value)
        hi = max(float(ci[1]), point_value)

        stage_coefs = tuple(
            tuple(float(c) for c in list(m.coef_) + [float(m.intercept_)])
            for m in q_models_fit
        )
        n_treated = int(np.sum(A_seq[:, 0]))

        dtr_result = DTRResult(
            method="dr_dtr",
            optimal_regime=optimal_regime,
            value_estimate=point_value,
            value_ci=(lo, hi),
            n_units=n_units,
            n_stages=n_periods,
            stage_coefficients=stage_coefs,
        )
        return _build_dtr_output(
            method_enum=CausalMethod.DOUBLY_ROBUST_DTR,
            estimand_str="V^{DR}(d*): doubly-robust optimal DTR value",
            dtr_result=dtr_result,
            n_units=n_units,
            n_periods=n_periods,
            n_treated=n_treated,
            warnings=[],
            params=params,
        )


__all__ = [
    "ALearningDTR",
    "DoublyRobustDTR",
    "DTRResult",
    "OutcomeWeightedLearning",
    "QLearningDTR",
    "estimate_dtr_trajectory",
]
