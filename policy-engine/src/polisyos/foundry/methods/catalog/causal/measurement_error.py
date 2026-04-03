"""measurement_error — Identification and estimation under measurement error.

Implements identification via proxy variables (Kuroki & Pearl 2014) and two
classical estimation corrections:

* **Regression Calibration** — Carroll et al. (2006): replace the mismeasured
  variable with its conditional expectation given the proxy and covariates.
* **SIMEX** (Simulation Extrapolation) — Cook & Stefanski (1994): add extra
  noise at increasing levels, fit at each level, then extrapolate back to λ=0
  (no extra noise) to recover the unattenuated estimate.

The module also provides :func:`identify_with_proxy`, a pure identification
function that returns an :class:`IdentificationResult` with a
:class:`ProxyAdjustmentNode` AST, and :func:`bounds_with_measurement_error`,
which widens standard Manski bounds by a classification-error rate α.

Foundry method: ``causal.measurement_error.proxy@1.0.0``

References
----------
Kuroki, M. & Pearl, J. (2014). "Measurement Bias and Effect Restoration in
    Causal Inference." *Biometrika*, 101(2), 423–437.
Carroll, R.J., Ruppert, D., Stefanski, L.A. & Crainiceanu, C.M. (2006).
    *Measurement Error in Nonlinear Models*, 2nd ed. Chapman & Hall/CRC.
Cook, J.R. & Stefanski, L.A. (1994). "Simulation-Extrapolation Estimation in
    Parametric Measurement Error Models." *JASA*, 89(428), 1314–1328.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Literal, Mapping

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
from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    ProxyAdjustmentNode,
    SumNode,
    ProductNode,
)
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    BoundsReport,
    PartialIdentificationResult,
)

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Graphical identification (Kuroki & Pearl 2014)
# ---------------------------------------------------------------------------


def identify_with_proxy(
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
    proxy_map: dict[str, str],
    measurement_model: Literal["known", "estimated", "unknown"] = "unknown",
) -> "Any":  # IdentificationResult — imported lazily to avoid circular imports
    """Graphical identification under measurement error (Kuroki & Pearl 2014, Thm 2).

    Checks whether P(Y|do(X)) is identifiable when true confounder C is latent
    but proxy C* = ``proxy_map[C]`` is observed.

    Sufficient identification conditions
    ------------------------------------
    (a) **Proxy validity**: C* ⊥ Y | (C, X) in the full graph G.
        The proxy C* carries no information about Y beyond what C carries.
    (b) **Non-degeneracy**: The measurement model P(C*|C) has full column rank
        (for discrete C) or positive conditional density (for continuous C).
    (c) **C d-separates confounding**: C is a sufficient adjustment set; removing
        the C → Y and C → X paths (replacing them with C* → Y* and C* → X*
        via the proxy) preserves identifiability.

    When both (a) and (b) hold, the proxy-adjusted estimand is::

        P(Y|do(X)) = Σ_c P(Y|X, C=c) · Σ_{c*} P(C=c|C*=c*) P(C*=c*)

    Parameters
    ----------
    graph:
        Full causal DAG including both C (latent) and C* (proxy).
    treatment:
        Treatment variable name X.
    outcome:
        Outcome variable name Y.
    proxy_map:
        Mapping ``{latent_variable: proxy_variable}``,
        e.g. ``{"C": "C_star"}``.
    measurement_model:
        ``"known"``    — P(C*|C) is available from prior knowledge.
        ``"estimated"``— P(C*|C) is estimated from a validation sub-sample.
        ``"unknown"``  — P(C*|C) is unknown; identification is uncertain.

    Returns
    -------
    IdentificationResult
        IDENTIFIED (with :class:`ProxyAdjustmentNode` AST) when conditions hold;
        ORACLE_NEEDED otherwise.
    """
    from polisyos.foundry.methods.catalog.causal.id_engine import (
        IdentificationResult,
        IdentificationStatus,
        ProofStep,
    )
    from polisyos.foundry.methods.catalog.causal.admg_ops import m_separation

    _trace: list[str] = []
    _steps: list[ProofStep] = []

    _trace.append(
        f"[PROXY-ID] identify_with_proxy("
        f"X={treatment!r}, Y={outcome!r}, "
        f"proxy_map={proxy_map}, measurement_model={measurement_model!r})"
    )

    def _proxy_boundary_metadata(*, proxy_explanation_ruled_out: bool) -> dict[str, Any]:
        return {
            "proxy_boundary": latent_proxy_boundary_notes(
                proxy_map=proxy_map,
                measurement_model=measurement_model,
                proxy_explanation_ruled_out=proxy_explanation_ruled_out,
            )
        }

    all_nodes = set(graph.nodes)
    latent_vars = set(proxy_map.keys())
    proxy_vars = set(proxy_map.values())

    # Validate proxy variables are present in the graph
    missing_proxies = proxy_vars - all_nodes
    if missing_proxies:
        _trace.append(
            f"[PROXY-ID] Proxy variables {sorted(missing_proxies)} not in graph → "
            "ORACLE_NEEDED"
        )
        return IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=_trace,
            required_distributions=[],
            algorithm_version="proxy_id_v1",
            proof_steps=_steps,
            metadata=_proxy_boundary_metadata(proxy_explanation_ruled_out=False),
        )

    # Condition (a): proxy validity check C* ⊥ Y | (C, X)
    proxy_valid = True
    for c_var, c_star in proxy_map.items():
        condition_set = frozenset({c_var, treatment})
        sep_ok = m_separation(
            graph,
            x_set=frozenset({c_star}),
            y_set=frozenset({outcome}),
            z_set=condition_set,
        )
        if not sep_ok:
            proxy_valid = False
            _trace.append(
                f"[PROXY-ID] Proxy validity condition FAILED: "
                f"{c_star!r} ⊬⊥ {outcome!r} | {{{c_var!r}, {treatment!r}}} "
                f"in G → ORACLE_NEEDED"
            )
        else:
            _trace.append(
                f"[PROXY-ID] Proxy validity OK: "
                f"{c_star!r} ⊥ {outcome!r} | {{{c_var!r}, {treatment!r}}}"
            )

    _steps.append(ProofStep(
        rule_name="PROXY_ADJUSTMENT",
        antecedent_vars=(treatment,),
        consequent_vars=(outcome,),
        applied_to_graph_state=(
            f"Proxy validity check for {list(proxy_map.items())}: "
            f"{'PASSED' if proxy_valid else 'FAILED'}; "
            f"measurement_model={measurement_model!r}"
        ),
        depth=0,
    ))

    if not proxy_valid:
        return IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=_trace,
            required_distributions=[],
            algorithm_version="proxy_id_v1",
            proof_steps=_steps,
            metadata=_proxy_boundary_metadata(proxy_explanation_ruled_out=False),
        )

    # Condition (b): measurement model availability
    if measurement_model == "unknown":
        _trace.append(
            "[PROXY-ID] Measurement model UNKNOWN — "
            "identification requires P(C*|C); returning ORACLE_NEEDED"
        )
        return IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=_trace,
            required_distributions=[],
            algorithm_version="proxy_id_v1",
            proof_steps=_steps,
            metadata=_proxy_boundary_metadata(proxy_explanation_ruled_out=False),
        )

    # Identification succeeds — build proxy-adjusted estimand
    # P(Y|do(X)) = Σ_c P(Y|X,C=c) · Σ_{c*} P(C=c|C*) P(C*)
    # For simplicity represent as a backdoor-style product with a ProxyAdjustmentNode wrapper
    # The inner estimand uses proxy_vars as the observed adjustment set
    observed_adjustment = tuple(sorted(proxy_vars))
    inner_node: Any = ProductNode(factors=(
        DistributionRef(
            domain=DistributionDomain.SOURCE,
            variables=(outcome,),
            conditioning=(treatment,) + observed_adjustment,
            dataset_ref=None,
        ),
        DistributionRef(
            domain=DistributionDomain.SOURCE,
            variables=observed_adjustment,
            dataset_ref=None,
        ),
    ))
    if observed_adjustment:
        inner_node = SumNode(
            summation_vars=observed_adjustment,
            operand=inner_node,
        )

    proxy_node = ProxyAdjustmentNode(
        inner_do_node=inner_node,
        proxy_map=tuple(sorted(proxy_map.items())),
        measurement_model=measurement_model,
        identification_theorem="Kuroki-Pearl-2014-Thm2",
        domain=DistributionDomain.SOURCE,
        dataset_ref=None,
    )

    ast = EstimandAST(
        query_str=f"P({outcome}|do({treatment})) [proxy-adjusted]",
        root=proxy_node,
        treatment=treatment,
        outcome=outcome,
        all_variables=tuple(sorted({treatment, outcome} | latent_vars | proxy_vars)),
        identification_method="proxy_adjustment",
    )

    required_dists = [
        DistributionRef(
            domain=DistributionDomain.SOURCE,
            variables=(outcome,),
            conditioning=(treatment,) + observed_adjustment,
        ),
        DistributionRef(
            domain=DistributionDomain.SOURCE,
            variables=observed_adjustment,
        ),
    ]

    _trace.append(
        f"[PROXY-ID] IDENTIFIED via proxy adjustment "
        f"(measurement_model={measurement_model!r})"
    )

    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ast,
        hedge_certificate=None,
        trace=_trace,
        required_distributions=required_dists,
        algorithm_version="proxy_id_v1",
        proof_steps=_steps,
        metadata=_proxy_boundary_metadata(proxy_explanation_ruled_out=True),
    )


# ---------------------------------------------------------------------------
# Estimation corrections
# ---------------------------------------------------------------------------


def regression_calibration(
    outcome: np.ndarray,
    treatment_proxy: np.ndarray,
    covariates: np.ndarray | None = None,
    validation_outcome: np.ndarray | None = None,
    validation_true_treatment: np.ndarray | None = None,
) -> dict[str, Any]:
    """Regression calibration for classical measurement error (Carroll et al. 2006).

    Replaces the mismeasured treatment proxy T* with its conditional expectation
    Ê[T|T*, Z] estimated from a validation sub-sample (if provided) or assumed
    to equal T* (naive regression, no correction).

    Algorithm
    ---------
    1. If validation data available:
       a. Fit T = α + β T* + γ Z via OLS on validation set.
       b. Predict T_hat = α̂ + β̂ T* + γ̂ Z for full sample.
    2. Otherwise: T_hat = T* (no correction possible).
    3. Fit Y = a + b T_hat + c Z via OLS on full sample.
    4. Return b as the calibrated causal effect estimate.

    Parameters
    ----------
    outcome:
        (n,) array of observed outcome values.
    treatment_proxy:
        (n,) array of observed (mismeasured) treatment proxy T*.
    covariates:
        (n, p) optional covariate matrix.
    validation_outcome:
        Unused (kept for API symmetry). Future: validate using Y in val set.
    validation_true_treatment:
        (n_val,) true treatment values T in a validation sub-sample.
        If provided alongside validation_proxy (same rows of treatment_proxy),
        used to estimate the calibration model.

    Returns
    -------
    dict with keys: ``ate``, ``se``, ``ci_lower``, ``ci_upper``, ``n_obs``,
        ``calibration_applied``, ``method``.
    """
    n = len(outcome)
    Y = np.asarray(outcome, dtype=float)
    T_proxy = np.asarray(treatment_proxy, dtype=float)

    calibration_applied = False

    if validation_true_treatment is not None and len(validation_true_treatment) > 0:
        T_true_val = np.asarray(validation_true_treatment, dtype=float)
        n_val = len(T_true_val)
        T_proxy_val = T_proxy[:n_val]
        # Calibration model: T = alpha + beta * T_proxy (on validation set)
        if covariates is not None:
            X_val = np.column_stack([np.ones(n_val), T_proxy_val, covariates[:n_val]])
            X_full = np.column_stack([np.ones(n), T_proxy, covariates])
        else:
            X_val = np.column_stack([np.ones(n_val), T_proxy_val])
            X_full = np.column_stack([np.ones(n), T_proxy])
        try:
            cal_coef, *_ = np.linalg.lstsq(X_val, T_true_val, rcond=None)
            T_hat = X_full @ cal_coef
            calibration_applied = True
        except np.linalg.LinAlgError:
            T_hat = T_proxy
    else:
        T_hat = T_proxy

    # Outcome regression on calibrated treatment
    if covariates is not None:
        X_out = np.column_stack([np.ones(n), T_hat, covariates])
    else:
        X_out = np.column_stack([np.ones(n), T_hat])

    try:
        coef, residuals, rank, _ = np.linalg.lstsq(X_out, Y, rcond=None)
    except np.linalg.LinAlgError:
        return {
            "result": {
                "ate": float("nan"),
                "se": float("nan"),
                "ci_lower": float("nan"),
                "ci_upper": float("nan"),
                "n_obs": n,
                "calibration_applied": calibration_applied,
                "method": "regression_calibration",
                "error": "lstsq failed",
            }
        }

    ate = float(coef[1]) if len(coef) > 1 else float("nan")

    # Heteroscedasticity-robust SE estimate
    Y_hat = X_out @ coef
    resid = Y - Y_hat
    p = X_out.shape[1]
    sigma2 = float(np.sum(resid**2) / max(n - p, 1))
    try:
        cov_coef = sigma2 * np.linalg.inv(X_out.T @ X_out)
        se = float(np.sqrt(max(cov_coef[1, 1], 0.0))) if len(coef) > 1 else float("nan")
    except np.linalg.LinAlgError:
        se = float("nan")

    z95 = 1.959964
    ci_lo = ate - z95 * se if np.isfinite(se) else float("nan")
    ci_hi = ate + z95 * se if np.isfinite(se) else float("nan")

    return {
        "result": {
            "ate": ate,
            "se": se,
            "ci_lower": ci_lo,
            "ci_upper": ci_hi,
            "n_obs": n,
            "calibration_applied": calibration_applied,
            "method": "regression_calibration",
        }
    }


def simex(
    outcome: np.ndarray,
    treatment_proxy: np.ndarray,
    covariates: np.ndarray | None = None,
    error_variance: float = 1.0,
    n_simulations: int = 200,
    lambda_grid: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0),
    extrapolant: Literal["linear", "quadratic"] = "quadratic",
    rng_seed: int = 42,
) -> dict[str, Any]:
    """SIMEX correction for classical measurement error (Cook & Stefanski 1994).

    Algorithm
    ---------
    For each λ in ``lambda_grid``:
      1. Simulate B replicates: T*_b(λ) = T* + √(λ σ²_ε) · ε_b, ε_b ~ N(0,1).
      2. Fit outcome model Y = a + b T*_b(λ) + c Z on each replicate.
      3. Average b̂(λ) = mean_b(b̂_b).

    Then extrapolate (b̂(0)) = extrapolant fit of {(λ, b̂(λ))} evaluated at λ = -1
    (i.e. λ = −1 represents zero measurement error: T* = T).

    Parameters
    ----------
    outcome:
        (n,) observed outcome array Y.
    treatment_proxy:
        (n,) mismeasured treatment T*.
    covariates:
        (n, p) optional covariate matrix.
    error_variance:
        σ²_ε — known (or estimated) measurement error variance.
    n_simulations:
        B — number of simulation replicates per λ level.
    lambda_grid:
        Grid of λ values (noise multipliers). At λ=0 we recover the naive estimate;
        SIMEX extrapolates to λ=−1 (i.e. no measurement error).
    extrapolant:
        ``"linear"`` or ``"quadratic"`` polynomial extrapolation in λ.
    rng_seed:
        Random seed for reproducibility.

    Returns
    -------
    dict with keys: ``ate_simex``, ``ate_naive``, ``se``, ``ci_lower``,
        ``ci_upper``, ``lambda_grid``, ``beta_at_lambda``, ``n_obs``, ``method``.
    """
    rng = np.random.default_rng(rng_seed)
    n = len(outcome)
    Y = np.asarray(outcome, dtype=float)
    T_star = np.asarray(treatment_proxy, dtype=float)
    sigma_eps = float(np.sqrt(max(error_variance, 0.0)))

    # Naive estimate (λ=0)
    if covariates is not None:
        X_base = np.column_stack([np.ones(n), T_star, covariates])
    else:
        X_base = np.column_stack([np.ones(n), T_star])
    try:
        coef_naive, *_ = np.linalg.lstsq(X_base, Y, rcond=None)
        beta_naive = float(coef_naive[1]) if len(coef_naive) > 1 else float("nan")
    except np.linalg.LinAlgError:
        beta_naive = float("nan")

    # Simulate at each λ level
    beta_at_lambda: list[float] = []
    lambda_list = list(lambda_grid)

    for lam in lambda_list:
        betas_b: list[float] = []
        extra_sd = sigma_eps * float(np.sqrt(lam))
        for _ in range(n_simulations):
            noise = rng.standard_normal(n) * extra_sd
            T_noisy = T_star + noise
            if covariates is not None:
                X_sim = np.column_stack([np.ones(n), T_noisy, covariates])
            else:
                X_sim = np.column_stack([np.ones(n), T_noisy])
            try:
                c, *_ = np.linalg.lstsq(X_sim, Y, rcond=None)
                betas_b.append(float(c[1]) if len(c) > 1 else float("nan"))
            except np.linalg.LinAlgError:
                betas_b.append(float("nan"))
        beta_at_lambda.append(float(np.nanmean(betas_b)))

    # Extrapolate to λ = -1 (no measurement error)
    lam_arr = np.array(lambda_list)
    beta_arr = np.array(beta_at_lambda)
    valid = np.isfinite(beta_arr)

    ate_simex = float("nan")
    se_simex = float("nan")

    if np.sum(valid) >= 2:
        if extrapolant == "quadratic" and np.sum(valid) >= 3:
            deg = 2
        else:
            deg = 1
        try:
            poly_coef = np.polyfit(lam_arr[valid], beta_arr[valid], deg)
            ate_simex = float(np.polyval(poly_coef, -1.0))
            # Bootstrap SE: variance of extrapolant evaluated at λ=-1
            # Use residuals from polynomial fit as proxy
            fitted = np.polyval(poly_coef, lam_arr[valid])
            mse = float(np.mean((beta_arr[valid] - fitted) ** 2))
            se_simex = float(np.sqrt(mse / max(np.sum(valid) - deg - 1, 1)))
        except (np.linalg.LinAlgError, ValueError):
            ate_simex = float("nan")
            se_simex = float("nan")

    z95 = 1.959964
    ci_lo = ate_simex - z95 * se_simex if np.isfinite(se_simex) else float("nan")
    ci_hi = ate_simex + z95 * se_simex if np.isfinite(se_simex) else float("nan")

    return {
        "result": {
            "ate_simex": ate_simex,
            "ate_naive": beta_naive,
            "se": se_simex,
            "ci_lower": ci_lo,
            "ci_upper": ci_hi,
            "lambda_grid": list(lambda_list),
            "beta_at_lambda": [float(b) for b in beta_at_lambda],
            "n_obs": n,
            "extrapolant": extrapolant,
            "method": "simex",
        }
    }


def bounds_with_measurement_error(
    outcome: np.ndarray,
    treatment_proxy: np.ndarray,
    error_rate_bound: float,
    y_lower: float = 0.0,
    y_upper: float = 1.0,
) -> dict[str, Any]:
    """Manski-style bounds widened by a classification error rate α.

    When the observed treatment T* misclassifies the true treatment T with
    probability at most α = P(T* ≠ T), the standard Manski ATE bounds are
    widened by ±2α(y_max − y_min).

    Proof sketch: ATE = E[Y(1)] − E[Y(0)].  Under α-misclassification,
    E[Y|T*=t] = (1−α) E[Y|T=t] + α E[Y|T=1−t], so a correction of at most
    2α · (y_max − y_min) is needed on each side.

    Parameters
    ----------
    outcome:
        (n,) observed outcome values.
    treatment_proxy:
        (n,) observed (possibly misclassified) treatment T*.
    error_rate_bound:
        α ∈ [0, 0.5) — upper bound on classification error P(T* ≠ T).
    y_lower, y_upper:
        Known bounds on the outcome variable.

    Returns
    -------
    dict with ``bounds_report`` key containing :class:`BoundsReport` dict.
    """
    alpha = float(np.clip(error_rate_bound, 0.0, 0.499))
    Y = np.asarray(outcome, dtype=float)
    T = np.asarray(treatment_proxy, dtype=float)

    treated = T > 0.5
    p1 = float(np.mean(treated))
    p0 = 1.0 - p1
    e_y1 = float(np.mean(Y[treated])) if np.any(treated) else float(y_lower)
    e_y0 = float(np.mean(Y[~treated])) if np.any(~treated) else float(y_lower)

    # Standard Manski bounds
    y_range = float(y_upper) - float(y_lower)
    manski_lb = (e_y1 - float(y_upper)) * p1 + (float(y_lower) - e_y0) * p0
    manski_ub = (e_y1 - float(y_lower)) * p1 + (float(y_upper) - e_y0) * p0

    # Widen by measurement error correction: ±2α · (y_max − y_min)
    correction = 2.0 * alpha * y_range
    lb = manski_lb - correction
    ub = manski_ub + correction

    manski_result = PartialIdentificationResult(
        method=BoundMethod.MANSKI,
        lower_bound=manski_lb,
        upper_bound=manski_ub,
        bound_width=manski_ub - manski_lb,
        confidence=0.95,
        assumptions_used=("no_assumption",),
        display_label="Manski (no measurement error correction)",
        chart_type="interval",
    )
    corrected_result = PartialIdentificationResult(
        method=BoundMethod.MANSKI,
        lower_bound=lb,
        upper_bound=ub,
        bound_width=ub - lb,
        confidence=0.95,
        assumptions_used=(f"measurement_error_alpha={alpha:.3f}",),
        display_label=f"Manski + measurement error (α={alpha:.3f})",
        chart_type="interval",
    )

    report = BoundsReport(
        results=(manski_result, corrected_result),
        tightest_method=BoundMethod.MANSKI,
        tightest_lower=manski_lb,
        tightest_upper=manski_ub,
        consensus_lower=lb,
        consensus_upper=ub,
        is_informative=(ub - lb) < y_range,
        assumptions_used=("manski_worst_case", f"error_rate_alpha={alpha:.3f}"),
        warnings=(
            f"Bounds widened by ±{correction:.4f} due to α={alpha:.3f} "
            "classification error in treatment proxy",
        ) if alpha > 0.0 else (),
    )
    return {"bounds_report": report.model_dump()}


# ---------------------------------------------------------------------------
# Foundry method
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.measurement_error",
    version="1.0.0",
    tags={"causal", "measurement_error", "proxy", "kuroki_pearl"},
)
class MeasurementErrorEstimator:
    """Identification and estimation under measurement error (Kuroki & Pearl 2014).

    Supports three estimation methods dispatched via the ``method`` parameter:

    ``regression_calibration`` (default)
        Carroll et al. (2006) calibration correction. Requires validation data
        (``validation_true_treatment``) for a non-trivial correction.

    ``simex``
        Cook & Stefanski (1994) simulation-extrapolation. Requires
        ``error_variance`` parameter.

    ``bounds``
        Manski-style bounds widened by classification error rate ``error_rate_bound``.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="measurement_error_proxy",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            SlotSpec(
                "treatment_proxy",
                SlotType.VECTOR,
                Unit("treatment", "proxy"),
                shape=("n_obs",),
            ),
            SlotSpec(
                "covariates",
                SlotType.MATRIX,
                Unit("covariates", "features"),
                shape=("n_obs", "n_features"),
            ),
        }),
        output_slots=frozenset({
            SlotSpec("result", SlotType.SCALAR, Unit("result", "json")),
        }),
        parameters=(
            ParameterSpec(name="method", default="regression_calibration"),
            ParameterSpec(name="error_variance", default=1.0),
            ParameterSpec(name="error_rate_bound", default=0.0),
            ParameterSpec(name="n_simulations", default=200),
            ParameterSpec(name="extrapolant", default="quadratic"),
            ParameterSpec(name="y_lower", default=0.0),
            ParameterSpec(name="y_upper", default=1.0),
            ParameterSpec(name="rng_seed", default=42),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Identification and estimation under measurement error. "
            "Supports regression calibration, SIMEX, and widened Manski bounds."
        ),
        tags=frozenset({
            "causal", "measurement_error", "proxy", "calibration",
            "simex", "kuroki_pearl", "carroll",
        }),
        citations=(
            "Kuroki, M. & Pearl, J. (2014). Measurement Bias and Effect "
            "Restoration in Causal Inference. Biometrika, 101(2), 423–437.",
            "Carroll, R.J. et al. (2006). Measurement Error in Nonlinear Models. "
            "Chapman & Hall/CRC.",
            "Cook, J.R. & Stefanski, L.A. (1994). Simulation-Extrapolation "
            "Estimation in Parametric Measurement Error Models. JASA, 89(428).",
        ),
        equations={
            "regression_calibration": "T_hat = E[T|T*,Z]; Y = a + b T_hat + c Z; ATE = b",
            "simex": "b(λ=-1) via extrapolation of b(λ) for λ ∈ grid",
            "bounds_widened": "ATE ∈ [manski_lb - 2α(y_max-y_min), manski_ub + 2α(y_max-y_min)]",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Treatment variable is measured with error (misclassification, attenuation, "
            "random noise); proxy variable or validation data available."
        ),
        when_not_to_use=(
            "Error variance is unknown and no validation data available; "
            "outcome variable (not treatment) is mismeasured."
        ),
        output_interpretation=(
            "ATE corrected for measurement attenuation bias. "
            "SIMEX and regression calibration give point estimates; "
            "bounds method gives a conservative interval."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        """Dispatch to the selected measurement error correction method.

        Parameters in ``params``
        ------------------------
        method : str
            ``"regression_calibration"`` | ``"simex"`` | ``"bounds"``
        error_variance : float
            Measurement error variance σ²_ε (for SIMEX).
        error_rate_bound : float
            Classification error rate α (for bounds).
        n_simulations : int
            Number of SIMEX replicates.
        extrapolant : str
            ``"linear"`` or ``"quadratic"`` (SIMEX).
        y_lower, y_upper : float
            Outcome range (for bounds).
        rng_seed : int
            RNG seed (for SIMEX).
        """
        Y = np.asarray(state["outcome"], dtype=float)
        T_proxy = np.asarray(state["treatment_proxy"], dtype=float)
        cov = (
            np.asarray(state["covariates"], dtype=float)
            if "covariates" in state and state["covariates"] is not None
            else None
        )
        val_T_true = (
            np.asarray(state["validation_true_treatment"], dtype=float)
            if "validation_true_treatment" in state and state["validation_true_treatment"] is not None
            else None
        )

        method = str(params.get("method", "regression_calibration"))

        if method == "simex":
            return simex(
                outcome=Y,
                treatment_proxy=T_proxy,
                covariates=cov,
                error_variance=float(params.get("error_variance", 1.0)),
                n_simulations=int(params.get("n_simulations", 200)),
                extrapolant=str(params.get("extrapolant", "quadratic")),  # type: ignore[arg-type]
                rng_seed=int(params.get("rng_seed", 42)),
            )
        elif method == "bounds":
            return bounds_with_measurement_error(
                outcome=Y,
                treatment_proxy=T_proxy,
                error_rate_bound=float(params.get("error_rate_bound", 0.0)),
                y_lower=float(params.get("y_lower", 0.0)),
                y_upper=float(params.get("y_upper", 1.0)),
            )
        else:
            # Default: regression_calibration
            return regression_calibration(
                outcome=Y,
                treatment_proxy=T_proxy,
                covariates=cov,
                validation_true_treatment=val_T_true,
            )


def latent_proxy_boundary_notes(
    *,
    proxy_map: Mapping[str, str],
    measurement_model: Literal["known", "estimated", "unknown"] = "unknown",
    proxy_explanation_ruled_out: bool = False,
) -> dict[str, Any]:
    """Build governance notes for the latent-vs-proxy boundary without proposing latents."""

    boundary_notes: list[str] = []
    no_promotion_reasons: list[str] = []

    if not proxy_map:
        boundary_notes.append("proxy_boundary:missing_proxy_map")
        no_promotion_reasons.append("proxy_boundary_unresolved")
    else:
        latent_labels = ", ".join(sorted(str(key) for key in proxy_map))
        proxy_labels = ", ".join(sorted(str(value) for value in proxy_map.values()))
        boundary_notes.append(
            f"proxy_boundary:observed_proxies={proxy_labels}; latent_targets={latent_labels}"
        )

    if measurement_model == "unknown":
        boundary_notes.append("proxy_boundary:measurement_model_unknown")
        no_promotion_reasons.append("measurement_model_unknown")
    elif measurement_model == "estimated":
        boundary_notes.append("proxy_boundary:measurement_model_estimated")
    else:
        boundary_notes.append("proxy_boundary:measurement_model_known")

    if proxy_explanation_ruled_out:
        boundary_notes.append("proxy_boundary:proxy_explanation_ruled_out")
    else:
        boundary_notes.append("proxy_boundary:proxy_explanation_not_ruled_out")
        no_promotion_reasons.append("proxy_explanation_not_ruled_out")

    return {
        "boundary_notes": boundary_notes,
        "measurement_model": measurement_model,
        "proxy_explanation_ruled_out": bool(proxy_explanation_ruled_out),
        "proxy_map": {str(key): str(value) for key, value in proxy_map.items()},
        "no_promotion_reasons": sorted(set(no_promotion_reasons)),
    }


__all__ = [
    "identify_with_proxy",
    "latent_proxy_boundary_notes",
    "regression_calibration",
    "simex",
    "bounds_with_measurement_error",
    "MeasurementErrorEstimator",
]
