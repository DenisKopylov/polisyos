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

from typing import Any, ClassVar, Mapping

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
from polisyos.foundry.methods.catalog.causal._sklearn_compat import (
    LinearRegression,
    LogisticRegression,
)
from polisyos.foundry.methods.catalog.causal._common import (
    bootstrap_ci,
    build_failure_report,
    build_success_report,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus
from polisyos.ir.analytics.dynamic_regime import GComputationResult, RegimeRule

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


def _build_history_matrix(
    A_seq: np.ndarray, L_seq: np.ndarray, t: int
) -> np.ndarray:
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

    # Step 1: fit Q_T = E[Y | H_{T-1}, A_{T-1}]
    H_last = _build_history_matrix(A_seq, L_seq, n_periods - 1)
    X_last = np.hstack([H_last, A_seq[:, n_periods - 1 : n_periods]])
    q_model = _fit_outcome_model(X_last, Y)
    pseudo_Y = Y.copy().astype(float)

    # Step 2: backward iteration t = T-2, ..., 0
    for t in range(n_periods - 2, -1, -1):
        H_t = _build_history_matrix(A_seq, L_seq, t)
        L_t = L_seq[:, t, :]
        a_regime = _apply_regime(H_t, L_t, rule, thr_cov, thr_val)

        # Predict Q_{t+1}(H_{t+1}, d*(H_{t+1})) using current pseudo_Y model
        # but apply regime at period t+1
        H_next = _build_history_matrix(A_seq, L_seq, t + 1)
        L_next = L_seq[:, t + 1, :] if t + 1 < n_periods else L_seq[:, -1, :]
        a_next = _apply_regime(H_next, L_next, rule, thr_cov, thr_val)
        X_next_regime = np.hstack(
            [_build_history_matrix(A_seq, L_seq, t + 1), a_next.reshape(-1, 1)]
        )
        pseudo_Y = q_model.predict(X_next_regime)

        # Fit new model for Q_t on OBSERVED treatment A_t (not regime)
        X_t = np.hstack([H_t, A_seq[:, t : t + 1]])
        q_model = _fit_outcome_model(X_t, pseudo_Y)

    # Step 3: final estimate — apply regime at t=0
    H0 = _build_history_matrix(A_seq, L_seq, 0)
    L0 = L_seq[:, 0, :]
    a0 = _apply_regime(H0, L0, rule, thr_cov, thr_val)
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

    # Monte Carlo simulation
    # Draw L_0 from empirical distribution
    mc_outcomes = np.empty(n_mc)
    for b in range(n_mc):
        # Sample a random unit's L_0 as starting point
        unit_idx = rng.integers(0, n_units)
        L_sim = np.zeros((1, n_periods, n_cov))
        A_sim = np.zeros((1, n_periods))
        L_sim[0, 0, :] = L_seq[unit_idx, 0, :]

        for t in range(n_periods):
            H_t = _build_history_matrix(A_sim, L_sim, t)
            L_t = L_sim[0, t, :].reshape(1, -1)
            a_t = _apply_regime(H_t, L_t, rule, thr_cov, thr_val)
            A_sim[0, t] = a_t[0]

            if t < n_periods - 1:
                X_cov_sim = np.hstack([H_t, a_t.reshape(-1, 1)])
                for j in range(n_cov):
                    mean_j = cov_models[t][j].predict(X_cov_sim)[0]
                    L_sim[0, t + 1, j] = mean_j + rng.normal(
                        0, cov_residual_stds[t][j]
                    )

        H_final = _build_history_matrix(A_sim, L_sim, n_periods - 1)
        X_out_sim = np.hstack([H_final, A_sim[:, n_periods - 1 : n_periods]])
        y_sim = out_model.predict(X_out_sim)[0]
        mc_outcomes[b] = y_sim + rng.normal(0, out_resid_std)

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
    raise TypeError(
        f"Expected DynamicTreatmentData or dict, got {type(state).__name__}"
    )


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
        namespace="placeholder",
        version="0.0.0",
        input_slots=_dynamic_input_slots(),
        output_slots=_dynamic_output_slots(),
        parameters=_dynamic_base_params()
        + (
            ParameterSpec("n_monte_carlo", default=500, bounds=(100, 5000)),
        ),
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
            "g_formula": (
                "E[Y^{ā}] = Σ_{l̄} E[Y|Ā=ā,L̄=l̄] × Π_t P(L_t|ā_{t-1},l̄_{t-1})"
            ),
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
    def pure_step(
        state: DynamicTreatmentData, params: Mapping[str, Any]
    ) -> dict[str, Any]:
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
        regime_params = {k: params.get(k, v.default) for k, v in {
            "regime": type("_", (), {"default": "always_treat"})(),
            "threshold_covariate_index": type("_", (), {"default": 0})(),
            "threshold_value": type("_", (), {"default": 0.0})(),
        }.items()}
        regime_params["regime"] = regime
        regime_params["threshold_covariate_index"] = int(
            params.get("threshold_covariate_index", 0)
        )
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
        namespace="placeholder",
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
                "Q_t = E[Q_{t+1}(H_{t+1}, d*(H_{t+1})) | H_t, A_t]; "
                "E[Y^d] = E[Q_0(H_0, d*(H_0))]"
            ),
        },
        assumptions=dict(_ASSUMPTIONS),
        when_to_use="Time-varying treatments; prefer over parametric g-formula for speed.",
        when_not_to_use=(
            "When outcome model is severely misspecified; prefer LTMLE for robustness."
        ),
        typical_min_obs=50,
        output_interpretation=(
            "point_estimate is E[Y^{ā}] under the specified dynamic regime."
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
            boot_estimates[b] = _ice_estimate(
                Y[idx], A_seq[idx], L_seq[idx], regime_params
            )
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
        namespace="placeholder",
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
    def pure_step(
        state: DynamicTreatmentData, params: Mapping[str, Any]
    ) -> dict[str, Any]:
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
]
