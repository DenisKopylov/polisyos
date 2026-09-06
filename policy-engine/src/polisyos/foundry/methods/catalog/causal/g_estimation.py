"""Structural Nested Mean Model (SNMM) via G-estimation.

Implements g-estimation for the blip-to-zero function γ(a_t, H_t; ψ):

    E[Y^{h̄_{t-1}, a_t, 0̄_{t+1:T}} − Y^{h̄_{t-1}, 0, 0̄_{t+1:T}} | H_t] = γ(a_t, H_t; ψ)

G-estimation solves the estimating equations:
    E[U_t(ψ) · f(H_t)] = 0
where U_t(ψ) = A_t − E[A_t|H_t]  (propensity residual)

Algorithm (backward induction):
    For t = T-1, T-2, ..., 0:
        1. Fit propensity π_t = E[A_t|H_t] via logistic regression
        2. Compute residuals U_t = A_t − π̂_t
        3. Solve ψ_t via OLS on blip-down pseudo-outcome Y_t*
        4. Blip-down: Y* −= γ(A_t, H_t; ψ̂_t)
    Return ψ̂ = concatenate of all stage estimates

References:
    Robins, J.M. (1994). Correcting for non-compliance in randomized trials
        using structural nested mean models. Communications in Statistics, 23, 2379-2412.
    Hernán, M.A. & Robins, J.M. (2020). Causal Inference: What If. Chapman & Hall.
    Vansteelandt, S. & Joffe, M. (2014). Structural nested models and G-estimation.
        Statistical Science, 29(2), 232-255.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability import DeterminismTier
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
    _build_history_matrix,
    _dynamic_input_slots,
    _extract_dynamic_data,
    _fit_propensity_model,
    _predict_proba_safe,
)
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus
from polisyos.ir.analytics.dynamic_regime import (
    DynamicTreatmentRegime,
    RegimeRule,
    SNMMResult,
)

_ASSUMPTIONS = {
    "sequential_ignorability": (
        "A_t ⊥ Y^{ā} | H_t for all t (no unmeasured time-varying confounders)"
    ),
    "blip_model_correct": ("The specified blip function γ(a_t, H_t; ψ) is correctly specified"),
    "consistency": "Y_i = Y_i^{ā} when Ā_i = ā",
    "positivity": "0 < P(A_t = 1 | H_t) < 1 for all H_t in support",
}


def _build_blip_features(
    A_t: np.ndarray,
    H_t: np.ndarray,
    L_t: np.ndarray,
    blip_model: str,
) -> np.ndarray:
    """Construct design matrix for blip function.

    For linear:      X = [A_t]                      → ψ: (1,)
    For interaction: X = [A_t, A_t * L_t[..., 0]]   → ψ: (2,)
    For quadratic:   X = [A_t, A_t * L_t[..., 0],
                          A_t * L_t[..., 0]^2]       → ψ: (3,)
    """
    a = A_t.reshape(-1, 1)
    if blip_model == "linear":
        return a
    l0 = L_t[:, 0:1]  # first covariate only for interaction
    if blip_model == "interaction":
        return np.hstack([a, a * l0])
    if blip_model == "quadratic":
        return np.hstack([a, a * l0, a * l0**2])
    return a  # fallback


def _blip_value(
    A_t: np.ndarray,
    H_t: np.ndarray,
    L_t: np.ndarray,
    psi: np.ndarray,
    blip_model: str,
) -> np.ndarray:
    """Compute γ(A_t, H_t; ψ) for each unit. Returns (n_units,)."""
    X_blip = _build_blip_features(A_t, H_t, L_t, blip_model)
    return X_blip @ psi


def _g_estimate_stage(
    pseudo_Y: np.ndarray,
    A_t: np.ndarray,
    H_t: np.ndarray,
    L_t: np.ndarray,
    blip_model: str,
) -> np.ndarray:
    """Estimate blip parameters ψ_t for one stage using g-estimation.

    Solves the estimating equation:
        E[U_t · X_blip_t] = 0
    where U_t = A_t − π̂_t (propensity residual)

    This is equivalent to OLS of pseudo_Y on X_blip with propensity residual instruments
    (Robins 1994, simplified for linear blip).
    """
    pm = _fit_propensity_model(H_t, A_t)
    pi_hat = _predict_proba_safe(pm, H_t)
    U_t = A_t - pi_hat  # propensity residuals (n_units,)

    X_blip = _build_blip_features(A_t, H_t, L_t, blip_model)  # (n_units, K)
    # IV-style: instrument is U_t * X_blip columns (rank-1 trick for linear blip)
    # Simple OLS estimate: ψ = (X_blip.T @ diag(U_t) @ X_blip)^{-1} @ (X_blip.T @ U_t @ Y)
    # For linear blip (K=1): ψ = (U_t · A_t)^{-1} · (U_t · pseudo_Y)
    K = X_blip.shape[1]
    # Correct g-estimation instruments: Z_k = U_t * f_k(H_t)
    # For linear blip (K=1):       f(H_t) = 1    → Z = [U_t]
    # For interaction blip (K=2):  f(H_t) = [1, L_t[:,0]] → Z = [U_t, U_t*L_t[:,0]]
    # For quadratic blip (K=3):    f(H_t) = [1, L_t[:,0], L_t[:,0]^2]
    if blip_model == "linear":
        Z = U_t.reshape(-1, 1)
    elif blip_model == "interaction":
        l0 = L_t[:, 0]
        Z = np.column_stack([U_t, U_t * l0])[:, :K]
    elif blip_model == "quadratic":
        l0 = L_t[:, 0]
        Z = np.column_stack([U_t, U_t * l0, U_t * l0**2])[:, :K]
    else:
        Z = U_t.reshape(-1, 1)

    # 2SLS: ψ = (Z.T @ X_blip)^{-1} @ (Z.T @ pseudo_Y)
    ZtX = Z.T @ X_blip  # (K, K)
    ZtY = Z.T @ pseudo_Y  # (K,)
    try:
        psi = np.linalg.solve(ZtX + np.eye(K) * 1e-8, ZtY)
    except np.linalg.LinAlgError:
        psi = np.zeros(K)
    return psi


def _run_snmm(
    Y: np.ndarray,
    A_seq: np.ndarray,
    L_seq: np.ndarray,
    blip_model: str,
) -> tuple[list[np.ndarray], float]:
    """Run SNMM backward induction; return per-stage ψ estimates and final psi_0."""
    n_units, n_periods, _ = L_seq.shape
    pseudo_Y = Y.copy().astype(float)
    stage_psis: list[np.ndarray] = []

    for t in range(n_periods - 1, -1, -1):
        H_t = _build_history_matrix(A_seq, L_seq, t)
        L_t = L_seq[:, t, :]
        A_t = A_seq[:, t]
        psi_t = _g_estimate_stage(pseudo_Y, A_t, H_t, L_t, blip_model)
        # Blip down
        pseudo_Y -= _blip_value(A_t, H_t, L_t, psi_t, blip_model)
        stage_psis.insert(0, psi_t)  # prepend so index 0 = stage 0

    return stage_psis, float(np.mean(pseudo_Y))


def _extract_optimal_regime(
    stage_psis: list[np.ndarray],
    blip_model: str,
    L_seq: np.ndarray,
    A_seq: np.ndarray,
) -> DynamicTreatmentRegime:
    """Derive optimal regime from ψ estimates.

    For linear blip γ(a, H; ψ) = ψ_0 · a: treat iff ψ_0 > 0 → always or never treat.
    For interaction blip γ = ψ_0 · a + ψ_1 · a · L: treat iff ψ_0 + ψ_1·L > 0.
    Approximated as a threshold rule on the first covariate.
    """
    n_periods = len(stage_psis)
    time_points = tuple(range(n_periods))
    treatment_vars = tuple(f"A_{t}" for t in range(n_periods))
    cov_vars = tuple(f"L_{t}" for t in range(n_periods))

    psi0 = stage_psis[0]  # first stage ψ (most relevant for regime)
    if blip_model == "linear":
        rule = RegimeRule.ALWAYS_TREAT if float(psi0[0]) > 0 else RegimeRule.NEVER_TREAT
        return DynamicTreatmentRegime(
            time_points=time_points,
            treatment_variables=treatment_vars,
            time_varying_covariates=cov_vars,
            outcome="Y",
            rule=rule,
            regime_coefficients=tuple(float(p) for p in psi0),
        )
    # Interaction / quadratic: derive threshold rule
    # Treat if ψ_0 + ψ_1 * L > 0 → L > -ψ_0/ψ_1
    if len(psi0) >= 2 and abs(float(psi0[1])) > 1e-10:
        threshold = -float(psi0[0]) / float(psi0[1])
        return DynamicTreatmentRegime(
            time_points=time_points,
            treatment_variables=treatment_vars,
            time_varying_covariates=cov_vars,
            outcome="Y",
            rule=RegimeRule.THRESHOLD,
            threshold_covariate_index=0,
            threshold_value=threshold,
            regime_coefficients=tuple(float(p) for p in psi0),
        )
    rule = RegimeRule.ALWAYS_TREAT if float(psi0[0]) > 0 else RegimeRule.NEVER_TREAT
    return DynamicTreatmentRegime(
        time_points=time_points,
        treatment_variables=treatment_vars,
        time_varying_covariates=cov_vars,
        outcome="Y",
        rule=rule,
        regime_coefficients=tuple(float(p) for p in psi0),
    )


# ---------------------------------------------------------------------------
# StructuralNestedMeanModel
# ---------------------------------------------------------------------------


@foundry_method(namespace="causal.dynamic.snmm", version="1.0.0")
class StructuralNestedMeanModel:
    """Structural Nested Mean Model (SNMM) estimated via G-estimation (Robins 1994).

    Models the blip function γ(a_t, H_t; ψ) — the causal effect of treatment
    a_t at time t on the final outcome, removing all future treatments.

    For linear blip: γ(a_t, H_t; ψ) = ψ_0 · a_t

    G-estimation solves E[U_t(ψ) · f(H_t)] = 0, where U_t = A_t − E[A_t|H_t].

    The optimal dynamic regime d*(H_t) = argmax_a γ(a, H_t; ψ̂) is extracted
    automatically from the fitted blip parameters.

    References:
        Robins (1994). Correcting for non-compliance in randomized trials.
        Vansteelandt & Joffe (2014). Structural nested models and G-estimation.
            Statistical Science, 29(2), 232-255.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="snmm_g_estimation",
        namespace="",
        version="0.0.0",
        input_slots=_dynamic_input_slots(),
        output_slots=frozenset(
            {
                SlotSpec("result", SlotType.SCALAR, Unit("report", "json")),
                SlotSpec("snmm_result", SlotType.SCALAR, Unit("snmm_result", "json")),
                SlotSpec("warnings", SlotType.SCALAR, Unit("warning", "list")),
            }
        ),
        parameters=(
            ParameterSpec("blip_model", default="linear"),
            ParameterSpec("n_bootstrap", default=200, bounds=(50, 1000)),
            ParameterSpec("confidence_level", default=0.95, bounds=(0.8, 0.99)),
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
            "Structural Nested Mean Model via G-estimation. "
            "Estimates the blip function γ(a_t, H_t; ψ) — the causal effect of "
            "treatment at each time point — and extracts the optimal dynamic regime."
        ),
        tags=frozenset(
            {
                "causal",
                "dynamic",
                "longitudinal",
                "snmm",
                "g_estimation",
                "structural_nested",
                "time_varying",
            }
        ),
        citations=(
            "Robins, J.M. (1994). Correcting for non-compliance in randomized trials "
            "using structural nested mean models. Communications in Statistics, 23.",
            "Vansteelandt, S. & Joffe, M. (2014). Structural nested models and "
            "G-estimation. Statistical Science, 29(2), 232-255.",
        ),
        equations={
            "blip_linear": "γ(a_t, H_t; ψ) = ψ_0 · a_t",
            "blip_interaction": "γ(a_t, H_t; ψ) = ψ_0 · a_t + ψ_1 · a_t · L_{t,1}",
            "estimating_eq": "E[U_t(ψ) · f(H_t)] = 0,  U_t = A_t − E[A_t|H_t]",
        },
        assumptions=dict(_ASSUMPTIONS),
        when_to_use=(
            "Dynamic treatment regimes with sequential confounders; "
            "useful when a parametric blip structure is plausible."
        ),
        when_not_to_use=(
            "When the blip function is highly non-linear; use Q-learning or OWL instead."
        ),
        typical_min_obs=80,
        output_interpretation=(
            "psi_estimates are the blip function coefficients ψ̂. "
            "ψ[0] > 0 suggests treatment is beneficial. "
            "optimal_regime contains the estimated optimal rule d*(H_t)."
        ),
    )

    @staticmethod
    def pure_step(state: DynamicTreatmentData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            data = _extract_dynamic_data(state)
        except Exception as exc:
            dummy = build_failure_report(
                method=CausalMethod.G_ESTIMATION,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="blip(a_t, H_t; ψ)",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions={},
            )
            return wrap_causal_output(dummy, extras={"snmm_result": None})

        Y = data.outcome.astype(float)
        A_seq = data.treatment_sequence.astype(float)
        L_seq = data.covariate_sequence.astype(float)
        n_units, n_periods = data.n_units, data.n_periods
        blip_model: str = str(params.get("blip_model", "linear"))
        n_boot = int(params.get("n_bootstrap", 200))
        conf_level = float(params.get("confidence_level", 0.95))

        if n_units < 20:
            dummy = build_failure_report(
                method=CausalMethod.G_ESTIMATION,
                status=EstimationStatus.INPUT_INVALID,
                reason="Need at least 20 units for SNMM",
                estimand="blip(a_t, H_t; ψ)",
                sample_size=n_units,
                n_treated=0,
                n_control=0,
                pre_periods=n_periods,
                post_periods=0,
                assumptions=dict(_ASSUMPTIONS),
            )
            return wrap_causal_output(dummy, extras={"snmm_result": None})

        stage_psis, _ = _run_snmm(Y, A_seq, L_seq, blip_model)

        # Flatten all stage ψ into one vector
        psi_flat = np.concatenate(stage_psis)
        K_total = len(psi_flat)

        # Bootstrap SEs
        rng = np.random.default_rng(42)
        boot_psis = np.empty((n_boot, K_total))
        for b in range(n_boot):
            idx = rng.integers(0, n_units, size=n_units)
            boot_stages, _ = _run_snmm(Y[idx], A_seq[idx], L_seq[idx], blip_model)
            boot_psis[b] = np.concatenate(boot_stages)

        psi_ses = np.std(boot_psis, axis=0, ddof=1)

        # Point estimate for CausalEffectReport = ψ_0[0] (main treatment effect at stage 0)
        main_effect = float(psi_flat[0])
        boot_main = boot_psis[:, 0]
        ci = bootstrap_ci(boot_main, conf_level)
        ci_lo = min(float(ci[0]), main_effect)
        ci_hi = max(float(ci[1]), main_effect)
        se_main = float(psi_ses[0])

        # Extract optimal regime
        optimal_regime = _extract_optimal_regime(stage_psis, blip_model, L_seq, A_seq)

        snmm_result = SNMMResult(
            psi_estimates=tuple(float(p) for p in psi_flat),
            psi_std_errors=tuple(float(s) for s in psi_ses),
            blip_model=blip_model,  # type: ignore[arg-type]
            n_units=n_units,
            n_periods=n_periods,
            optimal_regime=optimal_regime,
        )

        n_treated = int(np.sum(A_seq[:, 0]))
        report = build_success_report(
            method=CausalMethod.G_ESTIMATION,
            estimand="blip function ψ: γ(a_t, H_t; ψ)",
            point_estimate=main_effect,
            confidence_interval=(ci_lo, ci_hi),
            inference_method="bootstrap",
            sample_size=n_units,
            n_treated=n_treated,
            n_control=n_units - n_treated,
            pre_periods=n_periods,
            post_periods=0,
            assumptions=dict(_ASSUMPTIONS),
            standard_error=se_main,
            metadata={
                "blip_model": blip_model,
                "n_periods": n_periods,
                "psi_all": [float(p) for p in psi_flat],
            },
        )
        return wrap_causal_output(report, extras={"snmm_result": snmm_result})


__all__ = [
    "SNMMResult",
    "StructuralNestedMeanModel",
]
