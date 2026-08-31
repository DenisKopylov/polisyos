"""Phase 7: Advanced partial identification — sensitivity and intersection bounds.

Implements:
- TanBoundsEstimator          Tan (2006, JASA) MSM-based sensitivity sweep
- IntersectionBoundsEstimator CLR (Chernozhukov, Lee & Rosen 2013, Econometrica) intersection
- RosenbaumSharpBoundsEstimator  Sharp per-γ p-value bounds for matched pairs
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

_logger = logging.getLogger(__name__)

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
from polisyos.foundry.methods.catalog.causal.bounds import _make_partial_id_result
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    SensitivitySweepResult,
)


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


# ---------------------------------------------------------------------------
# Helpers shared with sensitivity_metrics (reimplemented here to avoid circular
# imports; these are simple enough to duplicate)
# ---------------------------------------------------------------------------


def _sign_rank_stat(diffs: np.ndarray) -> float:
    """Wilcoxon signed-rank statistic W+ = sum of ranks of positive differences."""
    abs_diffs = np.abs(diffs)
    ranks = np.argsort(np.argsort(abs_diffs)) + 1.0  # ranks 1..n
    return float(np.sum(ranks[diffs > 0]))


def _normal_signed_rank_pvalue(w_obs: float, n: int, mean_w: float, std_w: float) -> float:
    """One-sided p-value P(W+ ≥ w_obs) via normal approximation."""
    from scipy.stats import norm

    if std_w <= 0:
        return 1.0
    z = (w_obs - mean_w - 0.5) / std_w  # continuity correction
    return float(norm.sf(z))


def _sharp_pvalue_bounds(diffs: np.ndarray, gamma: float) -> tuple[float, float]:
    """Compute (p_lower, p_upper) for the signed-rank test under sensitivity Γ.

    Under Γ, each pair i has treatment-assignment probability in [1/(1+Γ), Γ/(1+Γ)].
    We compute the worst-case (p_upper) and best-case (p_lower) one-sided p-values.
    """
    n = len(diffs)
    if n == 0:
        return 1.0, 1.0

    abs_d = np.abs(diffs)
    ranks = np.argsort(np.argsort(abs_d)) + 1.0
    w_obs = float(np.sum(ranks[diffs > 0]))

    p_hi = gamma / (1.0 + gamma)  # max assignment prob → maximises W+
    p_lo = 1.0 / (1.0 + gamma)  # min assignment prob → minimises W+

    # Under Γ: E[W+] and Var[W+] depend on assignment probabilities per pair.
    # Worst case (max W+): each pair i has p_i = p_hi for positive diffs, p_lo for negative.
    pos_mask = diffs > 0
    # Worst-case: assign p_hi to positive-diff pairs, p_lo to negative-diff pairs
    # Expected W+ under worst case
    p_worst = np.where(pos_mask, p_hi, p_lo)
    e_w_worst = float(np.sum(ranks * p_worst))
    var_w_worst = float(np.sum(ranks**2 * p_worst * (1.0 - p_worst)))
    std_w_worst = math.sqrt(max(var_w_worst, 1e-12))
    p_upper = _normal_signed_rank_pvalue(w_obs, n, e_w_worst, std_w_worst)

    # Best case (min W+): assign p_lo to positive-diff pairs, p_hi to negative-diff pairs
    p_best = np.where(pos_mask, p_lo, p_hi)
    e_w_best = float(np.sum(ranks * p_best))
    var_w_best = float(np.sum(ranks**2 * p_best * (1.0 - p_best)))
    std_w_best = math.sqrt(max(var_w_best, 1e-12))
    p_lower = _normal_signed_rank_pvalue(w_obs, n, e_w_best, std_w_best)

    return float(np.clip(p_lower, 0.0, 1.0)), float(np.clip(p_upper, 0.0, 1.0))


# ---------------------------------------------------------------------------
# TanBoundsEstimator
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.bounds",
    version="1.0.0",
    tags={"causal", "bounds", "sensitivity", "tan", "msm"},
)
class TanBoundsEstimator:
    """Tan (2006, JASA) regression and weighting bounds under the Marginal Sensitivity Model.

    Under the Marginal Sensitivity Model (MSM), unmeasured confounding is bounded by the
    sensitivity parameter λ ≥ 1:

        1/λ ≤ OR(T=1|X,U) / OR(T=1|X) ≤ λ

    At λ=1 (no unmeasured confounding) the bounds collapse to the standard IPW ATE.
    As λ increases, bounds widen to reflect uncertainty from unmeasured confounders.

    Computation follows the trimmed-weights approach:
    - Lower bound: use propensity-based weight trimmed down by factor λ
    - Upper bound: use propensity-based weight trimmed up by factor λ

    Reference: Tan, Z. (2006). Regression and weighting methods for causal inference
    using instrumental variables. JASA 101(476):1607–1618.
    See also: Zhao, Small & Bhattacharya (2019). Sensitivity analysis for inverse
    probability weighting estimators via the percentile bootstrap. JRSS-B.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "sklearn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="tan_bounds",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "numeric"), shape=("n_obs",)),
                SlotSpec(
                    "treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)
                ),
                SlotSpec(
                    "propensity_scores",
                    SlotType.VECTOR,
                    Unit("propensity", "probability"),
                    shape=("n_obs",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(
                name="lambda_values",
                default=None,
                description=(
                    "List of λ sensitivity values ≥ 1. "
                    "None uses [1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]."
                ),
            ),
            ParameterSpec(
                name="min_propensity",
                default=0.01,
                description="Clip propensity scores below this value to avoid extreme weights.",
            ),
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
            "Tan (2006) sensitivity sweep for ATE under the Marginal Sensitivity Model. "
            "Returns bounds on ATE as a function of the sensitivity parameter λ."
        ),
        tags=frozenset({"causal", "bounds", "sensitivity", "tan", "msm", "partial-identification"}),
        citations=(
            "Tan, Z. (2006). Regression and weighting methods for causal inference "
            "using instrumental variables. JASA 101(476):1607–1618.",
            "Zhao, Q., Small, D.S. & Bhattacharya, B.B. (2019). Sensitivity analysis "
            "for inverse probability weighting. JRSS-B 81(1):207–231.",
        ),
        equations={
            "msm": "1/λ ≤ OR(T=1|X,U) / OR(T=1|X) ≤ λ",
            "ipw_upper": "Σ_{T=1} w_hi(i)*Y_i / Σ_{T=1} w_hi(i) − Σ_{T=0} w_lo(i)*Y_i / Σ_{T=0} w_lo(i)",
            "w_hi": "w_hi(i) = min(λ, 1/π(X_i))  for T=1",
            "w_lo": "w_lo(i) = max(1/λ, 1/π(X_i))  for T=1",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy", "sklearn"),
        when_to_use=(
            "Assessing robustness of ATE to unmeasured confounding when a propensity model "
            "can be estimated. Reports how large λ must be for the bounds to include 0."
        ),
        when_not_to_use=(
            "No reasonable propensity model available; use Manski or Rosenbaum bounds instead."
        ),
        output_interpretation=(
            "sweep: SensitivitySweepResult with lower/upper ATE bounds per λ. "
            "ate_lower_bound/ate_upper_bound: bounds at λ=1 (i.e., the standard IPW ATE). "
            "critical_lambda: smallest λ where lower bound ≤ 0 (effect may be explained away)."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        Y = np.asarray(state["outcome"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        n = len(Y)
        min_ps = float(params.get("min_propensity", 0.01))

        raw_lambda = params.get("lambda_values")
        if raw_lambda is None:
            lambda_values = [1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]
        else:
            lambda_values = [float(v) for v in raw_lambda]

        # Obtain propensity scores
        ps_raw = state.get("propensity_scores")
        if ps_raw is not None:
            ps = np.clip(np.asarray(ps_raw, dtype=float), min_ps, 1.0 - min_ps)
        else:
            # Fit logistic propensity using a constant predictor (marginal PS)
            # If no covariates available, use marginal P(T=1) as constant PS
            p_t = float(np.mean(T > 0.5))
            p_t = float(np.clip(p_t, min_ps, 1.0 - min_ps))
            ps = np.full(n, p_t)

        treated = T > 0.5
        y1 = Y[treated]
        y0 = Y[~treated]
        ps1 = ps[treated]
        ps0 = ps[~treated]

        lowers: list[float] = []
        uppers: list[float] = []

        for lam in lambda_values:
            if lam < 1.0:
                lam = 1.0

            # IPW weights for treated: w(i) = 1/π(X_i)
            # Under MSM: effective weight clipped to [1/λ, λ] / π(X_i)
            # Upper bound: maximize E[Y(1)] - E[Y(0)]
            #   treated: use w_hi = min(λ/π, 1) normalised   → amplify high-Y treated
            #   control: use w_lo = max(1/(λ*(1-π)), 1) normalised → amplify low-Y control
            # Lower bound: reverse the clipping

            # Treated group weights (unnormalized)
            w1_hi = np.clip(1.0 / ps1, 1.0, lam / ps1)  # max weight for treated
            w1_lo = np.clip(1.0 / ps1, 1.0 / lam / ps1, 1.0)  # min weight for treated

            # Control group weights (unnormalized)
            w0_hi = np.clip(1.0 / (1.0 - ps0), 1.0, lam / (1.0 - ps0))
            w0_lo = np.clip(1.0 / (1.0 - ps0), 1.0 / (lam * (1.0 - ps0)), 1.0)

            # Normalise within each arm
            sum_w1_hi = float(np.sum(w1_hi)) or 1.0
            sum_w1_lo = float(np.sum(w1_lo)) or 1.0
            sum_w0_hi = float(np.sum(w0_hi)) or 1.0
            sum_w0_lo = float(np.sum(w0_lo)) or 1.0

            mu1_hi = float(np.sum(w1_hi * y1) / sum_w1_hi)
            mu1_lo = float(np.sum(w1_lo * y1) / sum_w1_lo)
            mu0_hi = float(np.sum(w0_hi * y0) / sum_w0_hi)
            mu0_lo = float(np.sum(w0_lo * y0) / sum_w0_lo)

            upper_ate = mu1_hi - mu0_lo
            lower_ate = mu1_lo - mu0_hi
            lowers.append(min(lower_ate, upper_ate))
            uppers.append(max(lower_ate, upper_ate))

        # Critical lambda: smallest λ where lower bound ≤ 0 (sign may flip)
        ate_at_lam1 = lowers[0] if lowers else 0.0
        critical_lambda: float | None = None
        if ate_at_lam1 > 0:
            for lv, lb in zip(lambda_values, lowers):
                if lb <= 0.0:
                    critical_lambda = float(lv)
                    break
        elif ate_at_lam1 < 0:
            for lv, ub in zip(lambda_values, uppers):
                if ub >= 0.0:
                    critical_lambda = float(lv)
                    break

        sweep = SensitivitySweepResult(
            parameter_name="lambda",
            parameter_values=tuple(float(v) for v in lambda_values),
            lower_bounds=tuple(lowers),
            upper_bounds=tuple(uppers),
            critical_value=critical_lambda,
            method=BoundMethod.TAN_BOUNDS,
            display_label="Tan (2006) MSM Sensitivity Sweep",
        )

        partial_id = _make_partial_id_result(
            lower=lowers[0],
            upper=uppers[0],
            method=BoundMethod.TAN_BOUNDS,
            assumptions=["marginal_sensitivity_model", "propensity_model_partial"],
            confidence=0.9,
            display_label="Tan Bounds (λ=1)",
        )

        return {
            "result": {
                "sweep": sweep.model_dump(),
                "ate_lower_bound": lowers[0],
                "ate_upper_bound": uppers[0],
                "critical_lambda": critical_lambda,
                "partial_id_result": partial_id,
                "n_obs": n,
            }
        }


# ---------------------------------------------------------------------------
# IntersectionBoundsEstimator
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.bounds",
    version="1.0.0",
    tags={
        "causal",
        "bounds",
        "intersection",
        "clr",
        "estimation",
        "cross-section",
        "partial-identification",
    },
)
class IntersectionBoundsEstimator:
    """Chernozhukov, Lee & Rosen (2013) intersection of identified sets.

    If under assumption set k, the true parameter θ lies in [L_k, U_k], then under
    the conjunction of all assumption sets:

        θ ∈ ∩_k [L_k, U_k] = [max_k L_k, min_k U_k]

    This estimator takes a list of pre-computed bound sets and returns their intersection.

    Statistical inference
    ---------------------
    Two modes are supported:

    1. **Conservative (default)**: Pointwise intersection with no additional adjustment.
       The intersection itself is returned as both the point estimate and CI.

    2. **CLR bootstrap** (``use_clr_bootstrap=True``): Approximates the CLR (2013)
       simulation-based inference.  Each bound set must provide a ``se`` field.
       The bootstrap simulates the distribution of the maximum/minimum of correlated
       Gaussian estimates and returns percentile-based CIs.

    Reference: Chernozhukov, V., Lee, S. & Rosen, A.M. (2013). Intersection bounds:
    estimation and inference. Econometrica 81(2):667–737.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="intersection_bounds",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "bounds_list",
                    SlotType.SCALAR,
                    Unit("bounds", "json"),
                    description=(
                        "List of dicts, each with 'ate_lower_bound', 'ate_upper_bound', "
                        "and optionally 'se'."
                    ),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="alpha", default=0.05, description="Significance level for CI."),
            ParameterSpec(
                name="n_obs",
                default=100,
                description="Number of observations (used for bootstrap SE scaling).",
            ),
            ParameterSpec(
                name="use_clr_bootstrap",
                default=False,
                description="If True, use CLR-style bootstrap for inference.",
            ),
            ParameterSpec(name="n_bootstrap", default=500, description="Bootstrap replicates."),
            ParameterSpec(name="seed", default=0, description="RNG seed for bootstrap."),
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
            "CLR (2013) intersection bounds: pointwise intersection of multiple identified sets "
            "with optional bootstrap-based inference."
        ),
        tags=frozenset({"causal", "bounds", "intersection", "clr", "partial-identification"}),
        citations=(
            "Chernozhukov, V., Lee, S. & Rosen, A.M. (2013). "
            "Intersection bounds: estimation and inference. Econometrica 81(2):667–737.",
        ),
        equations={
            "intersection": "θ ∈ ∩_k [L_k, U_k] = [max_k L_k, min_k U_k]",
            "clr_boot": "CI via percentiles of bootstrap distribution of max_k L̂_k, min_k Û_k",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Multiple partial identification methods have been run and you want to "
            "combine their identified sets into a single tighter interval."
        ),
        when_not_to_use="Only one bound set available; intersection degenerates to that set.",
        output_interpretation=(
            "[ate_lower_bound, ate_upper_bound] = intersection of all supplied bound intervals. "
            "This is never wider than any individual interval."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        bounds_list = list(state["bounds_list"])
        alpha = float(params.get("alpha", 0.05))
        use_clr = bool(params.get("use_clr_bootstrap", False))
        n_bootstrap = int(params.get("n_bootstrap", 500))
        rng_seed = int(params.get("seed", 0))
        n_obs = int(params.get("n_obs", 100))

        if not bounds_list:
            return {
                "result": {
                    "ate_lower_bound": -np.inf,
                    "ate_upper_bound": np.inf,
                    "ci_lower": -np.inf,
                    "ci_upper": np.inf,
                    "n_methods": 0,
                    "partial_id_result": _make_partial_id_result(
                        lower=-1.0,
                        upper=1.0,
                        method=BoundMethod.INTERSECTION_BOUNDS,
                        assumptions=[],
                        confidence=0.0,
                        display_label="Intersection Bounds (empty)",
                    ),
                }
            }

        lowers = [float(b["ate_lower_bound"]) for b in bounds_list]
        uppers = [float(b["ate_upper_bound"]) for b in bounds_list]

        intersection_lower = max(lowers)
        intersection_upper = min(uppers)

        # --- CI computation ---
        if use_clr and n_obs > 1:
            # CLR-style bootstrap: simulate the distribution of max/min of Gaussian estimates.
            # Each bound provides an optional 'se' field. If absent, assume se=0 (conservative).
            ses = [float(b.get("se", 0.0)) for b in bounds_list]
            K = len(bounds_list)
            rng = np.random.default_rng(rng_seed)

            boot_max_lower: list[float] = []
            boot_min_upper: list[float] = []
            se_scale = 1.0 / math.sqrt(max(n_obs, 1))
            for _ in range(n_bootstrap):
                noise = rng.standard_normal(K)
                bl = [lowers[i] + ses[i] * se_scale * noise[i] for i in range(K)]
                bu = [uppers[i] + ses[i] * se_scale * noise[i] for i in range(K)]
                boot_max_lower.append(max(bl))
                boot_min_upper.append(min(bu))

            ci_lower = float(np.quantile(boot_max_lower, alpha / 2))
            ci_upper = float(np.quantile(boot_min_upper, 1.0 - alpha / 2))
        else:
            # Conservative: pointwise (no additional widening)
            ci_lower = intersection_lower
            ci_upper = intersection_upper

        partial_id = _make_partial_id_result(
            lower=intersection_lower,
            upper=intersection_upper,
            method=BoundMethod.INTERSECTION_BOUNDS,
            assumptions=[f"conjunction_of_{len(bounds_list)}_assumption_sets"],
            confidence=1.0 - alpha,
            display_label=f"Intersection Bounds ({len(bounds_list)} methods)",
        )

        return {
            "result": {
                "ate_lower_bound": intersection_lower,
                "ate_upper_bound": intersection_upper,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "n_methods": len(bounds_list),
                "partial_id_result": partial_id,
                "n_obs": n_obs,
            }
        }


# ---------------------------------------------------------------------------
# RosenbaumSharpBoundsEstimator
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.bounds",
    version="1.0.0",
    tags={"causal", "bounds", "rosenbaum", "sensitivity", "matched-pairs"},
)
class RosenbaumSharpBoundsEstimator:
    """Sharp per-γ p-value bounds for matched pairs (Rosenbaum 2002).

    Unlike a critical-γ scan (which returns only the scalar Γ* where the null
    is first rejected), this estimator returns the full p-value interval
    [p_lower(γ), p_upper(γ)] for every γ in a user-specified grid.

    At each γ, ``p_upper`` is the worst-case one-sided p-value (maximises the
    chance of falsely accepting the null), and ``p_lower`` is the best-case
    p-value.  The critical γ is the smallest value where ``p_upper > α``.

    Algorithm
    ---------
    Uses the Wilcoxon signed-rank test with a normal approximation.
    For each pair, the assignment probability lies in [1/(1+γ), γ/(1+γ)].
    The worst-case expected W+ assigns γ/(1+γ) to pairs with positive differences;
    the best-case assigns 1/(1+γ).

    Input options
    -------------
    - If ``is_matched_diffs=True`` (default False): ``outcome`` contains pre-computed
      pair differences d_i = Y_{treated,i} - Y_{control,i}.
    - Otherwise: ``outcome`` and ``treatment`` are raw arrays; nearest-neighbour
      matching is performed on ranks (no covariates — use when no covariate info
      available or matching is done externally).

    Reference: Rosenbaum, P.R. (2002). Observational Studies. 2nd ed. Springer.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="rosenbaum_sharp",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "outcome",
                    SlotType.VECTOR,
                    Unit("outcome", "numeric"),
                    shape=("n_obs",),
                    description="Outcomes (or pre-computed matched diffs if is_matched_diffs=True).",
                ),
                SlotSpec(
                    "treatment",
                    SlotType.VECTOR,
                    Unit("treatment", "binary"),
                    shape=("n_obs",),
                    description="Binary treatment indicator (not needed if is_matched_diffs=True).",
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(
                name="gamma_values",
                default=None,
                description="Grid of Γ values ≥ 1. None → np.arange(1.0, 4.1, 0.25).",
            ),
            ParameterSpec(name="alpha", default=0.05, description="Significance level."),
            ParameterSpec(
                name="is_matched_diffs",
                default=False,
                description=(
                    "If True, treat 'outcome' as pre-computed matched pair differences "
                    "d_i = Y_treated - Y_control. Skips matching step."
                ),
            ),
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
            "Sharp per-γ p-value bounds for the Wilcoxon signed-rank test under "
            "Rosenbaum sensitivity analysis."
        ),
        tags=frozenset(
            {
                "causal",
                "bounds",
                "rosenbaum",
                "sensitivity",
                "matched-pairs",
                "partial-identification",
            }
        ),
        citations=("Rosenbaum, P.R. (2002). Observational Studies. 2nd ed. Springer.",),
        equations={
            "assignment_range": "P(T_i=1 | pair i) ∈ [1/(1+Γ), Γ/(1+Γ)]",
            "w_plus": "W+ = Σ_i rank(|d_i|) × 1(d_i > 0)",
            "p_upper": "P(W+ ≥ w_obs | worst-case assignment) via normal approximation",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy", "scipy"),
        when_to_use=(
            "Matched-pairs observational study; want to know how large hidden bias (Γ) "
            "would need to be to invalidate the conclusion."
        ),
        when_not_to_use=("No matched pairs available; use E-value or Manski bounds instead."),
        output_interpretation=(
            "sweep: p-value bounds [p_lower, p_upper] per Γ value. "
            "critical_gamma: Γ* where p_upper first exceeds α — "
            "hidden bias must exceed Γ* to explain away the result."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        alpha = float(params.get("alpha", 0.05))
        is_matched_diffs = bool(params.get("is_matched_diffs", False))

        raw_gamma = params.get("gamma_values")
        if raw_gamma is None:
            gamma_values = list(np.arange(1.0, 4.1, 0.25).tolist())
        else:
            gamma_values = [float(g) for g in raw_gamma]

        if is_matched_diffs:
            # outcome already contains pair differences
            diffs_all = np.asarray(state["outcome"], dtype=float)
        else:
            Y = np.asarray(state["outcome"], dtype=float)
            T = np.asarray(state.get("treatment", np.zeros_like(Y)), dtype=float)
            treated = T > 0.5
            y1 = Y[treated]
            y0 = Y[~treated]

            # Simple matching: match treated to control by nearest outcome rank
            if len(y1) == 0 or len(y0) == 0:
                return {
                    "result": {
                        "sweep": SensitivitySweepResult(
                            parameter_name="gamma",
                            parameter_values=tuple(gamma_values),
                            lower_bounds=tuple(1.0 for _ in gamma_values),
                            upper_bounds=tuple(1.0 for _ in gamma_values),
                            critical_value=None,
                            method=BoundMethod.ROSENBAUM_SHARP,
                            display_label="Rosenbaum Sharp Bounds (no pairs)",
                        ).model_dump(),
                        "critical_gamma": None,
                        "n_pairs": 0,
                    }
                }

            # Nearest-rank matching (outcome-rank proximity)
            r1 = np.argsort(np.argsort(y1))
            r0 = np.argsort(np.argsort(y0))
            n_pairs = min(len(y1), len(y0))
            diffs_list: list[float] = []
            used0: set[int] = set()
            for i in range(len(y1)):
                if len(diffs_list) >= n_pairs:
                    break
                dists = np.abs(r0 - r1[i]).astype(float)
                for j in np.argsort(dists):
                    j = int(j)
                    if j not in used0:
                        diffs_list.append(float(y1[i] - y0[j]))
                        used0.add(j)
                        break
            diffs_all = np.array(diffs_list, dtype=float)

        # Keep only non-zero differences for the signed-rank test
        diffs = diffs_all[np.abs(diffs_all) > 1e-12]
        n_pairs = len(diffs)

        if n_pairs < 3:
            sweep_lower = tuple(1.0 for _ in gamma_values)
            sweep_upper = tuple(1.0 for _ in gamma_values)
            sweep = SensitivitySweepResult(
                parameter_name="gamma",
                parameter_values=tuple(gamma_values),
                lower_bounds=sweep_lower,
                upper_bounds=sweep_upper,
                critical_value=None,
                method=BoundMethod.ROSENBAUM_SHARP,
                display_label="Rosenbaum Sharp Bounds (insufficient pairs)",
            )
            return {
                "result": {
                    "sweep": sweep.model_dump(),
                    "critical_gamma": None,
                    "n_pairs": n_pairs,
                    "partial_id_result": _make_partial_id_result(
                        lower=-1.0,
                        upper=1.0,
                        method=BoundMethod.ROSENBAUM_SHARP,
                        assumptions=["matched_pairs"],
                        confidence=0.0,
                        display_label="Rosenbaum Sharp Bounds (insufficient data)",
                    ),
                }
            }

        lower_pvals: list[float] = []
        upper_pvals: list[float] = []
        for gv in gamma_values:
            gv = max(1.0, float(gv))
            p_lo, p_hi = _sharp_pvalue_bounds(diffs, gv)
            lower_pvals.append(p_lo)
            upper_pvals.append(p_hi)

        # Critical gamma: smallest γ where p_upper exceeds alpha
        critical_gamma: float | None = None
        for gv, p_hi in zip(gamma_values, upper_pvals):
            if p_hi > alpha:
                critical_gamma = float(gv)
                break

        sweep = SensitivitySweepResult(
            parameter_name="gamma",
            parameter_values=tuple(float(g) for g in gamma_values),
            lower_bounds=tuple(lower_pvals),
            upper_bounds=tuple(upper_pvals),
            critical_value=critical_gamma,
            method=BoundMethod.ROSENBAUM_SHARP,
            display_label="Rosenbaum Sharp Bounds",
        )

        # Build a PartialIdentificationResult using p-values at Γ=1 as bounds
        # (Γ=1 is the no-hidden-bias scenario; [p_lower, p_upper] should be identical)
        partial_id = _make_partial_id_result(
            lower=lower_pvals[0],
            upper=upper_pvals[0],
            method=BoundMethod.ROSENBAUM_SHARP,
            assumptions=["matched_pairs", "random_assignment_within_pairs_at_gamma_1"],
            confidence=1.0 - alpha,
            display_label="Rosenbaum Sharp Bounds (Γ=1)",
        )

        return {
            "result": {
                "sweep": sweep.model_dump(),
                "critical_gamma": critical_gamma,
                "p_lower_at_gamma1": lower_pvals[0],
                "p_upper_at_gamma1": upper_pvals[0],
                "n_pairs": n_pairs,
                "partial_id_result": partial_id,
            }
        }


__all__ = [
    "IntersectionBoundsEstimator",
    "RosenbaumSharpBoundsEstimator",
    "TanBoundsEstimator",
]
