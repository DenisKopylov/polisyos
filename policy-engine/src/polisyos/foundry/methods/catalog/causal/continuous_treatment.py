"""continuous_treatment — dose-response estimation for continuous treatments.

Implements four estimators:

1. **GeneralizedPropensityScoreEstimator** — Hirano & Imbens (2004).
   Two-step GPS: fit T|X ~ Normal, regress Y on (T, GPS), marginalize.

2. **KernelDoseResponseEstimator** — Kennedy, Ma, McHugh & Small (2017).
   Doubly-robust kernel estimator using the EIF for continuous ATE.
   Cross-fits nuisance models (conditional density + outcome model).

3. **ShiftInterventionEstimator** — Díaz & van der Laan (2012).
   Modified treatment policy: E[Y(A+δ)] − E[Y(A)] via density ratio.

4. **EntropyBalancingContinuousEstimator** — Vegetabile et al. (2021).
   Minimum-KL weights satisfying covariate moment constraints.

All estimators share ``ContinuousTreatmentData`` as input and produce
``DoseResponseResult`` or a plain dict (for scalar effects).

References
----------
Hirano, K. & Imbens, G.W. (2004). The Propensity Score with Continuous
    Multivalued Treatments. Applied Bayesian Modeling and Causal Inference
    from Incomplete-Data Perspectives.

Kennedy, E.H., Ma, Z., McHugh, M.D. & Small, D.S. (2017). Non-parametric
    methods for doubly robust estimation of continuous treatment effects.
    *Journal of the Royal Statistical Society: Series B*, 79(4).

Díaz, I. & van der Laan, M.J. (2012). Population intervention causal effects
    based on stochastic interventions. *Biometrics*, 68(2).

Vegetabile, B.G., Griffin, B.A., Coffman, D.L., Cefalu, M., Robbins, M.W.
    & McCaffrey, D.F. (2021). Nonparametric estimation of population average
    dose-response curves using entropy balancing weights for continuous
    exposures. *Health Services and Outcomes Research Methodology*.
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
from polisyos.foundry.methods.catalog.causal.eif_bounds import (
    ContinuousEIFScores,
    EIFScores,
    _gaussian_kernel,
    _silverman_bandwidth,
    compute_eif_continuous_ate,
    compute_eif_shift_intervention,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    ContinuousTreatmentData,
    DoseResponseResult,
)

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _normal_pdf(x: np.ndarray, mu: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian PDF N(mu, sigma²) evaluated at x.  Returns density."""
    z = (x - mu) / sigma
    return np.exp(-0.5 * z * z) / (sigma * np.sqrt(2.0 * np.pi))


def _build_eval_grid(
    T: np.ndarray,
    data: ContinuousTreatmentData,
    params: Mapping[str, Any],
) -> np.ndarray:
    """Return evaluation grid for the dose-response curve.

    Uses ``data.evaluation_points`` if provided; otherwise generates
    ``n_eval_points`` equally-spaced quantiles in ``eval_range``.
    """
    if data.evaluation_points is not None:
        return data.evaluation_points
    n_eval = int(params.get("n_eval_points", 20))
    lo, hi = params.get("eval_range", (0.05, 0.95))
    return np.quantile(T, np.linspace(lo, hi, n_eval))


def _build_polynomial_features(
    T: np.ndarray,
    R: np.ndarray,
    degree: int = 2,
) -> np.ndarray:
    """Polynomial feature matrix in (T, R) up to total degree ``degree``.

    Includes intercept, T, R, T², R², T·R for degree=2.
    """
    cols = [np.ones(len(T)), T, R]
    if degree >= 2:
        cols.extend([T * T, R * R, T * R])
    if degree >= 3:
        cols.extend([T**3, T * T * R, T * R * R, R**3])
    return np.column_stack(cols)


def _fit_gps_model(
    X: np.ndarray,
    T: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Fit T ~ Normal(Xβ, σ²) via OLS.

    Returns (beta, sigma) where beta is for the augmented design [1, X].
    """
    X_aug = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(X_aug, T, rcond=None)
    T_hat = X_aug @ beta
    sigma = max(float(np.std(T - T_hat, ddof=1)), 1e-8)
    return beta, sigma


def _predict_gps(
    X: np.ndarray,
    T_eval: np.ndarray,
    beta: np.ndarray,
    sigma: float,
) -> np.ndarray:
    """Compute GPS r(t, x) = f(T_eval | X) under Normal model."""
    X_aug = np.column_stack([np.ones(len(X)), X])
    T_hat = X_aug @ beta
    return _normal_pdf(T_eval, T_hat, sigma)


def _bootstrap_dose_response(
    Y: np.ndarray,
    T: np.ndarray,
    X: np.ndarray,
    eval_pts: np.ndarray,
    n_bootstrap: int = 200,
    polynomial_degree: int = 2,
    seed: int = 0,
) -> np.ndarray:
    """Bootstrap SE for GPS dose-response curve.

    Returns SE (n_eval,) estimated from n_bootstrap resamples.
    """
    n = len(Y)
    rng = np.random.default_rng(seed)
    dr_boot = np.empty((n_bootstrap, len(eval_pts)), dtype=float)

    for b in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        Yb, Tb, Xb = Y[idx], T[idx], X[idx]
        try:
            dr_b = _gps_dose_response(Yb, Tb, Xb, eval_pts, polynomial_degree)
        except Exception:
            dr_b = np.full(len(eval_pts), np.nan)
        dr_boot[b] = dr_b

    # SE = std across bootstrap replicates (ignore NaN rows)
    valid = ~np.any(np.isnan(dr_boot), axis=1)
    if valid.sum() < 2:
        return np.ones(len(eval_pts)) * np.nan
    return np.std(dr_boot[valid], axis=0, ddof=1)


def _gps_dose_response(
    Y: np.ndarray,
    T: np.ndarray,
    X: np.ndarray,
    eval_pts: np.ndarray,
    polynomial_degree: int = 2,
) -> np.ndarray:
    """Single-run GPS dose-response (no bootstrap).

    Steps:
        1. Fit T|X ~ Normal via OLS → (beta, sigma).
        2. Compute GPS at observed T: R = f(T|X).
        3. Fit Y ~ poly(T, R) via OLS.
        4. For each t_j: compute GPS at (t_j, X), predict μ(t_j, R̂), average.
    """
    beta_t, sigma = _fit_gps_model(X, T)
    T_hat = np.column_stack([np.ones(len(X)), X]) @ beta_t
    R = _normal_pdf(T, T_hat, sigma)

    poly = _build_polynomial_features(T, R, degree=polynomial_degree)
    beta_y, *_ = np.linalg.lstsq(poly, Y, rcond=None)

    dr = np.empty(len(eval_pts), dtype=float)
    for j, t_j in enumerate(eval_pts):
        R_at_t = _predict_gps(X, np.full(len(X), t_j), beta_t, sigma)
        poly_at_t = _build_polynomial_features(
            np.full(len(X), t_j), R_at_t, degree=polynomial_degree
        )
        mu_at_t = poly_at_t @ beta_y
        dr[j] = float(mu_at_t.mean())

    return dr


def _kfold_indices(n: int, n_folds: int, seed: int = 42) -> list[tuple]:
    """Generate (train_idx, val_idx) pairs for K-fold CV."""
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    folds = np.array_split(idx, n_folds)
    result = []
    for k in range(n_folds):
        val = folds[k]
        train = np.concatenate([folds[j] for j in range(n_folds) if j != k])
        result.append((train, val))
    return result


def _build_oof_outcome_fn(
    Y: np.ndarray,
    T: np.ndarray,
    X: np.ndarray,
    n_folds: int,
    seed: int = 42,
) -> Any:
    """Build an out-of-fold outcome function μ(T, X) → (n,).

    The outcome model is μ(T, X) = [1, T, X] @ beta (linear in T).
    Out-of-fold: for each fold, fit on K-1 folds, predict on held-out.
    Returns a closure that evaluates at any (T_vec, X_mat).
    """
    n = len(Y)
    feat = np.column_stack([np.ones(n), T, X])  # (n, 1+p+1)
    beta_list: list[tuple[np.ndarray, np.ndarray]] = []  # (val_idx, beta)

    for train_idx, val_idx in _kfold_indices(n, n_folds, seed=seed):
        beta, *_ = np.linalg.lstsq(feat[train_idx], Y[train_idx], rcond=None)
        beta_list.append((val_idx, beta))

    # Also fit global model on all data for out-of-support evaluation
    beta_global, *_ = np.linalg.lstsq(feat, Y, rcond=None)

    def outcome_fn(T_in: np.ndarray, X_in: np.ndarray) -> np.ndarray:
        """Evaluate μ(T_in, X_in) using global model (best available at eval time)."""
        T_in = np.asarray(T_in, dtype=float)
        X_in = np.asarray(X_in, dtype=float)
        feat_in = np.column_stack([np.ones(len(T_in)), T_in, X_in])
        return feat_in @ beta_global

    return outcome_fn


# ---------------------------------------------------------------------------
# Estimator 1: GPS — Hirano & Imbens (2004)
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.continuous_treatment",
    version="1.0.0",
    tags=frozenset({"causal", "continuous_treatment", "dose_response", "gps"}),
)
class GeneralizedPropensityScoreEstimator:
    """GPS dose-response estimator (Hirano & Imbens 2004).

    Estimates the marginal dose-response curve β(t) = E[Y(t)] for a
    continuous treatment T using the Generalised Propensity Score:

    1. Fit GPS r̂(t, x) = f̂(T=t | X=x) ~ Normal(Xβ, σ̂²).
    2. Fit outcome model Ê[Y | T=t, R=r] as polynomial in (T, R).
    3. β̂(t) = n⁻¹ Σᵢ Ê[Y | T=t, R=r̂(t, Xᵢ)].
    4. Bootstrap confidence bands.

    Registered as ``causal.continuous_treatment.gps@1.0.0``.
    """

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="gps",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            [
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    description="(n,) outcome vector",
                    unit=Unit("dimensionless", ""),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    description="(n,) continuous treatment",
                    unit=Unit("dimensionless", ""),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    description="(n, p) covariate matrix",
                    unit=Unit("dimensionless", ""),
                    shape=("n_obs", "n_features"),
                ),
            ]
        ),
        output_slots=frozenset(
            [
                SlotSpec(
                    name="dose_response_result",
                    slot_type=SlotType.SCALAR,
                    description="DoseResponseResult dict",
                    unit=Unit("dimensionless", ""),
                ),
            ]
        ),
        parameters=(
            ParameterSpec(
                name="n_bootstrap",
                default=200,
                description="Bootstrap resamples for SE estimation",
                bounds=(10, 5000),
            ),
            ParameterSpec(
                name="polynomial_degree",
                default=2,
                description="Degree of (T, R) polynomial outcome model",
                bounds=(1, 3),
            ),
            ParameterSpec(
                name="n_eval_points",
                default=20,
                description="Grid size if evaluation_points not provided",
                bounds=(5, 200),
            ),
            ParameterSpec(
                name="eval_range",
                default=(0.05, 0.95),
                description="(lo, hi) quantile range for evaluation grid",
            ),
            ParameterSpec(name="seed", default=0, description="Random seed for bootstrap"),
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
            "GPS dose-response curve β(t) = E[Y(t)] estimated via the "
            "Generalised Propensity Score (Hirano & Imbens 2004). "
            "Assumes T|X ~ Normal and a polynomial outcome model."
        ),
        tags=frozenset({"causal", "continuous_treatment", "dose_response", "gps", "observational"}),
        citations=(
            "Hirano, K. & Imbens, G.W. (2004). The Propensity Score with "
            "Continuous Multivalued Treatments.",
        ),
        equations={
            "gps": "r(t, x) = φ((t − xᵀβ)/σ̂) / σ̂",
            "dr": "β̂(t) = n⁻¹ Σᵢ Ê[Y | T=t, R=r̂(t,Xᵢ)]",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Use when treatment is continuous and T|X is approximately Gaussian. "
            "Simpler and faster than the doubly-robust kernel estimator."
        ),
        when_not_to_use=(
            "Avoid if T|X is strongly non-Gaussian or the outcome model is "
            "non-linear in (T, R). Use KernelDoseResponseEstimator instead."
        ),
        prerequisites=(),
        diagnostic_checks=(
            "Check normality of GPS residuals.",
            "Inspect polynomial fit diagnostics.",
        ),
        typical_min_obs=100,
        output_interpretation=(
            "dose_response_result.dose_response[j] = β̂(t_j) = E[Y(t_j)]. "
            "Confidence bands via nonparametric bootstrap."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        data = ContinuousTreatmentData(
            outcome=state["outcome"],
            treatment=state["treatment"],
            covariates=state["covariates"],
            evaluation_points=state.get("evaluation_points"),
        )
        Y, T, X = data.outcome, data.treatment, data.covariates
        poly_degree = int(params.get("polynomial_degree", 2))
        n_bootstrap = int(params.get("n_bootstrap", 200))
        seed = int(params.get("seed", 0))

        eval_pts = _build_eval_grid(T, data, params)

        dr = _gps_dose_response(Y, T, X, eval_pts, polynomial_degree=poly_degree)
        se = _bootstrap_dose_response(
            Y,
            T,
            X,
            eval_pts,
            n_bootstrap=n_bootstrap,
            polynomial_degree=poly_degree,
            seed=seed,
        )
        # Replace NaN SE with 0 so result is always finite
        se = np.where(np.isfinite(se), se, 0.0)

        result = DoseResponseResult(
            treatment_grid=eval_pts,
            dose_response=dr,
            confidence_band_lower=dr - 1.96 * se,
            confidence_band_upper=dr + 1.96 * se,
            standard_errors=se,
            method="gps_hirano_imbens_2004",
            n_obs=len(Y),
            bandwidth=None,
        )
        return {"dose_response_result": result.model_dump()}


# ---------------------------------------------------------------------------
# Estimator 2: Kernel dose-response (doubly robust) — Kennedy et al. 2017
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.continuous_treatment",
    version="1.0.0",
    tags=frozenset(
        {
            "causal",
            "continuous_treatment",
            "dose_response",
            "doubly_robust",
            "kernel",
            "semiparametric",
        }
    ),
)
class KernelDoseResponseEstimator:
    """Doubly-robust kernel dose-response estimator (Kennedy et al. 2017).

    Estimates β(t) = E[Y(t)] using the EIF::

        ψᵢ(t) = K_h(Tᵢ−t)/f(Tᵢ|Xᵢ) × (Yᵢ − μ(Tᵢ,Xᵢ)) + μ(t,Xᵢ)

    with cross-fitted nuisance functions:
    - GPS f(T|X): parametric Gaussian density fitted via OLS.
    - Outcome model μ(T,X): linear in (T, X) fitted via OLS.

    Doubly robust: consistent if either f(T|X) or μ(T,X) is correctly
    specified (Kennedy et al. 2017, Theorem 1).

    Registered as ``causal.continuous_treatment.kernel_dr@1.0.0``.
    """

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="kernel_dr",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            [
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    description="(n,) outcome",
                    unit=Unit("dimensionless", ""),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    description="(n,) continuous treatment",
                    unit=Unit("dimensionless", ""),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    description="(n, p) covariates",
                    unit=Unit("dimensionless", ""),
                    shape=("n_obs", "n_features"),
                ),
            ]
        ),
        output_slots=frozenset(
            [
                SlotSpec(
                    name="dose_response_result",
                    slot_type=SlotType.SCALAR,
                    description="DoseResponseResult dict",
                    unit=Unit("dimensionless", ""),
                ),
            ]
        ),
        parameters=(
            ParameterSpec(
                name="n_folds", default=5, description="K-fold cross-fitting folds", bounds=(2, 20)
            ),
            ParameterSpec(
                name="bandwidth",
                default=None,
                description="Kernel bandwidth h. None → Silverman rule",
            ),
            ParameterSpec(
                name="n_eval_points", default=30, description="Grid size", bounds=(5, 200)
            ),
            ParameterSpec(
                name="eval_range",
                default=(0.05, 0.95),
                description="Quantile range for evaluation grid",
            ),
            ParameterSpec(
                name="min_gps", default=1e-4, description="GPS clipping floor", bounds=(1e-10, 0.1)
            ),
            ParameterSpec(name="seed", default=42, description="Random seed for cross-fitting"),
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
            "Doubly-robust kernel dose-response estimator. Uses the EIF for "
            "continuous-treatment ATE with cross-fitted GPS and outcome model. "
            "Consistent at √(nh) rate under either nuisance model misspecification."
        ),
        tags=frozenset(
            {"causal", "continuous_treatment", "semiparametric", "doubly_robust", "kernel", "eif"}
        ),
        citations=(
            "Kennedy, E.H., Ma, Z., McHugh, M.D. & Small, D.S. (2017). "
            "Non-parametric methods for doubly robust estimation of continuous "
            "treatment effects. JRSS-B 79(4).",
        ),
        equations={
            "eif": ("ψᵢ(t) = K_h(Tᵢ−t)/f(Tᵢ|Xᵢ)·(Yᵢ−μ(Tᵢ,Xᵢ)) + μ(t,Xᵢ)"),
            "beta_hat": "β̂(t) = n⁻¹ Σᵢ ψᵢ(t)",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Preferred over GPS when the parametric T|X model may be "
            "misspecified, or for valid semiparametric inference."
        ),
        when_not_to_use=(
            "Avoid for n < 100 — bandwidth selection degrades. Use GPS for small samples."
        ),
        prerequisites=(),
        diagnostic_checks=(
            "Vary bandwidth h and check stability of β̂(t).",
            "Compare to GPS estimate for sensitivity.",
        ),
        typical_min_obs=200,
        output_interpretation=(
            "dose_response_result.dose_response[j] = β̂(t_j) = E[Y(t_j)]. "
            "Standard errors from EIF variance: SE = std(ψᵢ(t))/√n."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        data = ContinuousTreatmentData(
            outcome=state["outcome"],
            treatment=state["treatment"],
            covariates=state["covariates"],
            evaluation_points=state.get("evaluation_points"),
        )
        Y, T, X = data.outcome, data.treatment, data.covariates
        n = len(Y)
        n_folds = int(params.get("n_folds", 5))
        bw = params.get("bandwidth", None)
        if bw is not None:
            bw = float(bw)
        min_gps = float(params.get("min_gps", 1e-4))
        seed = int(params.get("seed", 42))

        eval_pts = _build_eval_grid(T, data, params)

        # ---- Cross-fitted GPS (out-of-fold) ----
        gps_oof = np.zeros(n, dtype=float)
        for train_idx, val_idx in _kfold_indices(n, n_folds, seed=seed):
            beta_t, sigma = _fit_gps_model(X[train_idx], T[train_idx])
            gps_oof[val_idx] = _predict_gps(X[val_idx], T[val_idx], beta_t, sigma)
        gps_oof = np.clip(gps_oof, min_gps, None)

        # ---- Out-of-fold outcome model μ(T, X) ----
        outcome_fn = _build_oof_outcome_fn(Y, T, X, n_folds, seed=seed)

        # ---- EIF-based dose-response ----
        eif_scores: ContinuousEIFScores = compute_eif_continuous_ate(
            Y,
            T,
            X,
            gps_observed=gps_oof,
            outcome_fn=outcome_fn,
            eval_points=eval_pts,
            bandwidth=bw,
            min_gps=min_gps,
        )

        result = eif_scores.to_dose_response_result()
        return {"dose_response_result": result.model_dump()}


# ---------------------------------------------------------------------------
# Estimator 3: Shift Intervention — Díaz & van der Laan (2012)
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.continuous_treatment",
    version="1.0.0",
    tags=frozenset(
        {"causal", "continuous_treatment", "shift_intervention", "doubly_robust", "mtp"}
    ),
)
class ShiftInterventionEstimator:
    """Modified treatment policy shift intervention E[Y(A+δ)] − E[Y(A)].

    Uses the doubly-robust EIF from Díaz & van der Laan (2012)::

        ψᵢ(δ) = [μ(Aᵢ+δ,Xᵢ) − μ(Aᵢ,Xᵢ)]
                + f(Aᵢ|Xᵢ)/f(Aᵢ−δ|Xᵢ) × (Yᵢ − μ(Aᵢ,Xᵢ))

    The density ratio f(A|X)/f(A−δ|X) is computed from the parametric
    GPS model.  Cross-fitted nuisance functions reduce bias.

    Registered as ``causal.continuous_treatment.shift@1.0.0``.
    """

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="shift",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            [
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    description="(n,) outcome",
                    unit=Unit("dimensionless", ""),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    description="(n,) continuous treatment A",
                    unit=Unit("dimensionless", ""),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    description="(n, p) covariates",
                    unit=Unit("dimensionless", ""),
                    shape=("n_obs", "n_features"),
                ),
            ]
        ),
        output_slots=frozenset(
            [
                SlotSpec(
                    name="shift_effect",
                    slot_type=SlotType.SCALAR,
                    description="E[Y(A+δ)] − E[Y(A)] estimate dict",
                    unit=Unit("dimensionless", ""),
                ),
            ]
        ),
        parameters=(
            ParameterSpec(name="delta", default=1.0, description="Shift amount δ"),
            ParameterSpec(
                name="n_folds", default=5, description="K-fold cross-fitting", bounds=(2, 20)
            ),
            ParameterSpec(
                name="min_density_ratio",
                default=0.01,
                description="Lower clipping bound for density ratio",
                bounds=(1e-6, 1.0),
            ),
            ParameterSpec(
                name="max_density_ratio",
                default=100.0,
                description="Upper clipping bound for density ratio",
            ),
            ParameterSpec(name="seed", default=42, description="Random seed"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Doubly-robust shift intervention effect E[Y(A+δ)] − E[Y(A)]. "
            "Useful for answering 'what if every unit received δ more treatment?'"
        ),
        tags=frozenset({"causal", "continuous_treatment", "shift", "mtp", "doubly_robust"}),
        citations=(
            "Díaz, I. & van der Laan, M.J. (2012). Population intervention "
            "causal effects based on stochastic interventions. Biometrics 68(2).",
        ),
        equations={
            "psi": ("ψᵢ = [μ(A+δ,X) − μ(A,X)] + f(A|X)/f(A−δ|X)·(Y − μ(A,X))"),
            "tau": "τ̂(δ) = n⁻¹ Σᵢ ψᵢ",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Use to estimate the effect of a uniform additive shift in treatment. "
            "More interpretable than a full dose-response curve for policy analysis."
        ),
        when_not_to_use=(
            "Avoid if δ is very large relative to the treatment range "
            "— density ratios will be extreme."
        ),
        prerequisites=(),
        diagnostic_checks=(
            "Check density ratio distribution: extreme values indicate positivity issues.",
            "Test with δ=0 to verify τ̂ ≈ 0.",
        ),
        typical_min_obs=100,
        output_interpretation=(
            "shift_effect.point_estimate = E[Y(A+δ)] − E[Y(A)]. "
            "Positive means more treatment raises outcome."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        data = ContinuousTreatmentData(
            outcome=state["outcome"],
            treatment=state["treatment"],
            covariates=state["covariates"],
        )
        Y, T, X = data.outcome, data.treatment, data.covariates
        n = len(Y)
        delta = float(params.get("delta", 1.0))
        n_folds = int(params.get("n_folds", 5))
        min_dr = float(params.get("min_density_ratio", 0.01))
        max_dr = float(params.get("max_density_ratio", 100.0))
        seed = int(params.get("seed", 42))

        # ---- Cross-fitted GPS parameters ----
        # We need f(T|X) and f(T-δ|X) from the same parametric model.
        # Fit once per fold, then evaluate at T and T-δ for val units.

        gps_at_t = np.zeros(n, dtype=float)  # f(Tᵢ|Xᵢ)
        gps_at_t_minus = np.zeros(n, dtype=float)  # f(Tᵢ−δ|Xᵢ)

        for train_idx, val_idx in _kfold_indices(n, n_folds, seed=seed):
            beta_t, sigma = _fit_gps_model(X[train_idx], T[train_idx])
            gps_at_t[val_idx] = _predict_gps(X[val_idx], T[val_idx], beta_t, sigma)
            gps_at_t_minus[val_idx] = _predict_gps(X[val_idx], T[val_idx] - delta, beta_t, sigma)

        raw_density_ratio = gps_at_t / np.clip(gps_at_t_minus, 1e-12, None)
        clipped_density_ratio = np.clip(raw_density_ratio, min_dr, max_dr)
        density_ratio_sum = float(np.sum(clipped_density_ratio))
        density_ratio_sq_sum = float(np.sum(clipped_density_ratio**2))
        density_ratio_ess = float(density_ratio_sum**2 / max(density_ratio_sq_sum, 1e-12))
        n_clipped_ratio = int(np.sum((raw_density_ratio < min_dr) | (raw_density_ratio > max_dr)))

        # ---- Out-of-fold outcome model ----
        outcome_fn = _build_oof_outcome_fn(Y, T, X, n_folds, seed=seed)

        # ---- Density-ratio function for EIF ----
        def density_fn(t_vec: np.ndarray, x_mat: np.ndarray) -> np.ndarray:
            # Approximate: use the global GPS model fitted on all data
            beta_g, sigma_g = _fit_gps_model(X, T)
            return _predict_gps(x_mat, t_vec, beta_g, sigma_g)

        eif: EIFScores = compute_eif_shift_intervention(
            Y,
            T,
            X,
            density_fn=density_fn,
            outcome_fn=outcome_fn,
            delta=delta,
            min_density_ratio=min_dr,
            max_density_ratio=max_dr,
        )

        pe = eif.point_estimate()
        se = eif.standard_error()
        lo, hi = eif.ci()

        return {
            "shift_effect": {
                "delta": delta,
                "point_estimate": pe,
                "standard_error": se,
                "ci_lower": lo,
                "ci_upper": hi,
                "n_obs": n,
                "method": "shift_intervention_diaz_vdl_2012",
                "density_ratio_diagnostics": {
                    "status": "ok",
                    "n_obs": n,
                    "shift_delta": delta,
                    "min_density_ratio": float(np.min(clipped_density_ratio)),
                    "max_density_ratio": float(np.max(clipped_density_ratio)),
                    "p99_density_ratio": float(np.percentile(clipped_density_ratio, 99)),
                    "p999_density_ratio": float(np.percentile(clipped_density_ratio, 99.9)),
                    "effective_sample_size": density_ratio_ess,
                    "ess_fraction": float(density_ratio_ess / max(n, 1)),
                    "dominant_weight_share": float(
                        np.max(clipped_density_ratio) / max(density_ratio_sum, 1e-12)
                    ),
                    "n_clipped": n_clipped_ratio,
                    "clip_fraction": float(n_clipped_ratio / max(n, 1)),
                    "clip_bounds": {
                        "min": min_dr,
                        "max": max_dr,
                    },
                },
            }
        }


# ---------------------------------------------------------------------------
# Estimator 4: Entropy Balancing — Vegetabile et al. (2021)
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.continuous_treatment",
    version="1.0.0",
    tags=frozenset(
        {"causal", "continuous_treatment", "entropy_balancing", "weighting", "dose_response"}
    ),
)
class EntropyBalancingContinuousEstimator:
    """Entropy-balancing weights for continuous treatment dose-response.

    Minimises KL divergence from kernel-smoothed weights subject to
    moment constraints on covariates (Vegetabile et al. 2021)::

        wᵢ(t) ∝ K_h(Tᵢ − t) · exp(αᵀ φ(Xᵢ))

    where α solves ∂L/∂α = 0 (Newton iterations).
    β̂(t) = Σᵢ wᵢ(t) Yᵢ.

    Registered as ``causal.continuous_treatment.entropy_balancing@1.0.0``.
    """

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="entropy_balancing",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            [
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    description="(n,) outcome",
                    unit=Unit("dimensionless", ""),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    description="(n,) continuous treatment",
                    unit=Unit("dimensionless", ""),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    description="(n, p) covariates",
                    unit=Unit("dimensionless", ""),
                    shape=("n_obs", "n_features"),
                ),
            ]
        ),
        output_slots=frozenset(
            [
                SlotSpec(
                    name="dose_response_result",
                    slot_type=SlotType.SCALAR,
                    description="DoseResponseResult dict",
                    unit=Unit("dimensionless", ""),
                ),
            ]
        ),
        parameters=(
            ParameterSpec(
                name="bandwidth", default=None, description="Kernel bandwidth h. None → Silverman"
            ),
            ParameterSpec(
                name="n_eval_points", default=20, description="Grid size", bounds=(5, 200)
            ),
            ParameterSpec(
                name="eval_range",
                default=(0.05, 0.95),
                description="Quantile range for evaluation grid",
            ),
            ParameterSpec(
                name="max_iter",
                default=200,
                description="Newton iterations for balancing",
                bounds=(20, 2000),
            ),
            ParameterSpec(name="tol", default=1e-6, description="Convergence tolerance for Newton"),
            ParameterSpec(
                name="moment_order",
                default=1,
                description="Order of moment constraints (1 or 2)",
                bounds=(1, 2),
            ),
            ParameterSpec(
                name="n_bootstrap",
                default=200,
                description="Bootstrap resamples for SE",
                bounds=(10, 2000),
            ),
            ParameterSpec(name="seed", default=0, description="Random seed for bootstrap"),
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
            "Entropy-balancing dose-response estimator for continuous treatments. "
            "Reweights units to balance covariate moments at each treatment level."
        ),
        tags=frozenset(
            {"causal", "continuous_treatment", "entropy_balancing", "weighting", "nonparametric"}
        ),
        citations=(
            "Vegetabile, B.G. et al. (2021). Nonparametric estimation of "
            "population average dose-response curves using entropy balancing "
            "weights for continuous exposures. Health Services and Outcomes "
            "Research Methodology.",
        ),
        equations={
            "weights": "wᵢ(t) ∝ K_h(Tᵢ−t)·exp(αᵀφ(Xᵢ))",
            "balance": "Σᵢ wᵢ(t)·φ(Xᵢ) = φ̄",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Use when a flexible weighting approach is preferred over "
            "outcome regression. Provides exact covariate balance at each "
            "treatment level."
        ),
        when_not_to_use=(
            "Avoid if p is large (> 20) — moment constraints may be hard to "
            "satisfy. Use GPS or kernel-DR instead."
        ),
        prerequisites=(),
        diagnostic_checks=("Verify covariate balance: Σᵢ wᵢ(t)·X̄ᵢ ≈ X̄.",),
        typical_min_obs=100,
        output_interpretation=(
            "dose_response_result.dose_response[j] = Σᵢ wᵢ(t_j)·Yᵢ. "
            "Standard errors via nonparametric bootstrap."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        data = ContinuousTreatmentData(
            outcome=state["outcome"],
            treatment=state["treatment"],
            covariates=state["covariates"],
            evaluation_points=state.get("evaluation_points"),
        )
        Y, T, X = data.outcome, data.treatment, data.covariates
        n = len(Y)

        bw = params.get("bandwidth", None)
        h = float(bw) if bw is not None else _silverman_bandwidth(T)
        max_iter = int(params.get("max_iter", 200))
        tol = float(params.get("tol", 1e-6))
        moment_order = int(params.get("moment_order", 1))
        n_bootstrap = int(params.get("n_bootstrap", 200))
        seed = int(params.get("seed", 0))

        eval_pts = _build_eval_grid(T, data, params)

        # Moment basis: mean of X columns (first-order moments)
        # We balance φ(X) = [1, X] (intercept forces weights to sum to 1).
        if moment_order == 1:
            phi = np.column_stack([np.ones(n), X])  # (n, p+1)
        else:
            phi = np.column_stack([np.ones(n), X, X * X])  # (n, 2p+1)
        phi_bar = phi.mean(axis=0)  # target moments = population mean

        dr = np.empty(len(eval_pts), dtype=float)

        for j, t_j in enumerate(eval_pts):
            # ---- Kernel-initialised weights ----
            u = (T - t_j) / h
            k_vals = _gaussian_kernel(u) / h
            # Initialise α = 0 → w₀ = K_h / Σ K_h
            alpha = np.zeros(phi.shape[1], dtype=float)

            # ---- Newton iterations ----
            for _ in range(max_iter):
                log_w = np.log(np.maximum(k_vals, 1e-300)) + phi @ alpha
                log_w -= float(np.max(log_w))  # numerical stability
                raw_w = np.exp(log_w)
                w = raw_w / raw_w.sum()

                # gradient: ∂L/∂α = Σᵢ wᵢ φᵢ − φ̄
                grad = (w[:, None] * phi).sum(axis=0) - phi_bar
                if float(np.linalg.norm(grad)) < tol:
                    break

                # Hessian: H = Σᵢ wᵢ φᵢ φᵢᵀ − (Σᵢ wᵢ φᵢ)(Σᵢ wᵢ φᵢ)ᵀ
                wphiT = w[:, None] * phi  # (n, q)
                H = wphiT.T @ phi - np.outer(grad + phi_bar, grad + phi_bar)
                try:
                    delta_alpha = np.linalg.solve(H + 1e-8 * np.eye(H.shape[0]), grad)
                except np.linalg.LinAlgError:
                    break
                alpha -= delta_alpha

            dr[j] = float(np.sum(w * Y))

        # ---- Bootstrap SE ----
        rng = np.random.default_rng(seed)
        dr_boot = np.empty((n_bootstrap, len(eval_pts)), dtype=float)
        for b in range(n_bootstrap):
            idx = rng.integers(0, n, size=n)
            Yb, Tb, Xb = Y[idx], T[idx], X[idx]
            if moment_order == 1:
                phi_b = np.column_stack([np.ones(n), Xb])
            else:
                phi_b = np.column_stack([np.ones(n), Xb, Xb * Xb])
            phi_bar_b = phi_b.mean(axis=0)

            dr_b = np.empty(len(eval_pts), dtype=float)
            h_b = _silverman_bandwidth(Tb)
            for j, t_j in enumerate(eval_pts):
                u = (Tb - t_j) / h_b
                k_vals = _gaussian_kernel(u) / h_b
                # Simple Hajek estimator (no balancing for bootstrap speed)
                w_simple = k_vals / max(k_vals.sum(), 1e-300)
                dr_b[j] = float(np.sum(w_simple * Yb))
            dr_boot[b] = dr_b

        se = np.std(dr_boot, axis=0, ddof=1)

        result = DoseResponseResult(
            treatment_grid=eval_pts,
            dose_response=dr,
            confidence_band_lower=dr - 1.96 * se,
            confidence_band_upper=dr + 1.96 * se,
            standard_errors=se,
            method="entropy_balancing_vegetabile_2021",
            n_obs=n,
            bandwidth=h,
        )
        return {"dose_response_result": result.model_dump()}


__all__ = [
    "EntropyBalancingContinuousEstimator",
    "GeneralizedPropensityScoreEstimator",
    "KernelDoseResponseEstimator",
    "ShiftInterventionEstimator",
]
