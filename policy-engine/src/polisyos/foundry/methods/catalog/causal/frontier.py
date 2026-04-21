"""Frontier causal estimators for proximal, distributional, and network-aware effects."""
from __future__ import annotations

from dataclasses import is_dataclass
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


def _validate_binary_treatment(treatment: np.ndarray) -> None:
    if not np.isin(treatment, [0.0, 1.0]).all():
        raise ValueError("treatment must be binary (0/1)")


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
    centered = np.asarray(proxy, dtype=float).reshape(-1)
    centered = centered - float(np.mean(centered))
    columns = [centered ** degree for degree in range(1, max_degree + 1)]
    return _standardized_columns(np.column_stack(columns))


def _bridge_operator_diagnostics(
    *,
    treatment: np.ndarray,
    covariates: np.ndarray,
    treatment_proxy: np.ndarray,
    outcome_proxy: np.ndarray,
    ridge: float,
) -> tuple[float, float, float, float]:
    """Approximate proxy-operator completeness with residualized sieve SVD."""

    baseline = _baseline_design(treatment, covariates)
    z_residual = _residualize_on_baseline(treatment_proxy, baseline, ridge=ridge)
    w_residual = _residualize_on_baseline(outcome_proxy, baseline, ridge=ridge)
    proxy_association = abs(_safe_correlation(z_residual, w_residual))

    z_basis = _residualize_on_baseline(_proxy_sieve_basis(treatment_proxy), baseline, ridge=ridge)
    w_basis = _residualize_on_baseline(_proxy_sieve_basis(outcome_proxy), baseline, ridge=ridge)
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
