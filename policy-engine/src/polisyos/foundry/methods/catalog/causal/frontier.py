"""Frontier causal estimators for proximal, distributional, and network-aware effects."""
from __future__ import annotations

from dataclasses import is_dataclass
from statistics import NormalDist
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
from polisyos.foundry.methods.catalog.causal._common import (
    bootstrap_ci,
    build_failure_report,
    build_success_report,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal.density_ratio import compute_scalar_distributional_effect
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.foundry.methods.catalog.causal.treatment_effects import _logistic_propensity
from polisyos.ir.analytics.causal import CausalMethod, DiagnosticTest, EstimationStatus
from polisyos.ir.analytics.negative_certificate import (
    negative_certificate_from_bridge_plausibility_report,
)
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    PartialIdentificationResult,
    annotate_bounds_bundle_for_proximal_bridge_failure,
    bounds_bundle_from_partial_identification_result,
    compute_manski_bounds,
)
from polisyos.ir.analytics.proximal import (
    BridgeFailureMode,
    BridgeFallbackDisposition,
    BridgePlausibilityReport,
    BridgePlausibilitySeverity,
)


def _causal_frontier_output_slots(extra_slot: str) -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("report", SlotType.SCALAR, Unit("report", "json")),
            SlotSpec("envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            SlotSpec("warnings", SlotType.SCALAR, Unit("warning", "list")),
            SlotSpec(extra_slot, SlotType.SCALAR, Unit("result", "json")),
        }
    )


def _proximal_bridge_output_slots() -> frozenset[SlotSpec]:
    return _causal_frontier_output_slots("proximal_result") | frozenset(
        {
            SlotSpec(
                "bridge_plausibility_report",
                SlotType.SCALAR,
                Unit("bridge_plausibility", "json"),
            ),
            SlotSpec("bounds_bundle", SlotType.SCALAR, Unit("bounds", "json")),
            SlotSpec(
                "negative_certificate",
                SlotType.SCALAR,
                Unit("negative_certificate", "json"),
            ),
        }
    )


def _spatial_proximal_bridge_output_slots() -> frozenset[SlotSpec]:
    return _causal_frontier_output_slots("spatial_proximal_result") | frozenset(
        {
            SlotSpec(
                "bridge_plausibility_report",
                SlotType.SCALAR,
                Unit("bridge_plausibility", "json"),
            ),
            SlotSpec("bounds_bundle", SlotType.SCALAR, Unit("bounds", "json")),
            SlotSpec(
                "negative_certificate",
                SlotType.SCALAR,
                Unit("negative_certificate", "json"),
            ),
        }
    )


def _observational_payload(state: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, Mapping[str, Any]]:
    if isinstance(state, HTEObservationalData):
        return (
            np.asarray(state.outcome, dtype=float),
            np.asarray(state.treatment, dtype=float),
            np.asarray(state.covariates, dtype=float),
            state.metadata,
        )
    if not isinstance(state, Mapping):
        raise TypeError("state must be HTEObservationalData or a mapping payload")
    outcome = np.asarray(state["outcome"], dtype=float)
    treatment = np.asarray(state["treatment"], dtype=float)
    covariates_raw = state.get("covariates")
    covariates = None if covariates_raw is None else np.asarray(covariates_raw, dtype=float)
    metadata = state.get("metadata", {})
    if outcome.ndim != 1 or treatment.ndim != 1 or outcome.shape[0] != treatment.shape[0]:
        raise ValueError("outcome and treatment must be aligned 1D arrays")
    if covariates is not None:
        if covariates.ndim != 2 or covariates.shape[0] != outcome.shape[0]:
            raise ValueError("covariates must be a 2D matrix aligned with outcome")
    return outcome, treatment, covariates, metadata if isinstance(metadata, Mapping) else {}


def _coerce_vector(mapping: Mapping[str, Any], key: str, n_obs: int) -> np.ndarray:
    arr = np.asarray(mapping[key], dtype=float)
    if arr.ndim == 2 and arr.shape[1] == 1:
        arr = arr[:, 0]
    if arr.ndim != 1 or arr.shape[0] != n_obs:
        raise ValueError(f"{key} must be a length-{n_obs} vector")
    return arr


def _coerce_matrix(mapping: Mapping[str, Any], key: str, n_obs: int) -> np.ndarray:
    arr = np.asarray(mapping[key], dtype=float)
    if arr.ndim != 2 or arr.shape[0] != n_obs:
        raise ValueError(f"{key} must be a matrix with {n_obs} rows")
    return arr


def _coerce_proxy_matrix(mapping: Mapping[str, Any], key: str, n_obs: int) -> np.ndarray:
    arr = np.asarray(mapping[key], dtype=float)
    if arr.ndim == 1:
        arr = arr[:, None]
    if arr.ndim != 2 or arr.shape[0] != n_obs:
        raise ValueError(f"{key} must be a vector or matrix with {n_obs} rows")
    return arr


def _coerce_square_matrix(mapping: Mapping[str, Any], key: str, n_obs: int) -> np.ndarray:
    arr = np.asarray(mapping[key], dtype=float)
    if arr.ndim != 2 or arr.shape != (n_obs, n_obs):
        raise ValueError(f"{key} must be a square {n_obs}x{n_obs} matrix")
    return arr


def _validate_binary_treatment(treatment: np.ndarray) -> None:
    if not np.isin(treatment, [0.0, 1.0]).all():
        raise ValueError("treatment must be binary (0/1)")


def _row_normalize_weights(weights: np.ndarray) -> np.ndarray:
    matrix = np.asarray(weights, dtype=float)
    normalized = matrix.copy()
    np.fill_diagonal(normalized, 0.0)
    row_sums = np.sum(normalized, axis=1, keepdims=True)
    row_sums[row_sums == 0.0] = 1.0
    return normalized / row_sums


def _spectral_radius(weights: np.ndarray) -> float:
    matrix = np.asarray(weights, dtype=float)
    if matrix.size == 0:
        return 1.0
    try:
        eigenvalues = np.linalg.eigvals(matrix)
        radius = float(np.max(np.abs(eigenvalues)))
        return radius if np.isfinite(radius) and radius > 1.0e-8 else 1.0
    except np.linalg.LinAlgError:
        return 1.0


def _moran_i(values: np.ndarray, weights: np.ndarray) -> float:
    y = np.asarray(values, dtype=float).reshape(-1)
    if y.size < 3:
        return 0.0
    w = _row_normalize_weights(weights)
    centered = y - float(np.mean(y))
    denom = float(centered @ centered)
    if denom <= 1.0e-12:
        return 0.0
    w_sum = float(np.sum(w))
    if w_sum <= 1.0e-12:
        return 0.0
    return float((y.shape[0] / w_sum) * ((centered @ w @ centered) / denom))


def _normal_interval(
    point_estimate: float,
    scale: float,
    n_obs: int,
    confidence_level: float,
) -> tuple[float, float]:
    if n_obs <= 1 or not np.isfinite(scale) or scale <= 1.0e-12:
        return (float(point_estimate), float(point_estimate))
    z_value = float(NormalDist().inv_cdf(0.5 + 0.5 * confidence_level))
    half_width = z_value * float(scale) / float(np.sqrt(n_obs))
    return (float(point_estimate - half_width), float(point_estimate + half_width))


def _weighted_least_squares(
    design: np.ndarray,
    target: np.ndarray,
    sample_weight: np.ndarray | None = None,
    ridge: float = 1.0e-6,
) -> np.ndarray:
    x = np.asarray(design, dtype=float)
    y = np.asarray(target, dtype=float)
    if sample_weight is not None:
        w = np.sqrt(np.clip(np.asarray(sample_weight, dtype=float), 1.0e-12, None))
        x = x * w[:, None]
        y = y * w
    gram = x.T @ x + ridge * np.eye(x.shape[1])
    rhs = x.T @ y
    return np.linalg.solve(gram, rhs)


def _bootstrap_effect_interval(
    effect_fn: Any,
    *,
    n_obs: int,
    n_bootstrap: int,
    seed: int,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    estimates = np.empty(n_bootstrap, dtype=float)
    for idx in range(n_bootstrap):
        sample = rng.integers(0, n_obs, size=n_obs)
        estimates[idx] = float(effect_fn(sample))
    return bootstrap_ci(estimates)


def _to_json_safe(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if is_dataclass(value):
        return {name: _to_json_safe(getattr(value, name)) for name in value.__dataclass_fields__}
    if isinstance(value, Mapping):
        return {str(key): _to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(item) for item in value]
    return value


def _serialize_distributional_result(result: Any) -> dict[str, Any]:
    payload = _to_json_safe(result)
    quantile_shift = payload.get("quantile_shift")
    if isinstance(quantile_shift, Mapping):
        quantiles = list(quantile_shift.get("quantiles", []))
        baseline_values = list(quantile_shift.get("baseline_values", []))
        counterfactual_values = list(quantile_shift.get("counterfactual_values", []))
        shifts = list(quantile_shift.get("shifts", []))
        quantile_shift = dict(quantile_shift)
        quantile_shift["entries"] = [
            {
                "quantile": float(q),
                "baseline_value": float(b),
                "counterfactual_value": float(c),
                "shift": float(s),
            }
            for q, b, c, s in zip(quantiles, baseline_values, counterfactual_values, shifts, strict=False)
        ]
        payload["quantile_shift"] = quantile_shift
    tail_risk = payload.get("tail_risk")
    if isinstance(tail_risk, Mapping):
        tail_probs = list(tail_risk.get("tail_probs", []))
        thresholds = list(tail_risk.get("thresholds", []))
        baseline_exceedance = list(tail_risk.get("baseline_exceedance_probs", []))
        counterfactual_exceedance = list(tail_risk.get("counterfactual_exceedance_probs", []))
        exceedance_deltas = list(tail_risk.get("exceedance_deltas", []))
        baseline_shortfall = list(tail_risk.get("baseline_expected_shortfalls", []))
        counterfactual_shortfall = list(tail_risk.get("counterfactual_expected_shortfalls", []))
        shortfall_deltas = list(tail_risk.get("expected_shortfall_deltas", []))
        tail_risk = dict(tail_risk)
        tail_risk["entries"] = [
            {
                "tail_probability": float(p),
                "threshold": float(t),
                "baseline_exceedance_prob": float(bx),
                "counterfactual_exceedance_prob": float(cx),
                "exceedance_delta": float(dx),
                "baseline_expected_shortfall": float(bs),
                "counterfactual_expected_shortfall": float(cs),
                "expected_shortfall_delta": float(ds),
            }
            for p, t, bx, cx, dx, bs, cs, ds in zip(
                tail_probs,
                thresholds,
                baseline_exceedance,
                counterfactual_exceedance,
                exceedance_deltas,
                baseline_shortfall,
                counterfactual_shortfall,
                shortfall_deltas,
                strict=False,
            )
        ]
        payload["tail_risk"] = tail_risk
    return payload


def _safe_correlation(left: np.ndarray, right: np.ndarray) -> float:
    lhs = np.asarray(left, dtype=float).reshape(-1)
    rhs = np.asarray(right, dtype=float).reshape(-1)
    if lhs.shape[0] != rhs.shape[0]:
        return 0.0
    mask = np.isfinite(lhs) & np.isfinite(rhs)
    if int(np.sum(mask)) < 3:
        return 0.0
    lhs = lhs[mask]
    rhs = rhs[mask]
    if float(np.std(lhs)) <= 1.0e-12 or float(np.std(rhs)) <= 1.0e-12:
        return 0.0
    return float(np.clip(np.corrcoef(lhs, rhs)[0, 1], -1.0, 1.0))


def _standardized_columns(matrix: np.ndarray) -> np.ndarray:
    arr = np.asarray(matrix, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    means = np.mean(arr, axis=0)
    stds = np.std(arr, axis=0)
    return (arr - means) / np.where(stds > 1.0e-12, stds, 1.0)


def _baseline_design(treatment: np.ndarray, covariates: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(treatment.shape[0]), treatment, covariates])


def _residualize_on_baseline(
    values: np.ndarray,
    baseline: np.ndarray,
    *,
    ridge: float,
) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 1:
        coef = _weighted_least_squares(baseline, arr, ridge=ridge)
        return arr - baseline @ coef
    residuals = np.empty_like(arr, dtype=float)
    for col in range(arr.shape[1]):
        coef = _weighted_least_squares(baseline, arr[:, col], ridge=ridge)
        residuals[:, col] = arr[:, col] - baseline @ coef
    return residuals


def _proxy_sieve_basis(proxy: np.ndarray, *, max_degree: int = 3) -> np.ndarray:
    arr = np.asarray(proxy, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    columns: list[np.ndarray] = []
    for col in range(arr.shape[1]):
        centered = arr[:, col] - float(np.mean(arr[:, col]))
        columns.extend(centered ** degree for degree in range(1, max_degree + 1))
    return _standardized_columns(np.column_stack(columns))


def _bridge_operator_diagnostics(
    *,
    treatment: np.ndarray,
    covariates: np.ndarray,
    treatment_proxy: np.ndarray,
    outcome_proxy: np.ndarray,
    ridge: float,
    max_degree: int = 3,
) -> tuple[float, float, float, float]:
    """Approximate proxy-operator completeness with residualized sieve SVD."""

    baseline = _baseline_design(treatment, covariates)
    z_residual = _residualize_on_baseline(treatment_proxy, baseline, ridge=ridge)
    w_residual = _residualize_on_baseline(outcome_proxy, baseline, ridge=ridge)
    proxy_association = abs(_safe_correlation(z_residual, w_residual))

    z_basis = _residualize_on_baseline(
        _proxy_sieve_basis(treatment_proxy, max_degree=max_degree),
        baseline,
        ridge=ridge,
    )
    w_basis = _residualize_on_baseline(
        _proxy_sieve_basis(outcome_proxy, max_degree=max_degree),
        baseline,
        ridge=ridge,
    )
    z_basis = _standardized_columns(z_basis)
    w_basis = _standardized_columns(w_basis)
    if z_basis.shape[0] == 0 or w_basis.shape[0] == 0:
        return 0.0, 0.0, float("inf"), proxy_association

    cross_operator = z_basis.T @ w_basis / max(1, int(z_basis.shape[0]))
    singular_values = np.linalg.svd(cross_operator, compute_uv=False)
    finite_values = singular_values[np.isfinite(singular_values)]
    if finite_values.size == 0:
        return 0.0, 0.0, float("inf"), proxy_association
    max_sigma = float(np.max(finite_values))
    threshold = max(1.0e-4, 1.0e-3 * max_sigma)
    effective_rank = float(np.sum(finite_values > threshold))
    positive = finite_values[finite_values > threshold]
    sigma_min = float(np.min(positive)) if positive.size else 0.0
    ill_posedness = (
        float(max_sigma / sigma_min)
        if sigma_min > 1.0e-12
        else float("inf")
    )
    return effective_rank, sigma_min, ill_posedness, proxy_association


def _bridge_equation_residual(
    *,
    outcome: np.ndarray,
    treatment: np.ndarray,
    covariates: np.ndarray,
    treatment_proxy: np.ndarray,
    outcome_proxy: np.ndarray,
    ridge: float,
    seed: int,
) -> float:
    """Out-of-sample normalized residual for E[Y|Z,A,X] = E[h(W,A,X)|Z,A,X]."""

    n_obs = outcome.shape[0]
    rng = np.random.default_rng(seed)
    order = rng.permutation(n_obs)
    test_size = max(15, round(0.25 * n_obs))
    test_idx = order[:test_size]
    train_idx = order[test_size:]
    if train_idx.size < max(20, covariates.shape[1] + 6):
        train_idx = order
        test_idx = order

    train_x = covariates[train_idx]
    test_x = covariates[test_idx]
    m_train = np.column_stack(
        [
            np.ones(train_idx.size),
            treatment[train_idx],
            train_x,
            treatment_proxy[train_idx],
        ]
    )
    m_test = np.column_stack(
        [
            np.ones(test_idx.size),
            treatment[test_idx],
            test_x,
            treatment_proxy[test_idx],
        ]
    )
    m_coef = _weighted_least_squares(m_train, outcome[train_idx], ridge=ridge)
    m_pred = m_test @ m_coef

    proxy_train = m_train
    proxy_test = m_test
    proxy_coef = _weighted_least_squares(proxy_train, outcome_proxy[train_idx], ridge=ridge)
    expected_w = proxy_test @ proxy_coef

    bridge_train = np.column_stack(
        [
            np.ones(train_idx.size),
            treatment[train_idx],
            train_x,
            outcome_proxy[train_idx],
        ]
    )
    bridge_coef = _weighted_least_squares(bridge_train, outcome[train_idx], ridge=ridge)
    bridge_test = np.column_stack(
        [
            np.ones(test_idx.size),
            treatment[test_idx],
            test_x,
            expected_w,
        ]
    )
    bridge_pred = bridge_test @ bridge_coef

    residual = float(np.mean((m_pred - bridge_pred) ** 2))
    scale = float(np.var(m_pred))
    if scale <= 1.0e-12:
        scale = float(np.var(outcome[test_idx]))
    if scale <= 1.0e-12:
        scale = 1.0
    return max(0.0, residual / scale)


def _bridge_residual_interval(
    *,
    outcome: np.ndarray,
    treatment: np.ndarray,
    covariates: np.ndarray,
    treatment_proxy: np.ndarray,
    outcome_proxy: np.ndarray,
    ridge: float,
    seed: int,
    n_splits: int,
) -> tuple[float, tuple[float, float]]:
    residuals = np.array(
        [
            _bridge_equation_residual(
                outcome=outcome,
                treatment=treatment,
                covariates=covariates,
                treatment_proxy=treatment_proxy,
                outcome_proxy=outcome_proxy,
                ridge=ridge,
                seed=seed + 7919 * split,
            )
            for split in range(max(3, n_splits))
        ],
        dtype=float,
    )
    residuals = residuals[np.isfinite(residuals)]
    if residuals.size == 0:
        return 1.0e12, (1.0e12, 1.0e12)
    center = float(np.median(residuals))
    lower, upper = np.percentile(residuals, [5.0, 95.0])
    return center, (float(lower), float(upper))


def _build_bridge_plausibility_report(
    *,
    outcome: np.ndarray,
    treatment: np.ndarray,
    covariates: np.ndarray,
    treatment_proxy: np.ndarray,
    outcome_proxy: np.ndarray,
    ridge: float,
    seed: int,
    n_residual_splits: int = 12,
    max_degree: int = 3,
) -> BridgePlausibilityReport:
    residual_r, residual_interval = _bridge_residual_interval(
        outcome=outcome,
        treatment=treatment,
        covariates=covariates,
        treatment_proxy=treatment_proxy,
        outcome_proxy=outcome_proxy,
        ridge=ridge,
        seed=seed,
        n_splits=n_residual_splits,
    )
    effective_rank, sigma_min, ill_posedness, proxy_association = _bridge_operator_diagnostics(
        treatment=treatment,
        covariates=covariates,
        treatment_proxy=treatment_proxy,
        outcome_proxy=outcome_proxy,
        ridge=ridge,
        max_degree=max_degree,
    )

    severity = BridgePlausibilitySeverity.GREEN
    failure_mode = BridgeFailureMode.NONE
    bridge_supported = True
    completeness_plausible = True
    reasons: list[str] = []

    if not np.isfinite(residual_r) or residual_r >= 0.75:
        severity = BridgePlausibilitySeverity.RED
        failure_mode = BridgeFailureMode.INFEASIBLE_EQUATION
        bridge_supported = False
        reasons.append("bridge_equation_residual_large")
    elif residual_r >= 0.35:
        severity = BridgePlausibilitySeverity.YELLOW
        failure_mode = BridgeFailureMode.ILL_POSED
        reasons.append("bridge_equation_residual_elevated")

    if proxy_association < 0.03 or effective_rank < 1.0:
        severity = BridgePlausibilitySeverity.RED
        if failure_mode is BridgeFailureMode.NONE:
            failure_mode = BridgeFailureMode.WEAK_COMPLETENESS
        completeness_plausible = False
        reasons.append("proxy_association_or_effective_rank_too_low")
    elif proxy_association < 0.10 or effective_rank < 2.0:
        if severity is BridgePlausibilitySeverity.GREEN:
            severity = BridgePlausibilitySeverity.YELLOW
        if failure_mode is BridgeFailureMode.NONE:
            failure_mode = BridgeFailureMode.WEAK_COMPLETENESS
        completeness_plausible = False
        reasons.append("proxy_association_or_effective_rank_weak")

    if not np.isfinite(ill_posedness) or ill_posedness >= 1000.0 or sigma_min < 1.0e-6:
        if severity is BridgePlausibilitySeverity.GREEN:
            severity = BridgePlausibilitySeverity.YELLOW
        if failure_mode is BridgeFailureMode.NONE:
            failure_mode = BridgeFailureMode.ILL_POSED
        reasons.append("bridge_operator_ill_posed")
    elif ill_posedness >= 100.0 or sigma_min < 1.0e-3:
        if severity is BridgePlausibilitySeverity.GREEN:
            severity = BridgePlausibilitySeverity.YELLOW
        if failure_mode is BridgeFailureMode.NONE:
            failure_mode = BridgeFailureMode.ILL_POSED
        reasons.append("bridge_operator_nearly_singular")

    if failure_mode is BridgeFailureMode.NONE:
        reasons.append("bridge_equation_residual_and_proxy_operator_passed")

    return BridgePlausibilityReport(
        equation_type="outcome_bridge",
        residual_r=float(residual_r),
        residual_interval=residual_interval,
        effective_rank=float(effective_rank),
        sigma_min=float(sigma_min),
        ill_posedness_index=(
            float(ill_posedness) if np.isfinite(ill_posedness) else None
        ),
        proxy_association_score=float(proxy_association),
        bridge_existence_supported=bridge_supported,
        completeness_plausible=completeness_plausible,
        functional_invariant_to_nonuniqueness=True,
        suspected_failure_mode=failure_mode,
        severity=severity,
        reasons=tuple(reasons),
        recommended_bounds_methods=(
            "manski_bounds",
            "sensitivity_bounds",
            "iv_bounds_if_available",
        ),
        recommended_rescue_actions=(
            "add_an_independent_outcome_proxy",
            "add_an_independent_treatment_proxy",
            "expand_proxy_support_before_estimating_proximal_effects",
        ),
        metadata={
            "diagnostic_basis": "residualized_polynomial_sieve_svd",
            "residual_scale": "out_of_sample_conditional_mean_variance",
            "residual_splits": int(max(3, n_residual_splits)),
            "sieve_degree": int(max_degree),
        },
    )


def _bridge_diagnostic_tests(report: BridgePlausibilityReport) -> list[DiagnosticTest]:
    summary = report.to_summary_dict()
    return [
        DiagnosticTest(
            test_name="proximal_bridge_equation_residual",
            statistic=report.residual_r,
            passed=report.bridge_existence_supported is not False,
            details=summary,
        ),
        DiagnosticTest(
            test_name="proximal_proxy_association",
            statistic=report.proxy_association_score,
            passed=(
                report.proxy_association_score is not None
                and report.proxy_association_score >= 0.03
            ),
            details=summary,
        ),
        DiagnosticTest(
            test_name="proximal_operator_effective_rank",
            statistic=report.effective_rank,
            passed=report.completeness_plausible is not False,
            details=summary,
        ),
    ]


def _proximal_manski_fallback(
    *,
    outcome: np.ndarray,
    treatment: np.ndarray,
) -> PartialIdentificationResult:
    y = np.asarray(outcome, dtype=float).reshape(-1)
    a = np.asarray(treatment, dtype=float).reshape(-1)
    y_min = float(np.min(y))
    y_max = float(np.max(y))
    if not np.isfinite(y_min) or not np.isfinite(y_max) or abs(y_max - y_min) <= 1.0e-12:
        y_min, y_max = -1.0, 1.0
    treated = y[a == 1.0]
    control = y[a == 0.0]
    if treated.size == 0 or control.size == 0:
        span = max(float(y_max - y_min), 1.0)
        return PartialIdentificationResult(
            method=BoundMethod.MANSKI,
            lower_bound=-span,
            upper_bound=span,
            confidence=0.0,
            assumptions_used=["bounded_outcome_support", "proximal_bridge_diagnostic_failed"],
            bounds_type="manski",
            display_label="Worst-case proximal fallback bounds",
        )

    result = compute_manski_bounds(
        outcome_conditioned=np.array([np.mean(control), np.mean(treated)], dtype=float),
        treatment_probs=np.array([np.mean(a == 0.0), np.mean(a == 1.0)], dtype=float),
        outcome_support=(y_min, y_max),
    )
    return result.model_copy(
        update={
            "assumptions_used": [
                *result.assumptions_used,
                "bounded_outcome_support",
                "proximal_bridge_diagnostic_failed",
            ],
            "display_label": "Manski fallback after proximal bridge diagnostic",
        }
    )


def _epsilon_relaxed_spatial_bounds(
    *,
    point_estimate: float,
    outcome_scale: float,
    bridge_report: BridgePlausibilityReport,
    estimand_label: str,
    epsilon: float | None = None,
) -> PartialIdentificationResult:
    residual_upper = (
        float(bridge_report.residual_interval[1])
        if bridge_report.residual_interval is not None
        else float(bridge_report.residual_r or 0.0)
    )
    instability = float(bridge_report.ring_sensitivity_instability or 0.0)
    moran_penalty = abs(float(bridge_report.moran_i_bridge_residual or 0.0))
    epsilon_value = max(0.0, float(epsilon or 0.0))
    width = max(
        0.05 * abs(point_estimate),
        outcome_scale
        * (residual_upper + epsilon_value + 0.5 * instability + 0.25 * moran_penalty),
        1.0e-3,
    )
    return PartialIdentificationResult(
        method=BoundMethod.INTERSECTION_BOUNDS,
        lower_bound=float(point_estimate - width),
        upper_bound=float(point_estimate + width),
        confidence=0.0,
        assumptions_used=[
            "epsilon_relaxed_spatial_bridge_moments",
            "relaxed_buffered_spatial_proxy_exclusion",
        ],
        bounds_type="relaxed_polynomial",
        relaxation_gap=float(width),
        display_label=f"Epsilon-relaxed proximal spatial bounds ({estimand_label})",
        solver_metadata={
            "residual_upper": residual_upper,
            "epsilon": epsilon_value,
            "ring_sensitivity_instability": instability,
            "moran_i_bridge_residual": moran_penalty,
        },
    )


def _resolve_epsilon_grid(raw_value: Any) -> tuple[float, ...]:
    if raw_value is None:
        return (0.01, 0.025, 0.05)
    if isinstance(raw_value, (int, float)):
        value = max(0.0, float(raw_value))
        return (value,)
    values: list[float] = []
    for item in raw_value:
        try:
            value = float(item)
        except Exception:
            continue
        if value >= 0.0:
            values.append(value)
    if not values:
        return (0.01, 0.025, 0.05)
    return tuple(sorted(set(values)))


def _spatial_sensitivity_grid(
    *,
    point_estimate: float,
    outcome_scale: float,
    bridge_report: BridgePlausibilityReport,
    epsilon_grid: tuple[float, ...],
    estimand_label: str,
) -> list[dict[str, float]]:
    entries: list[dict[str, float]] = []
    for epsilon in epsilon_grid:
        bounds = _epsilon_relaxed_spatial_bounds(
            point_estimate=point_estimate,
            outcome_scale=outcome_scale,
            bridge_report=bridge_report,
            estimand_label=estimand_label,
            epsilon=epsilon,
        )
        entries.append(
            {
                "epsilon": float(epsilon),
                "lower_bound": float(bounds.lower_bound),
                "upper_bound": float(bounds.upper_bound),
                "width": float(bounds.bound_width),
            }
        )
    return entries


def _fit_spatial_proximal_linear(
    *,
    outcome: np.ndarray,
    treatment: np.ndarray,
    covariates: np.ndarray,
    weight_matrix: np.ndarray,
    treatment_proxy: np.ndarray,
    outcome_proxy: np.ndarray,
    ridge: float,
    stability_constraint_margin: float,
    model_family: str,
    spatial_lag_covariates: np.ndarray | None = None,
    spatial_lag_treatment: np.ndarray | None = None,
    weight_matrix_error: np.ndarray | None = None,
) -> dict[str, Any]:
    n_obs = outcome.shape[0]
    x = np.asarray(covariates, dtype=float)
    z = np.asarray(treatment_proxy, dtype=float)
    if z.ndim == 1:
        z = z[:, None]
    w_proxy = np.asarray(outcome_proxy, dtype=float)
    if w_proxy.ndim == 1:
        w_proxy = w_proxy[:, None]

    weight_matrix = _row_normalize_weights(weight_matrix)
    wa = (
        np.asarray(spatial_lag_treatment, dtype=float).reshape(-1)
        if spatial_lag_treatment is not None
        else weight_matrix @ treatment
    )
    wx = (
        np.asarray(spatial_lag_covariates, dtype=float)
        if spatial_lag_covariates is not None
        else weight_matrix @ x
    )
    if wx.ndim == 1:
        wx = wx[:, None]
    wy = weight_matrix @ outcome

    proxy_design = np.column_stack([np.ones(n_obs), treatment, wa, x, wx, z])
    proxy_coef = _weighted_least_squares(proxy_design, w_proxy, ridge=ridge)
    bridge_design = np.column_stack([np.ones(n_obs), wy, treatment, wa, x, wx, w_proxy])
    bridge_coef = _weighted_least_squares(bridge_design, outcome, ridge=ridge)

    p = x.shape[1]
    q = wx.shape[1]
    intercept = float(bridge_coef[0])
    raw_rho = float(bridge_coef[1])
    tau = float(bridge_coef[2])
    vartheta = float(bridge_coef[3])
    beta = np.asarray(bridge_coef[4 : 4 + p], dtype=float)
    gamma = np.asarray(bridge_coef[4 + p : 4 + p + q], dtype=float)
    bridge_proxy_coef = np.asarray(bridge_coef[4 + p + q :], dtype=float)

    spectral_radius = _spectral_radius(weight_matrix)
    max_abs_rho = max(1.0e-6, (1.0 - stability_constraint_margin) / spectral_radius)
    rho = float(np.clip(raw_rho, -max_abs_rho, max_abs_rho))

    structural_fitted = (
        intercept
        + rho * wy
        + tau * treatment
        + vartheta * wa
        + x @ beta
        + wx @ gamma
        + w_proxy @ bridge_proxy_coef
    )
    residual = np.asarray(outcome - structural_fitted, dtype=float)

    lambda_hat = 0.0
    if model_family == "sarar":
        weight_matrix_error = (
            weight_matrix
            if weight_matrix_error is None
            else _row_normalize_weights(weight_matrix_error)
        )
        error_radius = _spectral_radius(weight_matrix_error)
        max_abs_lambda = max(1.0e-6, (1.0 - stability_constraint_margin) / error_radius)
        raw_lambda = _safe_correlation(residual, weight_matrix_error @ residual)
        lambda_hat = float(np.clip(raw_lambda, -max_abs_lambda, max_abs_lambda))
        residual = residual - lambda_hat * (weight_matrix_error @ residual)

    impact_matrix = np.linalg.solve(
        np.eye(n_obs) - rho * weight_matrix,
        tau * np.eye(n_obs) + vartheta * weight_matrix,
    )
    ade = float(np.trace(impact_matrix) / n_obs)
    indirect_matrix = impact_matrix - np.diag(np.diag(impact_matrix))
    aie = float(np.sum(indirect_matrix) / n_obs)
    ate_total = float(ade + aie)
    unit_total_effect = np.sum(impact_matrix, axis=1)
    confidence_interval = _normal_interval(
        ate_total,
        float(np.std(unit_total_effect, ddof=1)) if n_obs > 1 else 0.0,
        n_obs,
        0.95,
    )
    denom = float(np.sum((outcome - np.mean(outcome)) ** 2))
    bridge_r2 = (
        1.0 - float(np.sum((outcome - structural_fitted) ** 2)) / denom
        if denom > 1.0e-12
        else 0.0
    )

    return {
        "rho": rho,
        "raw_rho": raw_rho,
        "tau": tau,
        "vartheta": vartheta,
        "beta": beta,
        "gamma": gamma,
        "lambda": lambda_hat,
        "bridge_proxy_coef": bridge_proxy_coef,
        "bridge_coef": bridge_coef,
        "proxy_coef": proxy_coef,
        "wa": wa,
        "wx": wx,
        "wy": wy,
        "residual": residual,
        "bridge_r_squared": float(bridge_r2),
        "impact_matrix": impact_matrix,
        "ade": ade,
        "aie": aie,
        "ate_total": ate_total,
        "unit_total_effect": unit_total_effect,
        "confidence_interval": confidence_interval,
        "spectral_radius": spectral_radius,
        "stability_clipped": bool(abs(raw_rho - rho) > 1.0e-10),
    }


def _proxy_ring_instability(
    *,
    outcome: np.ndarray,
    treatment: np.ndarray,
    covariates: np.ndarray,
    weight_matrix: np.ndarray,
    treatment_proxy: np.ndarray,
    outcome_proxy: np.ndarray,
    ridge: float,
    stability_constraint_margin: float,
    model_family: str,
    spatial_lag_covariates: np.ndarray | None = None,
    spatial_lag_treatment: np.ndarray | None = None,
    weight_matrix_error: np.ndarray | None = None,
) -> float:
    z = np.asarray(treatment_proxy, dtype=float)
    if z.ndim == 1:
        z = z[:, None]
    w_proxy = np.asarray(outcome_proxy, dtype=float)
    if w_proxy.ndim == 1:
        w_proxy = w_proxy[:, None]
    n_pairs = min(z.shape[1], w_proxy.shape[1])
    if n_pairs <= 1:
        return 0.0
    effects = []
    for idx in range(n_pairs):
        fitted = _fit_spatial_proximal_linear(
            outcome=outcome,
            treatment=treatment,
            covariates=covariates,
            weight_matrix=weight_matrix,
            treatment_proxy=z[:, [idx]],
            outcome_proxy=w_proxy[:, [idx]],
            ridge=ridge,
            stability_constraint_margin=stability_constraint_margin,
            model_family=model_family,
            spatial_lag_covariates=spatial_lag_covariates,
            spatial_lag_treatment=spatial_lag_treatment,
            weight_matrix_error=weight_matrix_error,
        )
        effects.append(float(fitted["ate_total"]))
    spread = float(np.std(np.asarray(effects, dtype=float), ddof=1))
    scale = max(abs(float(np.mean(effects))), 1.0e-6)
    return float(spread / scale)


def _buffer_exclusion_falsification(spatial_proxy_specs: tuple[Mapping[str, Any], ...]) -> bool | None:
    if not spatial_proxy_specs:
        return None
    for raw_spec in spatial_proxy_specs:
        roles = {str(item) for item in raw_spec.get("allowed_roles", ())}
        if "outcome_inducing" not in roles:
            continue
        time_mode = str(raw_spec.get("time_mode", "contemporaneous"))
        if time_mode != "contemporaneous":
            continue
        lag_orders = tuple(int(item) for item in raw_spec.get("lag_orders", ()))
        if not lag_orders:
            continue
        min_lag = min(lag_orders)
        buffer_radius = int(raw_spec.get("buffer_radius") or 0)
        spillover_radius = int(raw_spec.get("spillover_radius_claim") or 1)
        proxy_construction = str(raw_spec.get("proxy_construction", "ring_lag"))
        if proxy_construction in {"ring_lag", "buffered_ring_lag"} and max(
            min_lag, buffer_radius
        ) <= spillover_radius:
            return True
    return False


def _build_spatial_bridge_plausibility_report(
    *,
    base_report: BridgePlausibilityReport,
    residual: np.ndarray,
    weight_matrix: np.ndarray,
    spatial_proxy_specs: tuple[Mapping[str, Any], ...],
    ring_sensitivity_instability: float,
) -> BridgePlausibilityReport:
    severity = base_report.severity
    failure_mode = base_report.suspected_failure_mode
    bridge_supported = base_report.bridge_existence_supported
    completeness_plausible = base_report.completeness_plausible
    reasons = list(base_report.reasons)

    buffer_falsification = _buffer_exclusion_falsification(spatial_proxy_specs)
    moran_i_bridge_residual = _moran_i(residual, weight_matrix)

    if buffer_falsification is True:
        severity = BridgePlausibilitySeverity.RED
        failure_mode = BridgeFailureMode.INFEASIBLE_EQUATION
        bridge_supported = False
        if "buffer_exclusion_falsification" not in reasons:
            reasons.append("buffer_exclusion_falsification")

    if ring_sensitivity_instability >= 0.40:
        if severity is BridgePlausibilitySeverity.GREEN:
            severity = BridgePlausibilitySeverity.YELLOW
        if failure_mode is BridgeFailureMode.NONE:
            failure_mode = BridgeFailureMode.ILL_POSED
        completeness_plausible = False
        reasons.append("proxy_ring_sensitivity_instability_high")

    if abs(moran_i_bridge_residual) >= 0.45:
        severity = BridgePlausibilitySeverity.RED
        if failure_mode is BridgeFailureMode.NONE:
            failure_mode = BridgeFailureMode.INFEASIBLE_EQUATION
        bridge_supported = False
        reasons.append("bridge_residual_spatial_autocorrelation_high")
    elif abs(moran_i_bridge_residual) >= 0.20:
        if severity is BridgePlausibilitySeverity.GREEN:
            severity = BridgePlausibilitySeverity.YELLOW
        if failure_mode is BridgeFailureMode.NONE:
            failure_mode = BridgeFailureMode.ILL_POSED
        reasons.append("bridge_residual_spatial_autocorrelation_elevated")

    payload = base_report.model_dump(mode="python")
    payload.update(
        {
            "buffer_exclusion_falsification": buffer_falsification,
            "ring_sensitivity_instability": float(ring_sensitivity_instability),
            "moran_i_bridge_residual": float(moran_i_bridge_residual),
            "bridge_existence_supported": bridge_supported,
            "completeness_plausible": completeness_plausible,
            "suspected_failure_mode": failure_mode,
            "severity": severity,
            "reasons": tuple(reasons),
            "metadata": {
                **base_report.metadata,
                "spatial_proxy_specs_present": bool(spatial_proxy_specs),
                "spatial_diagnostic_basis": "buffered_proxy_checks_plus_moran_i",
            },
            "fallback_disposition": None,
        }
    )
    return BridgePlausibilityReport.model_validate(payload)


@foundry_method(
    namespace="causal.proximal",
    version="1.0.0",
    tags={"causal", "proximal", "negative-controls", "frontier"},
)
class ProximalBridgeEstimator:
    """Approximate proximal bridge estimation with negative-control exposure and outcome proxies."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="proximal_bridge",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
                SlotSpec("covariates", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("treatment_proxy", SlotType.VECTOR, Unit("proxy", "value"), shape=("n_obs",)),
                SlotSpec("outcome_proxy", SlotType.VECTOR, Unit("proxy", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_proximal_bridge_output_slots(),
        parameters=(
            ParameterSpec("n_bootstrap", default=200, bounds=(50, 1000)),
            ParameterSpec("confidence_level", default=0.95, bounds=(0.8, 0.99)),
            ParameterSpec("ridge", default=1.0e-4, bounds=(1.0e-8, None)),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Negative-control proximal bridge estimator for latent-confounding settings with observed proxies.",
        tags=frozenset({"causal", "proximal", "negative-controls", "frontier"}),
        citations=(
            "Tchetgen Tchetgen, E. et al. (2020). Introduction to proximal causal learning.",
            "Miao, W., Geng, Z. & Tchetgen Tchetgen, E. (2018). Identifying causal effects with proxy variables.",
        ),
        equations={
            "proxy_bridge": "E[Y - h(A, X, W) | Z, A, X] = 0",
            "proximal_ate": "ATE = E[h(1, X, W(1)) - h(0, X, W(0))]",
        },
        assumptions={
            "negative_control_exposure": "treatment_proxy carries latent-confounding signal but no direct effect on outcome after conditioning.",
            "negative_control_outcome": "outcome_proxy reflects latent confounding but is not causally affected by treatment except through confounding pathways.",
            "bridge_specification": "linear bridge approximation is adequate for the decision context.",
        },
        when_to_use="Suspected latent confounding with measured proxy variables or negative controls that make standard backdoor adjustment unreliable.",
        when_not_to_use="No credible proxies, severe overlap failure, or settings requiring a fully nonparametric bridge model.",
        diagnostic_checks=("causal.diagnostics.support_mismatch@1.0.0",),
        typical_min_obs=150,
        output_interpretation="point_estimate is the proximal ATE. bridge_r_squared and proxy_strength diagnose how informative the proxies were for latent-confounding adjustment.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any] | HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            outcome, treatment, covariates, _ = _observational_payload(state)
            if covariates is None:
                raise ValueError("covariates are required for proximal bridge estimation")
            mapping = state if isinstance(state, Mapping) else state.model_dump(mode="python")
            n_obs = outcome.shape[0]
            treatment_proxy = _coerce_vector(mapping, "treatment_proxy", n_obs)
            outcome_proxy = _coerce_vector(mapping, "outcome_proxy", n_obs)
            _validate_binary_treatment(treatment)
            if n_obs < 60:
                raise ValueError("proximal bridge estimation requires at least 60 observations")
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.PROXIMAL_BRIDGE,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="proximal_ate",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(ProximalBridgeEstimator.metadata.assumptions),
            )
            return wrap_causal_output(report, warnings=[report.status_reason or "input invalid"], extras={"proximal_result": None})

        ridge = float(params.get("ridge", 1.0e-4))
        seed = int(params.get("__seed__", 0))
        x = np.asarray(covariates, dtype=float)
        z = treatment_proxy[:, None]
        w = outcome_proxy

        proxy_design = np.column_stack([np.ones(n_obs), treatment, x, z[:, 0]])
        proxy_coef = _weighted_least_squares(proxy_design, w, ridge=ridge)

        def _predicted_proxy(a_value: float, indices: np.ndarray | None = None) -> np.ndarray:
            sel = slice(None) if indices is None else indices
            x_sel = x[sel]
            z_sel = z[sel, 0]
            a_vec = np.full(x_sel.shape[0], a_value, dtype=float)
            design = np.column_stack([np.ones(x_sel.shape[0]), a_vec, x_sel, z_sel])
            return design @ proxy_coef

        bridge_design = np.column_stack([np.ones(n_obs), treatment, x, w])
        bridge_coef = _weighted_least_squares(bridge_design, outcome, ridge=ridge)

        def _unit_effect(indices: np.ndarray | None = None) -> np.ndarray:
            sel = slice(None) if indices is None else indices
            x_sel = x[sel]
            y1_proxy = _predicted_proxy(1.0, indices)
            y0_proxy = _predicted_proxy(0.0, indices)
            d1 = np.column_stack([np.ones(x_sel.shape[0]), np.ones(x_sel.shape[0]), x_sel, y1_proxy])
            d0 = np.column_stack([np.ones(x_sel.shape[0]), np.zeros(x_sel.shape[0]), x_sel, y0_proxy])
            return (d1 @ bridge_coef) - (d0 @ bridge_coef)

        effect = _unit_effect()
        point_estimate = float(np.mean(effect))
        confidence_interval = _bootstrap_effect_interval(
            lambda idx: float(np.mean(_unit_effect(idx))),
            n_obs=n_obs,
            n_bootstrap=int(params.get("n_bootstrap", 200)),
            seed=int(params.get("__seed__", 0)),
        )
        bridge_pred = bridge_design @ bridge_coef
        denom = float(np.sum((outcome - np.mean(outcome)) ** 2))
        bridge_r2 = 1.0 - float(np.sum((outcome - bridge_pred) ** 2)) / denom if denom > 1.0e-12 else 0.0
        proxy_strength = float(abs(np.corrcoef(treatment_proxy, outcome_proxy)[0, 1])) if np.std(treatment_proxy) > 1.0e-12 and np.std(outcome_proxy) > 1.0e-12 else 0.0
        bridge_report = _build_bridge_plausibility_report(
            outcome=outcome,
            treatment=treatment,
            covariates=x,
            treatment_proxy=treatment_proxy,
            outcome_proxy=outcome_proxy,
            ridge=ridge,
            seed=seed,
            n_residual_splits=int(params.get("bridge_residual_splits", 12) or 12),
        )
        bridge_report_payload = bridge_report.model_dump(mode="json")
        bridge_diagnostics = _bridge_diagnostic_tests(bridge_report)
        fallback_disposition = bridge_report.fallback_disposition
        if fallback_disposition in {
            BridgeFallbackDisposition.BLOCK_POINT_ESTIMATE,
            BridgeFallbackDisposition.REQUIRE_BOUNDS,
        }:
            partial_bounds = _proximal_manski_fallback(
                outcome=outcome,
                treatment=treatment,
            )
            bounds_bundle = bounds_bundle_from_partial_identification_result(
                partial_bounds,
                estimand_type="ate",
                metadata={"source": "proximal_bridge_plausibility_fallback"},
            )
            bounds_bundle = annotate_bounds_bundle_for_proximal_bridge_failure(
                bounds_bundle,
                bridge_report,
            )
            negative_certificate = negative_certificate_from_bridge_plausibility_report(
                bridge_report,
                estimand_type="ate",
                bounds_bundle=bounds_bundle,
                missing_vars=("additional_treatment_proxy", "additional_outcome_proxy"),
            )
            reason = (
                "proximal_bridge_equation_infeasible"
                if bridge_report.suspected_failure_mode is BridgeFailureMode.INFEASIBLE_EQUATION
                else "proximal_bridge_completeness_or_stability_requires_bounds"
            )
            report = build_failure_report(
                method=CausalMethod.PROXIMAL_BRIDGE,
                status=EstimationStatus.ASSUMPTION_FAILED,
                reason=reason,
                estimand="proximal_ate",
                sample_size=n_obs,
                n_treated=int(np.sum(treatment == 1)),
                n_control=int(np.sum(treatment == 0)),
                pre_periods=0,
                post_periods=0,
                assumptions=dict(ProximalBridgeEstimator.metadata.assumptions),
                diagnostics=bridge_diagnostics,
                metadata={
                    "bridge_r_squared": float(bridge_r2),
                    "proxy_strength": float(proxy_strength),
                    "bridge_plausibility_report": bridge_report_payload,
                    "bridge_plausibility_severity": bridge_report.severity.value,
                    "bridge_failure_mode": bridge_report.suspected_failure_mode.value,
                    "bridge_fallback_disposition": (
                        fallback_disposition.value if fallback_disposition is not None else None
                    ),
                },
            )
            return wrap_causal_output(
                report,
                warnings=list(bounds_bundle.warnings),
                extras={
                    "proximal_result": None,
                    "bridge_plausibility_report": bridge_report_payload,
                    "bounds_bundle": bounds_bundle.model_dump(mode="json"),
                    "negative_certificate": negative_certificate.model_dump(mode="json"),
                },
            )

        report = build_success_report(
            method=CausalMethod.PROXIMAL_BRIDGE,
            estimand="proximal_ate",
            point_estimate=point_estimate,
            confidence_interval=confidence_interval,
            confidence_level=float(params.get("confidence_level", 0.95)),
            inference_method="proximal_bridge",
            sample_size=n_obs,
            n_treated=int(np.sum(treatment == 1)),
            n_control=int(np.sum(treatment == 0)),
            pre_periods=0,
            post_periods=0,
            assumptions=dict(ProximalBridgeEstimator.metadata.assumptions),
            diagnostics=bridge_diagnostics,
            metadata={
                "bridge_r_squared": bridge_r2,
                "proxy_strength": proxy_strength,
                "bridge_plausibility_report": bridge_report_payload,
                "bridge_plausibility_severity": bridge_report.severity.value,
                "bridge_failure_mode": bridge_report.suspected_failure_mode.value,
                "bridge_fallback_disposition": (
                    fallback_disposition.value if fallback_disposition is not None else None
                ),
            },
        )
        proximal_result = {
            "point_estimate": point_estimate,
            "confidence_interval": [float(confidence_interval[0]), float(confidence_interval[1])],
            "bridge_r_squared": float(bridge_r2),
            "proxy_strength": float(proxy_strength),
            "bridge_plausibility_report": bridge_report_payload,
            "bridge_plausibility_severity": bridge_report.severity.value,
            "bridge_failure_mode": bridge_report.suspected_failure_mode.value,
            "bridge_fallback_disposition": (
                fallback_disposition.value if fallback_disposition is not None else None
            ),
            "bridge_coefficients": [float(value) for value in bridge_coef.tolist()],
            "proxy_model_coefficients": [float(value) for value in proxy_coef.tolist()],
            "effect_std": float(np.std(effect, ddof=1)) if effect.shape[0] > 1 else 0.0,
        }
        warnings = (
            ["proximal_bridge_plausibility_warning"]
            if fallback_disposition is BridgeFallbackDisposition.PROCEED_WITH_WARNING
            else []
        )
        return wrap_causal_output(
            report,
            warnings=warnings,
            extras={
                "proximal_result": proximal_result,
                "bridge_plausibility_report": bridge_report_payload,
                "bounds_bundle": None,
                "negative_certificate": None,
            },
        )


@foundry_method(
    namespace="causal.proximal",
    version="1.0.0",
    tags={"causal", "proximal", "spatial", "negative-controls", "frontier"},
)
class SpatialProximalBridgeEstimator:
    """Approximate spatial-proximal bridge estimation for latent spatial confounding."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="spatial_proximal_bridge",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
                SlotSpec("covariates", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec(
                    "weight_matrix",
                    SlotType.MATRIX,
                    Unit("spatial_weight", "value"),
                    shape=("n_obs", "n_obs"),
                ),
                SlotSpec(
                    "treatment_proxy",
                    SlotType.MATRIX,
                    Unit("proxy", "value"),
                    shape=("n_obs", "n_proxy_features"),
                ),
                SlotSpec(
                    "outcome_proxy",
                    SlotType.MATRIX,
                    Unit("proxy", "value"),
                    shape=("n_obs", "n_proxy_features"),
                ),
            }
        ),
        output_slots=_spatial_proximal_bridge_output_slots(),
        parameters=(
            ParameterSpec("model_family", default="sdm"),
            ParameterSpec("sieve_degree", default=3, bounds=(1, 6)),
            ParameterSpec("n_folds", default=4, bounds=(2, 10)),
            ParameterSpec("block_cv_scheme", default="spatial_blocks"),
            ParameterSpec("n_bootstrap", default=80, bounds=(20, 400)),
            ParameterSpec("confidence_level", default=0.95, bounds=(0.8, 0.99)),
            ParameterSpec("ridge", default=1.0e-4, bounds=(1.0e-8, None)),
            ParameterSpec("bridge_residual_splits", default=12, bounds=(3, 50)),
            ParameterSpec("epsilon_grid", default=(0.01, 0.025, 0.05)),
            ParameterSpec("stability_constraint_margin", default=0.025, bounds=(1.0e-4, 0.25)),
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
            "Buffered spatial-proximal bridge estimator for SDM/SARAR-style "
            "settings with latent spatial confounding and proxy ring-lags."
        ),
        tags=frozenset({"causal", "proximal", "spatial", "negative-controls", "frontier"}),
        citations=(
            "Miao, W., Geng, Z. & Tchetgen Tchetgen, E. (2018). Identifying causal effects with proxy variables.",
            "Tchetgen Tchetgen, E. et al. (2020). Introduction to proximal causal learning.",
            "LeSage, J. & Pace, R.K. (2009). Introduction to Spatial Econometrics.",
        ),
        equations={
            "spatial_bridge_moment": "E[s(Z, A, X) {Y - rho WY - tau A - vartheta WA - WX gamma - h(W, A, X)}] = 0",
            "spatial_impacts": "B(rho, tau, vartheta) = (I - rho W)^(-1) (tau I + vartheta W)",
        },
        assumptions={
            "buffered_spatial_proxy_exclusion": "Outcome-inducing spatial proxies are buffered, pre-treatment, or negative-control constructions.",
            "dual_proxy_families": "Both treatment-inducing and outcome-inducing spatial proxy families carry latent-confounding signal.",
            "bridge_stability": "Residualized proxy operator is sufficiently well-conditioned for point estimation.",
        },
        when_to_use=(
            "Latent spatial confounding is plausible and the analyst can supply "
            "spatial weights plus buffered proxy rings."
        ),
        when_not_to_use=(
            "No credible spatial proxies, dense/global spillovers without buffered "
            "exclusion, or no spatial-weights matrix."
        ),
        diagnostic_checks=("spatial.autocorrelation.moran_i@1.0.0",),
        typical_min_obs=120,
        output_interpretation=(
            "point_estimate is the total spatial proximal effect. tau is the "
            "own-unit structural effect; ADE/AIE decompose direct and indirect impacts."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any] | HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            outcome, treatment, covariates, _ = _observational_payload(state)
            if covariates is None:
                raise ValueError("covariates are required for spatial proximal bridge estimation")
            mapping = state if isinstance(state, Mapping) else state.model_dump(mode="python")
            n_obs = outcome.shape[0]
            weight_matrix = _coerce_square_matrix(mapping, "weight_matrix", n_obs)
            treatment_proxy = _coerce_proxy_matrix(mapping, "treatment_proxy", n_obs)
            outcome_proxy = _coerce_proxy_matrix(mapping, "outcome_proxy", n_obs)
            spatial_lag_covariates = None
            if mapping.get("spatial_lag_covariates") is not None:
                spatial_lag_covariates = _coerce_matrix(mapping, "spatial_lag_covariates", n_obs)
            spatial_lag_treatment = None
            if mapping.get("spatial_lag_treatment") is not None:
                spatial_lag_treatment = _coerce_vector(mapping, "spatial_lag_treatment", n_obs)
            weight_matrix_error = None
            if mapping.get("weight_matrix_error") is not None:
                weight_matrix_error = _coerce_square_matrix(mapping, "weight_matrix_error", n_obs)
            _validate_binary_treatment(treatment)
            if n_obs < 80:
                raise ValueError(
                    "spatial proximal bridge estimation requires at least 80 observations"
                )
            model_family = str(params.get("model_family") or mapping.get("model_family") or "sdm").lower()
            if model_family not in {"sdm", "sarar"}:
                raise ValueError("model_family must be one of {'sdm', 'sarar'}")
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.PROXIMAL_BRIDGE,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="spatial_proximal_ate",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(SpatialProximalBridgeEstimator.metadata.assumptions),
            )
            return wrap_causal_output(
                report,
                warnings=[report.status_reason or "input invalid"],
                extras={"spatial_proximal_result": None},
            )

        ridge = float(params.get("ridge", 1.0e-4))
        stability_constraint_margin = float(params.get("stability_constraint_margin", 0.025))
        confidence_level = float(params.get("confidence_level", 0.95))
        n_bootstrap = int(params.get("n_bootstrap", 80) or 80)
        sieve_degree = int(params.get("sieve_degree", 3) or 3)
        n_folds = int(params.get("n_folds", 4) or 4)
        block_cv_scheme = str(params.get("block_cv_scheme", "spatial_blocks") or "spatial_blocks")
        epsilon_grid = _resolve_epsilon_grid(params.get("epsilon_grid"))
        spatial_specs_raw = mapping.get("spatial_proxy_specs") or ()
        spatial_proxy_specs = tuple(
            spec.model_dump(mode="json") if hasattr(spec, "model_dump") else dict(spec)
            for spec in spatial_specs_raw
        )

        fitted = _fit_spatial_proximal_linear(
            outcome=outcome,
            treatment=treatment,
            covariates=np.asarray(covariates, dtype=float),
            weight_matrix=weight_matrix,
            treatment_proxy=treatment_proxy,
            outcome_proxy=outcome_proxy,
            ridge=ridge,
            stability_constraint_margin=stability_constraint_margin,
            model_family=model_family,
            spatial_lag_covariates=spatial_lag_covariates,
            spatial_lag_treatment=spatial_lag_treatment,
            weight_matrix_error=weight_matrix_error,
        )

        diagnostic_covariates = np.column_stack(
            [
                np.asarray(covariates, dtype=float),
                fitted["wa"],
                fitted["wx"],
                fitted["wy"],
            ]
        )
        base_bridge_report = _build_bridge_plausibility_report(
            outcome=outcome,
            treatment=treatment,
            covariates=diagnostic_covariates,
            treatment_proxy=treatment_proxy,
            outcome_proxy=outcome_proxy,
            ridge=ridge,
            seed=int(params.get("__seed__", 0)),
            n_residual_splits=max(
                int(params.get("bridge_residual_splits", 12) or 12),
                n_folds,
            ),
            max_degree=sieve_degree,
        )
        ring_instability = _proxy_ring_instability(
            outcome=outcome,
            treatment=treatment,
            covariates=np.asarray(covariates, dtype=float),
            weight_matrix=weight_matrix,
            treatment_proxy=treatment_proxy,
            outcome_proxy=outcome_proxy,
            ridge=ridge,
            stability_constraint_margin=stability_constraint_margin,
            model_family=model_family,
            spatial_lag_covariates=spatial_lag_covariates,
            spatial_lag_treatment=spatial_lag_treatment,
            weight_matrix_error=weight_matrix_error,
        )
        bridge_report = _build_spatial_bridge_plausibility_report(
            base_report=base_bridge_report,
            residual=fitted["residual"],
            weight_matrix=weight_matrix,
            spatial_proxy_specs=spatial_proxy_specs,
            ring_sensitivity_instability=ring_instability,
        )
        bridge_report_payload = bridge_report.model_dump(mode="json")
        outcome_scale = float(np.std(outcome, ddof=1)) if n_obs > 1 else 1.0
        sensitivity_grid = _spatial_sensitivity_grid(
            point_estimate=float(fitted["ate_total"]),
            outcome_scale=outcome_scale,
            bridge_report=bridge_report,
            epsilon_grid=epsilon_grid,
            estimand_label="ATE_total",
        )
        bridge_diagnostics = [
            *_bridge_diagnostic_tests(bridge_report),
            DiagnosticTest(
                test_name="spatial_bridge_residual_moran_i",
                statistic=bridge_report.moran_i_bridge_residual,
                passed=abs(float(bridge_report.moran_i_bridge_residual or 0.0)) < 0.20,
                details=bridge_report.to_summary_dict(),
            ),
            DiagnosticTest(
                test_name="spatial_proxy_ring_instability",
                statistic=bridge_report.ring_sensitivity_instability,
                passed=float(bridge_report.ring_sensitivity_instability or 0.0) < 0.40,
                details=bridge_report.to_summary_dict(),
            ),
        ]
        fallback_disposition = bridge_report.fallback_disposition

        if fallback_disposition in {
            BridgeFallbackDisposition.BLOCK_POINT_ESTIMATE,
            BridgeFallbackDisposition.REQUIRE_BOUNDS,
        }:
            if bridge_report.buffer_exclusion_falsification is True or (
                bridge_report.proxy_association_score is not None
                and bridge_report.proxy_association_score < 0.03
            ):
                partial_bounds = _proximal_manski_fallback(outcome=outcome, treatment=treatment)
                bounds_source = "spatial_proximal_manski_fallback"
            else:
                partial_bounds = _epsilon_relaxed_spatial_bounds(
                    point_estimate=float(fitted["ate_total"]),
                    outcome_scale=outcome_scale,
                    bridge_report=bridge_report,
                    estimand_label="ATE_total",
                    epsilon=epsilon_grid[0],
                )
                bounds_source = "spatial_proximal_epsilon_relaxed_fallback"
            bounds_bundle = bounds_bundle_from_partial_identification_result(
                partial_bounds,
                estimand_type="ate",
                metadata={
                    "source": bounds_source,
                    "spatial_model_family": model_family,
                    "spatial_proxy_specs_present": bool(spatial_proxy_specs),
                    "epsilon_grid": [float(item) for item in epsilon_grid],
                    "sensitivity_grid": sensitivity_grid,
                    "block_cv_scheme": block_cv_scheme,
                },
            )
            bounds_bundle = annotate_bounds_bundle_for_proximal_bridge_failure(
                bounds_bundle,
                bridge_report,
            )
            negative_certificate = negative_certificate_from_bridge_plausibility_report(
                bridge_report,
                estimand_type="ate",
                bounds_bundle=bounds_bundle,
                missing_vars=("buffered_outcome_proxy", "independent_treatment_proxy"),
            )
            reason = (
                "spatial_buffer_exclusion_failed"
                if bridge_report.buffer_exclusion_falsification is True
                else "spatial_proximal_bridge_requires_bounds"
            )
            report = build_failure_report(
                method=CausalMethod.PROXIMAL_BRIDGE,
                status=EstimationStatus.ASSUMPTION_FAILED,
                reason=reason,
                estimand="spatial_proximal_ate",
                sample_size=n_obs,
                n_treated=int(np.sum(treatment == 1)),
                n_control=int(np.sum(treatment == 0)),
                pre_periods=0,
                post_periods=0,
                assumptions=dict(SpatialProximalBridgeEstimator.metadata.assumptions),
                diagnostics=bridge_diagnostics,
                metadata={
                    "spatial_model_family": model_family,
                    "tau": float(fitted["tau"]),
                    "ade": float(fitted["ade"]),
                    "aie": float(fitted["aie"]),
                    "ate_total": float(fitted["ate_total"]),
                    "rho": float(fitted["rho"]),
                    "lambda": float(fitted["lambda"]),
                    "bridge_plausibility_report": bridge_report_payload,
                    "sensitivity_grid": sensitivity_grid,
                    "block_cv_scheme": block_cv_scheme,
                },
            )
            return wrap_causal_output(
                report,
                warnings=list(bounds_bundle.warnings),
                extras={
                    "spatial_proximal_result": None,
                    "bridge_plausibility_report": bridge_report_payload,
                    "bounds_bundle": bounds_bundle.model_dump(mode="json"),
                    "negative_certificate": negative_certificate.model_dump(mode="json"),
                },
            )

        confidence_interval = _bootstrap_effect_interval(
            lambda idx: float(
                _fit_spatial_proximal_linear(
                    outcome=outcome[idx],
                    treatment=treatment[idx],
                    covariates=np.asarray(covariates, dtype=float)[idx],
                    weight_matrix=weight_matrix[np.ix_(idx, idx)],
                    treatment_proxy=treatment_proxy[idx],
                    outcome_proxy=outcome_proxy[idx],
                    ridge=ridge,
                    stability_constraint_margin=stability_constraint_margin,
                    model_family=model_family,
                    spatial_lag_covariates=(
                        None if spatial_lag_covariates is None else spatial_lag_covariates[idx]
                    ),
                    spatial_lag_treatment=(
                        None if spatial_lag_treatment is None else spatial_lag_treatment[idx]
                    ),
                    weight_matrix_error=(
                        None
                        if weight_matrix_error is None
                        else weight_matrix_error[np.ix_(idx, idx)]
                    ),
                )["ate_total"]
            ),
            n_obs=n_obs,
            n_bootstrap=n_bootstrap,
            seed=int(params.get("__seed__", 0)),
        )
        report = build_success_report(
            method=CausalMethod.PROXIMAL_BRIDGE,
            estimand="spatial_proximal_ate",
            point_estimate=float(fitted["ate_total"]),
            confidence_interval=confidence_interval,
            confidence_level=confidence_level,
            inference_method="spatial_proximal_bridge",
            sample_size=n_obs,
            n_treated=int(np.sum(treatment == 1)),
            n_control=int(np.sum(treatment == 0)),
            pre_periods=0,
            post_periods=0,
            assumptions=dict(SpatialProximalBridgeEstimator.metadata.assumptions),
            diagnostics=bridge_diagnostics,
            metadata={
                "spatial_model_family": model_family,
                "tau": float(fitted["tau"]),
                "ade": float(fitted["ade"]),
                "aie": float(fitted["aie"]),
                "ate_total": float(fitted["ate_total"]),
                "rho": float(fitted["rho"]),
                "lambda": float(fitted["lambda"]),
                "bridge_r_squared": float(fitted["bridge_r_squared"]),
                "bridge_plausibility_report": bridge_report_payload,
                "sensitivity_grid": sensitivity_grid,
                "block_cv_scheme": block_cv_scheme,
                "sieve_degree": sieve_degree,
            },
        )
        spatial_proximal_result = {
            "point_estimate": float(fitted["ate_total"]),
            "confidence_interval": [
                float(confidence_interval[0]),
                float(confidence_interval[1]),
            ],
            "tau": float(fitted["tau"]),
            "ade": float(fitted["ade"]),
            "aie": float(fitted["aie"]),
            "ate_total": float(fitted["ate_total"]),
            "rho": float(fitted["rho"]),
            "lambda": float(fitted["lambda"]),
            "vartheta": float(fitted["vartheta"]),
            "bridge_r_squared": float(fitted["bridge_r_squared"]),
            "proxy_strength": float(bridge_report.proxy_association_score or 0.0),
            "bridge_plausibility_report": bridge_report_payload,
            "bridge_plausibility_severity": bridge_report.severity.value,
            "bridge_failure_mode": bridge_report.suspected_failure_mode.value,
            "bridge_fallback_disposition": (
                fallback_disposition.value if fallback_disposition is not None else None
            ),
            "sensitivity_grid": sensitivity_grid,
            "moran_i_bridge_residual": float(bridge_report.moran_i_bridge_residual or 0.0),
            "ring_sensitivity_instability": float(
                bridge_report.ring_sensitivity_instability or 0.0
            ),
            "buffer_exclusion_falsification": bool(
                bridge_report.buffer_exclusion_falsification
            )
            if bridge_report.buffer_exclusion_falsification is not None
            else None,
            "stability_clipped": bool(fitted["stability_clipped"]),
            "block_cv_scheme": block_cv_scheme,
            "sieve_degree": sieve_degree,
        }
        warnings = (
            ["spatial_proximal_bridge_plausibility_warning"]
            if fallback_disposition is BridgeFallbackDisposition.PROCEED_WITH_WARNING
            else []
        )
        return wrap_causal_output(
            report,
            warnings=warnings,
            extras={
                "spatial_proximal_result": spatial_proximal_result,
                "bridge_plausibility_report": bridge_report_payload,
                "bounds_bundle": None,
                "negative_certificate": None,
            },
        )


@foundry_method(
    namespace="causal.distributional",
    version="1.0.0",
    tags={"causal", "distributional", "qte", "frontier"},
)
class DistributionalTreatmentEffectEstimator:
    """Estimate unconditional quantile and transport-weighted distributional treatment effects."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="unconditional_qte",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
                SlotSpec("covariates", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
            }
        ),
        output_slots=_causal_frontier_output_slots("distributional_result"),
        parameters=(
            ParameterSpec("n_bins", default=48, bounds=(8, 256)),
            ParameterSpec("regularization_strength", default=0.05, bounds=(1.0e-4, None)),
            ParameterSpec("max_iter", default=200, bounds=(10, 2000)),
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
        description="Unconditional quantile treatment effects with covariate-reweighted distributional comparisons.",
        tags=frozenset({"causal", "distributional", "qte", "frontier"}),
        citations=(
            "Firpo, S. (2007). Efficient semiparametric estimation of quantile treatment effects.",
            "Chernozhukov, V., Fernandez-Val, I. & Melly, B. (2013). Inference on counterfactual distributions.",
        ),
        equations={
            "qte": "QTE(q) = F^{-1}_{Y(1)}(q) - F^{-1}_{Y(0)}(q)",
            "wasserstein": "W_1 = integral_0^1 |F^{-1}_{Y(1)}(u) - F^{-1}_{Y(0)}(u)| du",
        },
        assumptions={
            "ignorability": "Treatment assignment is ignorable conditional on observed covariates.",
            "overlap": "Each treatment arm has support across the covariate region used for reweighting.",
        },
        when_to_use="Interest centers on tail effects, median policy impacts, or full distribution shifts rather than only mean treatment effects.",
        when_not_to_use="Tiny treated/control groups, deterministic treatment assignment, or settings requiring structural counterfactual distributions beyond reweighting.",
        diagnostic_checks=("causal.diagnostics.positivity_diagnostic@1.0.0",),
        typical_min_obs=120,
        output_interpretation="report.point_estimate is the mean effect, while distributional_result.quantile_shift and tail_risk summarize who gains or loses across the outcome distribution.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any] | HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            outcome, treatment, covariates, _ = _observational_payload(state)
            if covariates is None:
                raise ValueError("covariates are required for unconditional QTE estimation")
            _validate_binary_treatment(treatment)
            treated_mask = treatment == 1
            control_mask = treatment == 0
            if int(np.sum(treated_mask)) < 20 or int(np.sum(control_mask)) < 20:
                raise ValueError("need at least 20 treated and 20 control observations")
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.DISTRIBUTIONAL_TREATMENT_EFFECT,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="unconditional_qte",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(DistributionalTreatmentEffectEstimator.metadata.assumptions),
            )
            return wrap_causal_output(report, warnings=[report.status_reason or "input invalid"], extras={"distributional_result": None})

        y_treated = outcome[treated_mask]
        y_control = outcome[control_mask]
        x_treated = np.asarray(covariates[treated_mask], dtype=float)
        x_control = np.asarray(covariates[control_mask], dtype=float)

        dist_result = compute_scalar_distributional_effect(
            y_control,
            y_treated,
            baseline_covariates=x_control,
            counterfactual_covariates=x_treated,
            n_bins=int(params.get("n_bins", 48)),
            regularization_strength=float(params.get("regularization_strength", 0.05)),
            max_iter=int(params.get("max_iter", 200)),
        )
        point_estimate = float(np.mean(y_treated) - np.mean(y_control))
        confidence_interval = _bootstrap_effect_interval(
            lambda idx: float(np.mean(y_treated[idx]) - np.mean(y_control[np.minimum(idx, y_control.shape[0] - 1)])),
            n_obs=min(y_treated.shape[0], y_control.shape[0]),
            n_bootstrap=int(params.get("n_bootstrap", 200)),
            seed=int(params.get("__seed__", 0)),
        )

        report = build_success_report(
            method=CausalMethod.DISTRIBUTIONAL_TREATMENT_EFFECT,
            estimand="unconditional_qte",
            point_estimate=point_estimate,
            confidence_interval=confidence_interval,
            confidence_level=float(params.get("confidence_level", 0.95)),
            inference_method="distributional_reweighting",
            sample_size=int(outcome.shape[0]),
            n_treated=int(np.sum(treated_mask)),
            n_control=int(np.sum(control_mask)),
            pre_periods=0,
            post_periods=0,
            assumptions=dict(DistributionalTreatmentEffectEstimator.metadata.assumptions),
            metadata={
                "wasserstein_distance": float(dist_result.wasserstein_distance),
                "weighting_mode": dist_result.weighting_mode,
            },
        )
        return wrap_causal_output(
            report,
            extras={"distributional_result": _serialize_distributional_result(dist_result)},
        )


@foundry_method(
    namespace="causal.interference",
    version="1.0.0",
    tags={"causal", "interference", "hte", "network-aware", "frontier"},
)
class NetworkHeterogeneousEffectEstimator:
    """Estimate heterogeneous direct effects under network exposure using a low-order interaction model."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="network_cate",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
                SlotSpec("covariates", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("adjacency_matrix", SlotType.MATRIX, Unit("network", "adjacency"), shape=("n_obs", "n_obs")),
            }
        ),
        output_slots=_causal_frontier_output_slots("network_hte_result"),
        parameters=(
            ParameterSpec("feature_index", default=0, bounds=(0, None)),
            ParameterSpec("n_groups", default=3, bounds=(2, 8)),
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
        description="Network-aware heterogeneous treatment effect estimator combining direct effects, spillovers, and subgroup heterogeneity.",
        tags=frozenset({"causal", "interference", "hte", "network-aware", "frontier"}),
        citations=(
            "Aronow, P. & Samii, C. (2017). Estimating average causal effects under general interference.",
            "Saveski, M. et al. (2021). Detecting network effects with randomized experiments and observational data.",
        ),
        equations={
            "exposure": "E_i = sum_j G_ij A_j / max(sum_j G_ij, 1)",
            "network_cate": "tau_i = beta_A + beta_AE E_i + beta_AH H_i",
        },
        assumptions={
            "partial_interference_approximation": "spillovers are summarized well by the chosen scalar network exposure mapping.",
            "network_measured": "adjacency_matrix captures the relevant interference topology.",
        },
        when_to_use="Policy impacts depend on peer exposure, network saturation, or heterogeneous responses across observed risk groups.",
        when_not_to_use="Network topology is unknown, treatment interference is strategic in ways not captured by scalar exposure, or groups are too small.",
        typical_min_obs=80,
        output_interpretation="report.point_estimate is the average direct effect after accounting for exposure. network_hte_result.group_effects shows how direct effects vary across heterogeneity groups.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any] | HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            outcome, treatment, covariates, _ = _observational_payload(state)
            if covariates is None:
                raise ValueError("covariates are required for network CATE estimation")
            mapping = state if isinstance(state, Mapping) else state.model_dump(mode="python")
            adjacency = _coerce_matrix(mapping, "adjacency_matrix", outcome.shape[0])
            _validate_binary_treatment(treatment)
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.INTERFERENCE_CATE,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="network_cate",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(NetworkHeterogeneousEffectEstimator.metadata.assumptions),
            )
            return wrap_causal_output(report, warnings=[report.status_reason or "input invalid"], extras={"network_hte_result": None})

        n_obs = outcome.shape[0]
        degree = np.sum(np.clip(adjacency, 0.0, None), axis=1)
        exposure = (adjacency @ treatment) / np.maximum(degree, 1.0)
        feature_index = min(int(params.get("feature_index", 0)), covariates.shape[1] - 1)
        heterogeneity = np.asarray(covariates[:, feature_index], dtype=float)
        propensity = _logistic_propensity(np.asarray(covariates, dtype=float), treatment.astype(float))
        stabilized_weight = treatment / np.clip(propensity, 0.05, 0.95) + (1.0 - treatment) / np.clip(1.0 - propensity, 0.05, 0.95)

        design = np.column_stack(
            [
                np.ones(n_obs),
                treatment,
                exposure,
                heterogeneity,
                treatment * exposure,
                treatment * heterogeneity,
                exposure * heterogeneity,
            ]
        )
        coef = _weighted_least_squares(design, outcome, sample_weight=stabilized_weight)

        def _direct_effect(indices: np.ndarray | None = None) -> np.ndarray:
            sel = slice(None) if indices is None else indices
            exp_sel = exposure[sel]
            het_sel = heterogeneity[sel]
            return coef[1] + coef[4] * exp_sel + coef[5] * het_sel

        direct_effect = _direct_effect()
        point_estimate = float(np.mean(direct_effect))
        confidence_interval = _bootstrap_effect_interval(
            lambda idx: float(np.mean(_direct_effect(idx))),
            n_obs=n_obs,
            n_bootstrap=int(params.get("n_bootstrap", 200)),
            seed=int(params.get("__seed__", 0)),
        )

        n_groups = max(2, int(params.get("n_groups", 3)))
        group_edges = np.quantile(heterogeneity, np.linspace(0.0, 1.0, n_groups + 1))
        group_effects: list[dict[str, Any]] = []
        for group_idx in range(n_groups):
            if group_idx == n_groups - 1:
                mask = (heterogeneity >= group_edges[group_idx]) & (heterogeneity <= group_edges[group_idx + 1])
            else:
                mask = (heterogeneity >= group_edges[group_idx]) & (heterogeneity < group_edges[group_idx + 1])
            if not np.any(mask):
                continue
            group_effects.append(
                {
                    "group_index": group_idx + 1,
                    "feature_interval": [float(group_edges[group_idx]), float(group_edges[group_idx + 1])],
                    "n_obs": int(np.sum(mask)),
                    "direct_effect": float(np.mean(direct_effect[mask])),
                    "spillover_effect": float(np.mean(coef[2] + coef[4] * treatment[mask] + coef[6] * heterogeneity[mask])),
                    "mean_exposure": float(np.mean(exposure[mask])),
                }
            )

        report = build_success_report(
            method=CausalMethod.INTERFERENCE_CATE,
            estimand="network_cate",
            point_estimate=point_estimate,
            confidence_interval=confidence_interval,
            confidence_level=float(params.get("confidence_level", 0.95)),
            inference_method="network_interaction_ols",
            sample_size=n_obs,
            n_treated=int(np.sum(treatment == 1)),
            n_control=int(np.sum(treatment == 0)),
            pre_periods=0,
            post_periods=0,
            assumptions=dict(NetworkHeterogeneousEffectEstimator.metadata.assumptions),
            metadata={
                "mean_exposure": float(np.mean(exposure)),
                "feature_index": feature_index,
            },
        )
        return wrap_causal_output(
            report,
            extras={
                "network_hte_result": {
                    "point_estimate": point_estimate,
                    "confidence_interval": [float(confidence_interval[0]), float(confidence_interval[1])],
                    "group_effects": group_effects,
                    "coefficients": [float(value) for value in coef.tolist()],
                    "mean_exposure": float(np.mean(exposure)),
                }
            },
        )


__all__ = [
    "DistributionalTreatmentEffectEstimator",
    "NetworkHeterogeneousEffectEstimator",
    "ProximalBridgeEstimator",
]
